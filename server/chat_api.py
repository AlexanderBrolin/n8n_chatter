import json
import queue
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request, send_from_directory, session, stream_with_context
from werkzeug.security import generate_password_hash
from sqlalchemy import func, or_

from server.app import db
from server.chat_auth import chat_login_required
from server.file_handler import get_upload_dir, save_upload
from server.models import Bot, ChatUser, Conversation, FileAttachment, Message, QuickReply, conversation_members
from server.sse import sse_broker
from server.webhook import send_callback_webhook, send_webhook

chat_api_bp = Blueprint("chat_api", __name__)


# --- Helpers ---


def _serialize_message(msg):
    result = {
        "id": msg.id,
        "sender_type": msg.sender_type,
        "sender_name": msg.sender_name or "",
        "sender_id": msg.sender_id,
        "text": msg.text if not msg.is_deleted else "",
        "parse_mode": msg.parse_mode or "",
        "date": int(msg.created_at.timestamp()),
        "is_deleted": bool(msg.is_deleted),
        "attachments": [
            {
                "file_id": att.file_id,
                "filename": att.filename,
                "mime_type": att.mime_type,
                "file_size": att.file_size,
            }
            for att in msg.attachments
        ] if not msg.is_deleted else [],
    }
    if msg.edited_at:
        result["edited_at"] = int(msg.edited_at.timestamp())
    if msg.reply_markup and not msg.is_deleted:
        try:
            result["reply_markup"] = json.loads(msg.reply_markup)
        except (json.JSONDecodeError, TypeError):
            pass
    return result


def _user_conversations_query(user):
    """Get conversations where user is owner or group member."""
    return Conversation.query.filter(
        or_(
            Conversation.user_id == user.id,
            Conversation.id.in_(
                db.session.query(conversation_members.c.conversation_id)
                .filter(conversation_members.c.user_id == user.id)
            ),
        )
    )


def _publish_to_conversation_users(conv, event_type, data):
    """Publish SSE event to all users in a conversation."""
    for uid in conv.get_all_user_ids():
        sse_broker.publish_user(uid, event_type, data)


# --- Endpoints ---


@chat_api_bp.route("/profile", methods=["GET", "POST"])
@chat_login_required
def profile():
    """Get or update current user profile."""
    user = request.chat_user
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        user.first_name = data.get("first_name", user.first_name or "").strip()
        user.last_name = data.get("last_name", user.last_name or "").strip()
        new_password = data.get("password", "").strip()
        if new_password:
            if len(new_password) < 6:
                return jsonify({"error": "Пароль должен быть не менее 6 символов"}), 400
            user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({
        "username": user.username,
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "auth_provider": user.auth_provider or "local",
    })


@chat_api_bp.route("/bots")
@chat_login_required
def available_bots():
    """List bots available to the current user."""
    user = request.chat_user
    bots = [
        {
            "id": b.id,
            "name": b.name,
            "username": b.username,
            "description": b.description,
            "avatar_url": b.avatar_url,
        }
        for b in user.bots
        if b.is_active
    ]
    return jsonify(bots)


