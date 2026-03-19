import json
import os
import time as time_mod
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, request, send_from_directory

from server.app import db
from server.file_handler import get_upload_dir, save_upload
from server.models import Bot, ChatUser, Conversation, FileAttachment, Message, PushSubscription
from server.sse import sse_broker

bot_api_bp = Blueprint("bot_api", __name__)


# --- Auth decorator ---


def bot_from_token(f):
    """Extract and validate bot from URL token."""

    @wraps(f)
    def wrapper(token, *args, **kwargs):
        bot = Bot.query.filter_by(api_token=token, is_active=True).first()
        if not bot:
            return jsonify({"ok": False, "error_code": 401, "description": "Unauthorized"}), 401
        request.bot = bot
        return f(token, *args, **kwargs)

    return wrapper


# --- Helpers ---


def _message_to_tg(message, bot):
    """Convert a Message to Telegram-format response."""
    result = {
        "message_id": message.id,
        "from": {
            "id": bot.id,
            "is_bot": True,
            "first_name": bot.name,
            "username": bot.username,
        },
        "chat": {
            "id": message.conversation_id,
            "type": message.conversation.chat_type or "private",
        },
        "date": int(message.created_at.timestamp()),
    }
    if message.text:
        result["text"] = message.text
    if message.reply_markup:
        try:
            result["reply_markup"] = json.loads(message.reply_markup)
        except (json.JSONDecodeError, TypeError):
            pass
    if message.attachments:
        for att in message.attachments:
            if att.mime_type and att.mime_type.startswith("image/"):
                result.setdefault("photo", []).append(
                    {
                        "file_id": att.file_id,
                        "file_unique_id": att.file_id,
                        "width": 0,
                        "height": 0,
                        "file_size": att.file_size,
                    }
                )
            else:
                result["document"] = {
                    "file_id": att.file_id,
                    "file_name": att.filename,
                    "file_size": att.file_size,
                    "mime_type": att.mime_type,
                }
    return result


def _serialize_message_for_sse(message):
    """Serialize message for SSE push to frontend."""
    result = {
        "id": message.id,
        "sender_type": message.sender_type,
        "sender_name": message.sender_name or "",
        "sender_id": message.sender_id,
        "text": message.text if not message.is_deleted else "",
        "parse_mode": message.parse_mode or "",
        "date": int(message.created_at.timestamp()),
        "is_deleted": bool(message.is_deleted),
        "attachments": [
            {
                "file_id": att.file_id,
                "filename": att.filename,
                "mime_type": att.mime_type,
                "file_size": att.file_size,
            }
            for att in message.attachments
        ] if not message.is_deleted else [],
    }
    if message.edited_at:
        result["edited_at"] = int(message.edited_at.timestamp())
    if message.reply_markup and not message.is_deleted:
        try:
            result["reply_markup"] = json.loads(message.reply_markup)
        except (json.JSONDecodeError, TypeError):
            pass
    return result


def _publish_to_conversation_users(conv, event_type, data):
    """Publish SSE event to all users in a conversation."""
    for uid in conv.get_all_user_ids():
        sse_broker.publish_user(uid, event_type, data)
    if event_type == "new_message":
        _send_push_notifications(conv, data)


def _send_push_notifications(conv, data):
    """Send Web Push notifications to all users in a conversation."""
    import logging
    from flask import current_app

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return

    logger = logging.getLogger(__name__)
    vapid_private = current_app.config.get("VAPID_PRIVATE_KEY")
    if not vapid_private:
        return

    msg_data = data.get("message", {})
    bot_name = msg_data.get("sender_name", "")
    text = (msg_data.get("text") or "")[:100]
    payload = json.dumps({
        "title": bot_name,
        "body": text,
        "conv_id": conv.id,
    }, ensure_ascii=False)

    claims_email = current_app.config.get("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")

    for uid in conv.get_all_user_ids():
        subs = PushSubscription.query.filter_by(user_id=uid).all()
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": json.loads(sub.keys_json),
                    },
                    data=payload,
                    vapid_private_key=vapid_private,
                    vapid_claims={"sub": claims_email},
                )
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    db.session.delete(sub)
                    db.session.commit()
                else:
                    logger.warning("Push failed for user %s: %s", uid, e)
            except Exception as e:
                logger.warning("Push failed for user %s: %s", uid, e)


# --- Endpoints ---


@bot_api_bp.route("/<token>/setWebhook", methods=["POST"])
@bot_from_token
def set_webhook(token):
    bot = request.bot
    data = request.get_json(silent=True) or request.form
    url = data.get("url", "")

    bot.webhook_url = url
    db.session.commit()

    # Clear polling queue when switching to webhook mode
    if url:
        redis_client = sse_broker._redis
        if redis_client:
            redis_client.delete(f"bot:updates:{bot.id}")

    return jsonify({"ok": True, "result": True, "description": "Webhook was set"})


