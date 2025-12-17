"""
User-bot runner (Telethon).

Starts the Telethon client, authorizes via a persisted session, registers message handlers
and runs until disconnected.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.config.settings import TelegramUserBotSettings, get_userbot_settings
from app.infra.logging.config import setup_logging
from app.bots.user_bot.client import create_userbot_client
from app.bots.user_bot.handlers import SourceCache, register_handlers
from app.infra.db.base import get_db_session

logger = logging.getLogger(__name__)


def _log_task_result(task: asyncio.Task[object], *, name: str) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.info("%s task cancelled", name)
    except Exception:
        logger.exception("%s task crashed", name)


async def run_userbot(settings: Optional[TelegramUserBotSettings] = None) -> None:
    """
    Run Telegram user-bot.

    Requirements:
    - USERBOT_API_ID, USERBOT_API_HASH must be set
    - USERBOT_PHONE must be set on the first run (to login and create a session)
    """

    setup_logging()

    if settings is None:
        settings = get_userbot_settings()

    if settings.phone is None:
        logger.warning(
            "USERBOT_PHONE is not set. If the session is not authorized yet, Telethon login will fail."
        )

    client = create_userbot_client(settings)

    stop_event = asyncio.Event()
    source_cache = SourceCache(refresh_interval_seconds=60)
    register_handlers(client=client, source_cache=source_cache)

    refresh_task: Optional[asyncio.Task[object]] = None

    try:
        await client.start(phone=settings.phone)
        me = await client.get_me()
        logger.info(
            "User-bot started",
            extra={
                "extra_data": {
                    "me_id": getattr(me, "id", None),
                    "username": getattr(me, "username", None),
                }
            },
        )

        # Validate DB schema early to avoid noisy stacktraces later.
        try:
            async with get_db_session() as session:
                await session.execute(text("SELECT 1 FROM sources LIMIT 1"))
        except ProgrammingError as e:
            if "sources" in str(e).lower() and "does not exist" in str(e).lower():
                logger.error(
                    "DB schema is not initialized (missing table: sources). "
                    "Apply migrations: `alembic upgrade head` (or `python scripts/init_db.py`). "
                    "If `alembic upgrade head` prints no upgrade steps but `alembic_version` is already at head, "
                    "reset version and re-run: `alembic stamp base && alembic upgrade head`."
                )
                return
            raise

        refresh_task = asyncio.create_task(
            source_cache.run_forever(stop_event=stop_event), name="userbot_source_refresh"
        )
        refresh_task.add_done_callback(lambda t: _log_task_result(t, name="source_refresh"))

        await client.run_until_disconnected()

    except (KeyboardInterrupt, SystemExit):
        logger.info("User-bot stopped by signal")
    finally:
        stop_event.set()
        if refresh_task is not None:
            refresh_task.cancel()
            with contextlib.suppress(Exception):
                await refresh_task
        await client.disconnect()
        logger.info("User-bot disconnected")


if __name__ == "__main__":
    asyncio.run(run_userbot())

