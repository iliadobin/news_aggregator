"""
Telegram user-bot client initialization (Telethon).

This module is responsible for creating a Telethon `TelegramClient` configured with:
- session-based authorization (stored on disk)
- API credentials loaded from settings

The first run may require interactive login (SMS/Telegram code) which Telethon handles.
"""

from __future__ import annotations

import logging
from pathlib import Path

from telethon import TelegramClient

from app.config.settings import TelegramUserBotSettings, get_userbot_settings

logger = logging.getLogger(__name__)


def _build_session_path(settings: TelegramUserBotSettings) -> Path:
    # Telethon accepts a string path without extension; it will create `<name>.session`.
    return settings.session_dir / settings.session_name


def create_userbot_client(settings: TelegramUserBotSettings | None = None) -> TelegramClient:
    """
    Create Telethon client for user-bot.

    Notes:
    - This does not connect/authenticate; call `await client.start(...)` in runner.
    - `USERBOT_SESSION_DIR` is created automatically by settings validator.
    """

    if settings is None:
        settings = get_userbot_settings()

    if settings.api_id is None or settings.api_hash is None:
        raise ValueError(
            "USERBOT_API_ID and USERBOT_API_HASH must be configured to start user-bot"
        )

    session_path = _build_session_path(settings)
    logger.info("Creating Telegram user-bot client", extra={"extra_data": {"session": str(session_path)}})
    return TelegramClient(str(session_path), int(settings.api_id), str(settings.api_hash))