@chat_api_bp.route("/conversations")
@chat_login_required
def conversations():
    """List conversations for the current user (private + group)."""
    user = request.chat_user
    convs = (
        _user_conversations_query(user)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    result = []
    for conv in convs:
        last_msg = (
            Message.query.filter_by(conversation_id=conv.id)
            .filter(Message.is_deleted.is_(False))
            .order_by(Message.created_at.desc())
            .first()
        )
        conv_data = {
            "id": conv.id,
            "chat_type": conv.chat_type or "private",
            "title": conv.title or "",
            "bot": {
                "id": conv.bot.id,
                "name": conv.bot.name,
                "username": conv.bot.username,
                "avatar_url": conv.bot.avatar_url,
            },
            "last_message": _serialize_message(last_msg) if last_msg else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else "",
        }
        if conv.chat_type == "group":
            conv_data["members_count"] = len(conv.members)
        result.append(conv_data)
    return jsonify(result)


@chat_api_bp.route("/conversations/start", methods=["POST"])
@chat_login_required
def start_conversation():
    """Start a new conversation with a bot or return existing one."""
    user = request.chat_user
    data = request.get_json(silent=True) or {}
    bot_id = data.get("bot_id")

    if not bot_id:
        return jsonify({"error": "bot_id is required"}), 400

    bot = db.session.get(Bot, int(bot_id))
    if not bot or not bot.is_active:
        return jsonify({"error": "Bot not found"}), 404

    if bot not in user.bots:
        return jsonify({"error": "Access denied"}), 403

    conv = Conversation.query.filter_by(
        user_id=user.id, bot_id=bot.id, chat_type="private"
    ).first()
    if not conv:
        conv = Conversation(user_id=user.id, bot_id=bot.id, chat_type="private")
        db.session.add(conv)
        db.session.commit()

    return jsonify(
        {
            "id": conv.id,
            "chat_type": "private",
            "title": "",
            "bot": {
                "id": bot.id,
                "name": bot.name,
                "username": bot.username,
                "avatar_url": bot.avatar_url,
            },
        }
    )


@chat_api_bp.route("/conversations/<int:conv_id>/messages")
@chat_login_required
def get_messages(conv_id):
    """Get messages for a conversation with pagination."""
    user = request.chat_user
    conv = db.session.get(Conversation, conv_id)
    if not conv or not conv.user_has_access(user):
        return jsonify({"error": "Not found"}), 404

    before = request.args.get("before", type=int)
    limit = request.args.get("limit", 50, type=int)
    limit = min(limit, 100)

    query = Message.query.filter_by(conversation_id=conv.id)
    if before:
        query = query.filter(Message.id < before)
    messages = query.order_by(Message.created_at.desc()).limit(limit).all()
    messages.reverse()

    has_more = len(messages) == limit

    return jsonify(
        {
            "messages": [_serialize_message(m) for m in messages],
            "has_more": has_more,
        }
    )


@chat_api_bp.route("/conversations/<int:conv_id>/send", methods=["POST"])
@chat_login_required
def send_message(conv_id):
    """Send a message from the user (text + optional files)."""
    user = request.chat_user
    conv = db.session.get(Conversation, conv_id)
    if not conv or not conv.user_has_access(user):
        return jsonify({"error": "Not found"}), 404

    text = request.form.get("text", "").strip()
    files = request.files.getlist("files")

    if not text and not files:
        return jsonify({"error": "Message cannot be empty"}), 400

    message = Message(
        conversation_id=conv.id,
        sender_type="user",
        sender_id=user.id,
        sender_name=user.first_name or user.username,
        text=text,
    )
    db.session.add(message)
    db.session.flush()

    for f in files:
        if f and f.filename:
            attachment = save_upload(f)
            attachment.message_id = message.id
            db.session.add(attachment)

    conv.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    msg_data = _serialize_message(message)
    sse_broker.publish(conv.id, msg_data)
    _publish_to_conversation_users(conv, "new_message", {
        "conversation_id": conv.id,
        "message": msg_data,
    })

    send_webhook(conv.bot, conv, message, user)

    return jsonify(_serialize_message(message))


@chat_api_bp.route("/conversations/<int:conv_id>/messages/<int:msg_id>", methods=["DELETE"])
@chat_login_required
def delete_message(conv_id, msg_id):
    """Delete a message (soft delete). Users can delete their own messages."""
    user = request.chat_user
    conv = db.session.get(Conversation, conv_id)
    if not conv or not conv.user_has_access(user):
        return jsonify({"error": "Not found"}), 404

    msg = db.session.get(Message, msg_id)
    if not msg or msg.conversation_id != conv.id:
        return jsonify({"error": "Message not found"}), 404

    if msg.sender_type != "user" or msg.sender_id != user.id:
        return jsonify({"error": "Cannot delete this message"}), 403

    msg.is_deleted = True
    msg.text = ""
    msg.reply_markup = ""
    db.session.commit()

    delete_event = {"_type": "delete", "message_id": msg.id}
    sse_broker.publish(conv.id, delete_event)
    _publish_to_conversation_users(conv, "message_deleted", {
        "conversation_id": conv.id,
        "message_id": msg.id,
    })

    return jsonify({"ok": True})


@chat_api_bp.route("/conversations/<int:conv_id>/callback", methods=["POST"])
@chat_login_required
def inline_callback(conv_id):
    """Handle inline button callback — sends callback_query to n8n webhook."""
    user = request.chat_user
    conv = db.session.get(Conversation, conv_id)
    if not conv or not conv.user_has_access(user):
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    message_id = data.get("message_id")
    callback_data = data.get("data", "")

    if not message_id or not callback_data:
        return jsonify({"error": "message_id and data are required"}), 400

    msg = db.session.get(Message, int(message_id))
    if not msg or msg.conversation_id != conv.id:
        return jsonify({"error": "Message not found"}), 404

    send_callback_webhook(conv.bot, conv, msg, user, callback_data)

    return jsonify({"ok": True})


@chat_api_bp.route("/search")
@chat_login_required
def search_messages():
    """Full-text search across user's conversations."""
    user = request.chat_user
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify({"results": []})

    user_convs = _user_conversations_query(user).all()
    conv_ids = [c.id for c in user_convs]
    if not conv_ids:
        return jsonify({"results": []})

    conv_map = {c.id: c for c in user_convs}

    # PostgreSQL full-text search with Russian config
    results = Message.query.filter(
        Message.conversation_id.in_(conv_ids),
        Message.is_deleted.is_(False),
        func.to_tsvector("russian", func.coalesce(Message.text, "")).op("@@")(
            func.plainto_tsquery("russian", q)
        ),
    ).order_by(Message.created_at.desc()).limit(30).all()

    # Fallback to ILIKE if FTS returns nothing
    if not results:
        safe_q = q.replace("%", "\\%").replace("_", "\\_")
        results = Message.query.filter(
            Message.conversation_id.in_(conv_ids),
            Message.is_deleted.is_(False),
            Message.text.ilike(f"%{safe_q}%"),
        ).order_by(Message.created_at.desc()).limit(30).all()

    search_results = []
    for msg in results:
        conv = conv_map.get(msg.conversation_id)
        if conv:
            search_results.append({
                "message": _serialize_message(msg),
                "conversation_id": msg.conversation_id,
                "bot_name": conv.bot.name,
                "chat_title": conv.title if conv.chat_type == "group" else conv.bot.name,
            })

    return jsonify({"results": search_results})


@chat_api_bp.route("/conversations/<int:conv_id>/quick_replies")
@chat_login_required
def get_quick_replies(conv_id):
    """Get quick reply templates for the bot in this conversation."""
    user = request.chat_user
    conv = db.session.get(Conversation, conv_id)
    if not conv or not conv.user_has_access(user):
        return jsonify({"error": "Not found"}), 404

    replies = QuickReply.query.filter_by(bot_id=conv.bot_id).order_by(QuickReply.order).all()
    return jsonify([{"id": r.id, "text": r.text} for r in replies])


@chat_api_bp.route("/conversations/<int:conv_id>/stream")
@chat_login_required
def message_stream(conv_id):
    """SSE endpoint for real-time message updates."""
    user = request.chat_user
    conv = db.session.get(Conversation, conv_id)
    if not conv or not conv.user_has_access(user):
        return jsonify({"error": "Not found"}), 404

    def generate():
        q = sse_broker.subscribe(conv_id)
        try:
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            sse_broker.unsubscribe(conv_id, q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@chat_api_bp.route("/stream")
@chat_login_required
def user_stream():
    """User-level SSE endpoint for unread counters, notifications, typing."""
    user = request.chat_user

    def generate():
        q = sse_broker.subscribe_user(user.id)
        try:
            while True:
                try:
                    raw = q.get(timeout=30)
                    yield raw
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            sse_broker.unsubscribe_user(user.id, q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@chat_api_bp.route("/file/<file_id>")
@chat_login_required
def download_file(file_id):
    """Download a file by file_id."""
    attachment = FileAttachment.query.filter_by(file_id=file_id).first()
    if not attachment:
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(
        get_upload_dir(),
        attachment.stored_name,
        download_name=attachment.filename,
        as_attachment=True,
    )
