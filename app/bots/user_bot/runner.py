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
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest

from app.config.settings import TelegramUserBotSettings, get_userbot_settings
from app.infra.logging.config import setup_logging
from app.bots.user_bot.client import create_userbot_client
from app.bots.user_bot.handlers import SourceCache, register_handlers
from app.infra.db.base import get_db_session
from app.infra.db.repositories import SourceRepository

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
    join_task: Optional[asyncio.Task[object]] = None

    async def _ensure_joined_sources_forever(*, interval_seconds: int = 120) -> None:
        """
        Periodically ensure the user-bot account is joined to all active sources from DB.

        This is required for receiving new messages in channels/groups via updates.
        """
        # initial small delay to allow client.start() to complete
        await asyncio.sleep(2)
        while not stop_event.is_set():
            try:
                async with get_db_session() as session:
                    repo = SourceRepository(session)
                    sources = await repo.get_active_sources()

                for s in sources:
                    if stop_event.is_set():
                        break
                    ref: object
                    username = getattr(s, "username", None)
                    if username:
                        ref = f"@{username}" if not str(username).startswith("@") else str(username)
                    else:
                        ref = int(s.telegram_chat_id)

                    try:
                        entity = await client.get_entity(ref)
                        await client(JoinChannelRequest(entity))
                        logger.info(
                            "Joined source",
                            extra={
                                "extra_data": {
                                    "source_id": int(s.id),
                                    "telegram_chat_id": int(s.telegram_chat_id),
                                    "username": username,
                                }
                            },
                        )
                    except UserAlreadyParticipantError:
                        # Already joined; fine.
                        continue
                    except FloodWaitError as e:
                        # Telegram rate limits joins. Respect it.
                        seconds = int(getattr(e, "seconds", 30))
                        logger.warning("FloodWait while joining sources; sleeping %s seconds", seconds)
                        await asyncio.sleep(seconds)
                    except Exception:
                        logger.exception(
                            "Failed to join source",
                            extra={
                                "extra_data": {
                                    "source_id": int(getattr(s, "id", 0)),
                                    "telegram_chat_id": int(getattr(s, "telegram_chat_id", 0)),
                                    "username": username,
                                }
                            },
                        )

            except Exception:
                logger.exception("Failed to ensure joined sources")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                pass

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

        join_task = asyncio.create_task(
            _ensure_joined_sources_forever(interval_seconds=120), name="userbot_ensure_joined_sources"
        )
        join_task.add_done_callback(lambda t: _log_task_result(t, name="ensure_joined_sources"))

        await client.run_until_disconnected()

    except (KeyboardInterrupt, SystemExit):
        logger.info("User-bot stopped by signal")
    finally:
        stop_event.set()
        if refresh_task is not None:
            refresh_task.cancel()
            with contextlib.suppress(Exception):
                await refresh_task
        if join_task is not None:
            join_task.cancel()
            with contextlib.suppress(Exception):
                await join_task
        await client.disconnect()
        logger.info("User-bot disconnected")


if __name__ == "__main__":
    asyncio.run(run_userbot())

