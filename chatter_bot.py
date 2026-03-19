"""
Chatter Bot helper — drop-in replacement for python-telegram-bot configuration.

Usage:
    # Before (Telegram):
    application = Application.builder().token(TOKEN).build()

    # After (Chatter):
    from chatter_bot import chatter_application
    application = chatter_application(TOKEN, "https://chat.company.com")

    # Everything else (handlers, run_polling, etc.) stays the same.
"""

from telegram.ext import Application


def chatter_application(
    token: str,
    base_url: str,
    **builder_kwargs,
) -> Application:
    """Build a python-telegram-bot Application configured for Chatter.

    Args:
        token: Bot API token from Chatter admin panel.
        base_url: Chatter instance URL, e.g. "https://chat.company.com".
        **builder_kwargs: Extra kwargs forwarded to ApplicationBuilder methods
            (e.g. connect_timeout, read_timeout).

    Returns:
        Configured Application instance. Use .run_polling() as usual.
    """
    api_url = base_url.rstrip("/") + "/api/bot"

    builder = (
        Application.builder()
        .token(token)
        .base_url(api_url)
        .base_file_url(api_url)
    )

    if "connect_timeout" in builder_kwargs:
        builder = builder.connect_timeout(builder_kwargs.pop("connect_timeout"))
    if "read_timeout" in builder_kwargs:
        builder = builder.read_timeout(builder_kwargs.pop("read_timeout"))

    return builder.build()
