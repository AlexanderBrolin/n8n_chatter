import logging
import threading
import time
import uuid

import requests

from server.models import Bot, ChatUser, Conversation, Message

logger = logging.getLogger(__name__)

WEBHOOK_MAX_RETRIES = 3
WEBHOOK_BACKOFF_BASE = 2  # seconds


def build_update_payload(message, conversation, user, bot):
    """Build a Telegram-compatible Update payload."""
    chat_data = {
        "id": conversation.id,
        "type": conversation.chat_type or "private",
    }
    if conversation.chat_type == "group":
        chat_data["title"] = conversation.title or ""
    else:
        chat_data["first_name"] = user.first_name or user.username
        chat_data["last_name"] = user.last_name or ""
        chat_data["username"] = user.username

    payload = {
        "update_id": message.id,
        "message": {
            "message_id": message.id,
            "from": {
                "id": user.id,
                "is_bot": False,
                "first_name": user.first_name or user.username,
                "last_name": user.last_name or "",
                "username": user.username,
            },
            "chat": chat_data,
            "date": int(message.created_at.timestamp()),
        },
    }

    if message.text:
        payload["message"]["text"] = message.text

    if message.attachments:
        for att in message.attachments:
            doc_info = {
                "file_id": att.file_id,
                "file_name": att.filename,
                "file_size": att.file_size,
                "mime_type": att.mime_type,
            }
            if att.mime_type and att.mime_type.startswith("image/"):
                payload["message"].setdefault("photo", []).append(
                    {
                        "file_id": att.file_id,
                        "file_unique_id": att.file_id,
                        "width": 0,
                        "height": 0,
                        "file_size": att.file_size,
                    }
                )
            elif att.mime_type and att.mime_type.startswith("audio/"):
                payload["message"]["voice"] = {
                    "file_id": att.file_id,
                    "file_unique_id": att.file_id,
                    "duration": 0,
                    "file_size": att.file_size,
                    "mime_type": att.mime_type,
                }
            elif att.mime_type and att.mime_type.startswith("video/"):
                payload["message"]["video_note"] = {
                    "file_id": att.file_id,
                    "file_unique_id": att.file_id,
                    "length": 0,
                    "duration": 0,
                    "file_size": att.file_size,
                }
            else:
                payload["message"]["document"] = doc_info

    return payload


def _do_webhook_post(webhook_url, payload, bot_username, ref_id):
    """Execute webhook POST with retry logic."""
    for attempt in range(1, WEBHOOK_MAX_RETRIES + 1):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=30)
            if resp.status_code < 500:
                if resp.status_code >= 400:
                    logger.warning(
                        "Webhook to %s returned %d for %d: %s",
                        webhook_url, resp.status_code, ref_id,
                        resp.text[:200],
                    )
                return
            logger.warning(
                "Webhook to %s returned %d (attempt %d/%d)",
                webhook_url, resp.status_code, attempt, WEBHOOK_MAX_RETRIES,
            )
        except requests.RequestException as e:
            logger.error(
                "Webhook to %s failed (attempt %d/%d): %s",
                webhook_url, attempt, WEBHOOK_MAX_RETRIES, e,
            )

        if attempt < WEBHOOK_MAX_RETRIES:
            time.sleep(WEBHOOK_BACKOFF_BASE ** attempt)

    logger.error(
        "Webhook delivery failed after %d attempts: bot=%s ref_id=%d url=%s",
        WEBHOOK_MAX_RETRIES, bot_username, ref_id, webhook_url,
    )


def send_webhook(bot, conversation, message, user):
    """POST Telegram-format Update to the bot's webhook_url (fire-and-forget with retry)."""
    if not bot.webhook_url:
        logger.warning("Bot %s (id=%d) has no webhook_url configured", bot.username, bot.id)
        return

    payload = build_update_payload(message, conversation, user, bot)

    thread = threading.Thread(
        target=_do_webhook_post,
        args=(bot.webhook_url, payload, bot.username, message.id),
        daemon=True,
    )
    thread.start()


def send_callback_webhook(bot, conversation, message, user, callback_data):
    """POST Telegram-compatible callback_query to the bot's webhook_url."""
    if not bot.webhook_url:
        logger.warning("Bot %s (id=%d) has no webhook_url configured", bot.username, bot.id)
        return

    chat_data = {
        "id": conversation.id,
        "type": conversation.chat_type or "private",
    }
    if conversation.chat_type == "group":
        chat_data["title"] = conversation.title or ""

    payload = {
        "update_id": message.id,
        "callback_query": {
            "id": str(uuid.uuid4()),
            "from": {
                "id": user.id,
                "is_bot": False,
                "first_name": user.first_name or user.username,
                "last_name": user.last_name or "",
                "username": user.username,
            },
            "message": {
                "message_id": message.id,
                "chat": chat_data,
                "date": int(message.created_at.timestamp()),
                "text": message.text or "",
            },
            "chat_instance": str(conversation.id),
            "data": callback_data,
        },
    }

    thread = threading.Thread(
        target=_do_webhook_post,
        args=(bot.webhook_url, payload, bot.username, message.id),
        daemon=True,
    )
    thread.start()