@bot_api_bp.route("/<token>/deleteWebhook", methods=["POST"])
@bot_from_token
def delete_webhook(token):
    bot = request.bot
    data = request.get_json(silent=True) or request.form or {}
    bot.webhook_url = ""
    db.session.commit()

    # Telegram-compatible: optionally drop pending updates from polling queue
    if str(data.get("drop_pending_updates", "")).lower() in ("true", "1", "yes"):
        redis_client = sse_broker._redis
        if redis_client:
            redis_client.delete(f"bot:updates:{bot.id}")

    return jsonify({"ok": True, "result": True, "description": "Webhook was deleted"})


@bot_api_bp.route("/<token>/getWebhookInfo", methods=["GET"])
@bot_from_token
def get_webhook_info(token):
    bot = request.bot
    pending = 0
    redis_client = sse_broker._redis
    if redis_client:
        pending = redis_client.llen(f"bot:updates:{bot.id}")
    return jsonify(
        {
            "ok": True,
            "result": {
                "url": bot.webhook_url or "",
                "has_custom_certificate": False,
                "pending_update_count": pending,
            },
        }
    )


@bot_api_bp.route("/<token>/getUpdates", methods=["GET", "POST"])
@bot_from_token
def get_updates(token):
    """Telegram-compatible getUpdates — long-polling for updates from Redis queue."""
    bot = request.bot

    if bot.webhook_url:
        return jsonify({
            "ok": False,
            "error_code": 409,
            "description": "Conflict: can't use getUpdates method while webhook is active",
        }), 409

    data = request.get_json(silent=True) or request.args

    offset = int(data.get("offset", 0))
    limit = min(int(data.get("limit", 100)), 100)
    timeout = min(int(data.get("timeout", 0)), 30)  # cap at 30s

    redis_client = sse_broker._redis
    if not redis_client:
        return jsonify({"ok": True, "result": []})

    key = f"bot:updates:{bot.id}"

    # Confirm (remove) updates with update_id < offset
    if offset > 0:
        all_raw = redis_client.lrange(key, 0, -1)
        remaining = []
        for raw in all_raw:
            try:
                update = json.loads(raw)
                if update.get("update_id", 0) >= offset:
                    remaining.append(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        redis_client.delete(key)
        if remaining:
            redis_client.rpush(key, *remaining)

    def _fetch():
        raw_list = redis_client.lrange(key, 0, limit - 1)
        results = []
        for raw in raw_list:
            try:
                results.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                pass
        return results

    updates = _fetch()

    # Long polling: wait for new updates up to timeout
    if not updates and timeout > 0:
        deadline = time_mod.time() + timeout
        pubsub = redis_client.pubsub()
        notify_channel = f"bot:updates:notify:{bot.id}"
        pubsub.subscribe(notify_channel)
        try:
            while time_mod.time() < deadline:
                remaining_time = deadline - time_mod.time()
                if remaining_time <= 0:
                    break
                msg = pubsub.get_message(timeout=min(1.0, remaining_time))
                if msg and msg["type"] == "message":
                    updates = _fetch()
                    if updates:
                        break
        finally:
            pubsub.unsubscribe(notify_channel)
            pubsub.close()

    return jsonify({"ok": True, "result": updates[:limit]})


@bot_api_bp.route("/<token>/getMe", methods=["GET"])
@bot_from_token
def get_me(token):
    bot = request.bot
    return jsonify(
        {
            "ok": True,
            "result": {
                "id": bot.id,
                "is_bot": True,
                "first_name": bot.name,
                "username": bot.username,
            },
        }
    )


@bot_api_bp.route("/<token>/sendMessage", methods=["POST"])
@bot_from_token
def send_message(token):
    bot = request.bot
    data = request.get_json(silent=True) or request.form

    chat_id = data.get("chat_id")
    text = data.get("text", "")
    parse_mode = data.get("parse_mode", "")
    reply_markup = data.get("reply_markup", "")

    if not chat_id:
        return jsonify({"ok": False, "error_code": 400, "description": "chat_id is required"}), 400
    if not text:
        return jsonify({"ok": False, "error_code": 400, "description": "text is required"}), 400

    conversation = db.session.get(Conversation, int(chat_id))
    if not conversation or conversation.bot_id != bot.id:
        return jsonify({"ok": False, "error_code": 400, "description": "Chat not found"}), 400

    # Validate and store reply_markup as JSON string
    markup_str = ""
    if reply_markup:
        if isinstance(reply_markup, str):
            try:
                json.loads(reply_markup)
                markup_str = reply_markup
            except json.JSONDecodeError:
                return jsonify({"ok": False, "error_code": 400, "description": "Invalid reply_markup JSON"}), 400
        elif isinstance(reply_markup, dict):
            markup_str = json.dumps(reply_markup, ensure_ascii=False)

    message = Message(
        conversation_id=conversation.id,
        sender_type="bot",
        sender_id=bot.id,
        sender_name=bot.name,
        text=text,
        parse_mode=parse_mode.lower() if parse_mode else "",
        reply_markup=markup_str,
    )
    db.session.add(message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    msg_sse = _serialize_message_for_sse(message)
    sse_broker.publish(conversation.id, msg_sse)
    _publish_to_conversation_users(conversation, "new_message", {
        "conversation_id": conversation.id,
        "message": msg_sse,
    })

    return jsonify({"ok": True, "result": _message_to_tg(message, bot)})


@bot_api_bp.route("/<token>/editMessageText", methods=["POST"])
@bot_from_token
def edit_message_text(token):
    """Edit a bot's message text (Telegram-compatible)."""
    bot = request.bot
    data = request.get_json(silent=True) or request.form

    chat_id = data.get("chat_id")
    message_id = data.get("message_id")
    text = data.get("text", "")
    parse_mode = data.get("parse_mode", "")
    reply_markup = data.get("reply_markup", "")

    if not chat_id or not message_id:
        return jsonify({"ok": False, "error_code": 400, "description": "chat_id and message_id are required"}), 400
    if not text:
        return jsonify({"ok": False, "error_code": 400, "description": "text is required"}), 400

    conversation = db.session.get(Conversation, int(chat_id))
    if not conversation or conversation.bot_id != bot.id:
        return jsonify({"ok": False, "error_code": 400, "description": "Chat not found"}), 400

    message = db.session.get(Message, int(message_id))
    if not message or message.conversation_id != conversation.id:
        return jsonify({"ok": False, "error_code": 400, "description": "Message not found"}), 400

    if message.sender_type != "bot" or message.sender_id != bot.id:
        return jsonify({"ok": False, "error_code": 400, "description": "Can only edit own messages"}), 400

    message.text = text
    if parse_mode:
        message.parse_mode = parse_mode.lower()
    message.edited_at = datetime.now(timezone.utc)

    if reply_markup:
        if isinstance(reply_markup, str):
            try:
                json.loads(reply_markup)
                message.reply_markup = reply_markup
            except json.JSONDecodeError:
                pass
        elif isinstance(reply_markup, dict):
            message.reply_markup = json.dumps(reply_markup, ensure_ascii=False)

    db.session.commit()

    msg_sse = _serialize_message_for_sse(message)
    edit_event = {"_type": "edit", **msg_sse}
    sse_broker.publish(conversation.id, edit_event)
    _publish_to_conversation_users(conversation, "message_edited", {
        "conversation_id": conversation.id,
        "message": msg_sse,
    })

    return jsonify({"ok": True, "result": _message_to_tg(message, bot)})


@bot_api_bp.route("/<token>/deleteMessage", methods=["POST"])
@bot_from_token
def delete_message(token):
    """Delete a message (Telegram-compatible, soft delete)."""
    bot = request.bot
    data = request.get_json(silent=True) or request.form

    chat_id = data.get("chat_id")
    message_id = data.get("message_id")

    if not chat_id or not message_id:
        return jsonify({"ok": False, "error_code": 400, "description": "chat_id and message_id are required"}), 400

    conversation = db.session.get(Conversation, int(chat_id))
    if not conversation or conversation.bot_id != bot.id:
        return jsonify({"ok": False, "error_code": 400, "description": "Chat not found"}), 400

    message = db.session.get(Message, int(message_id))
    if not message or message.conversation_id != conversation.id:
        return jsonify({"ok": False, "error_code": 400, "description": "Message not found"}), 400

    message.is_deleted = True
    message.text = ""
    message.reply_markup = ""
    db.session.commit()

    delete_event = {"_type": "delete", "message_id": message.id}
    sse_broker.publish(conversation.id, delete_event)
    _publish_to_conversation_users(conversation, "message_deleted", {
        "conversation_id": conversation.id,
        "message_id": message.id,
    })

    return jsonify({"ok": True, "result": True})


@bot_api_bp.route("/<token>/answerCallbackQuery", methods=["POST"])
@bot_from_token
def answer_callback_query(token):
    """Telegram-compatible answerCallbackQuery — acknowledges a callback button press."""
    data = request.get_json(silent=True) or request.form
    callback_query_id = data.get("callback_query_id")

    if not callback_query_id:
        return jsonify({"ok": False, "error_code": 400, "description": "callback_query_id is required"}), 400

    return jsonify({"ok": True, "result": True})


@bot_api_bp.route("/<token>/sendChatAction", methods=["POST"])
@bot_from_token
def send_chat_action(token):
    """Telegram-compatible sendChatAction — publishes typing event via SSE."""
    bot = request.bot
    data = request.get_json(silent=True) or request.form

    chat_id = data.get("chat_id")
    if not chat_id:
        return jsonify({"ok": False, "error_code": 400, "description": "chat_id is required"}), 400

    conversation = db.session.get(Conversation, int(chat_id))
    if not conversation or conversation.bot_id != bot.id:
        return jsonify({"ok": False, "error_code": 400, "description": "Chat not found"}), 400

    sse_broker.publish(conversation.id, {"_type": "typing", "bot_name": bot.name})
    _publish_to_conversation_users(conversation, "typing", {
        "conversation_id": conversation.id,
        "bot_name": bot.name,
    })

    return jsonify({"ok": True, "result": True})


@bot_api_bp.route("/<token>/sendDocument", methods=["POST"])
@bot_from_token
def send_document(token):
    bot = request.bot
    chat_id = request.form.get("chat_id") or (request.get_json(silent=True) or {}).get("chat_id")
    caption = request.form.get("caption", "") or (request.get_json(silent=True) or {}).get("caption", "")

    if not chat_id:
        return jsonify({"ok": False, "error_code": 400, "description": "chat_id is required"}), 400

    conversation = db.session.get(Conversation, int(chat_id))
    if not conversation or conversation.bot_id != bot.id:
        return jsonify({"ok": False, "error_code": 400, "description": "Chat not found"}), 400

    file = request.files.get("document")
    if not file:
        return jsonify({"ok": False, "error_code": 400, "description": "document file is required"}), 400

    message = Message(
        conversation_id=conversation.id,
        sender_type="bot",
        sender_id=bot.id,
        sender_name=bot.name,
        text=caption,
    )
    db.session.add(message)
    db.session.flush()

    attachment = save_upload(file)
    attachment.message_id = message.id
    db.session.add(attachment)
    conversation.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    msg_sse = _serialize_message_for_sse(message)
    sse_broker.publish(conversation.id, msg_sse)
    _publish_to_conversation_users(conversation, "new_message", {
        "conversation_id": conversation.id,
        "message": msg_sse,
    })

    return jsonify({"ok": True, "result": _message_to_tg(message, bot)})


@bot_api_bp.route("/<token>/sendPhoto", methods=["POST"])
@bot_from_token
def send_photo(token):
    bot = request.bot
    chat_id = request.form.get("chat_id") or (request.get_json(silent=True) or {}).get("chat_id")
    caption = request.form.get("caption", "") or (request.get_json(silent=True) or {}).get("caption", "")

    if not chat_id:
        return jsonify({"ok": False, "error_code": 400, "description": "chat_id is required"}), 400

    conversation = db.session.get(Conversation, int(chat_id))
    if not conversation or conversation.bot_id != bot.id:
        return jsonify({"ok": False, "error_code": 400, "description": "Chat not found"}), 400

    file = request.files.get("photo")
    if not file:
        return jsonify({"ok": False, "error_code": 400, "description": "photo file is required"}), 400

    message = Message(
        conversation_id=conversation.id,
        sender_type="bot",
        sender_id=bot.id,
        sender_name=bot.name,
        text=caption,
    )
    db.session.add(message)
    db.session.flush()

    attachment = save_upload(file)
    attachment.message_id = message.id
    db.session.add(attachment)
    conversation.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    msg_sse = _serialize_message_for_sse(message)
    sse_broker.publish(conversation.id, msg_sse)
    _publish_to_conversation_users(conversation, "new_message", {
        "conversation_id": conversation.id,
        "message": msg_sse,
    })

    return jsonify({"ok": True, "result": _message_to_tg(message, bot)})


@bot_api_bp.route("/<token>/getFile", methods=["GET"])
@bot_from_token
def get_file(token):
    file_id = request.args.get("file_id")
    if not file_id:
        return jsonify({"ok": False, "error_code": 400, "description": "file_id is required"}), 400

    attachment = FileAttachment.query.filter_by(file_id=file_id).first()
    if not attachment:
        return jsonify({"ok": False, "error_code": 404, "description": "File not found"}), 404

    return jsonify(
        {
            "ok": True,
            "result": {
                "file_id": attachment.file_id,
                "file_size": attachment.file_size,
                "file_path": f"file/{attachment.file_id}",
            },
        }
    )


@bot_api_bp.route("/<token>/file/<file_id>", methods=["GET"])
@bot_from_token
def download_file_bot(token, file_id):
    attachment = FileAttachment.query.filter_by(file_id=file_id).first()
    if not attachment:
        return jsonify({"ok": False, "error_code": 404, "description": "File not found"}), 404
    return send_from_directory(
        get_upload_dir(),
        attachment.stored_name,
        download_name=attachment.filename,
        as_attachment=True,
    )
