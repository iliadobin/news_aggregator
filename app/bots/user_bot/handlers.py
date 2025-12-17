"""
User-bot handlers for incoming Telegram messages (Telethon).

Responsibilities (Epic 6):
- receive new messages from selected chats/channels (sources)
- transform Telegram messages into dispatcher payload (IncomingMessage)
- ensure minimal Source info is available for persistence (title/type/username)
- log errors and exceptions robustly
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.exc import ProgrammingError
from telethon import events
from telethon.tl.custom.message import Message as TgMessage
from telethon.tl.types import Channel, Chat, User

from app.infra.db.base import get_db_session
from app.infra.db.models import SourceType as DbSourceType
from app.infra.db.repositories import SourceRepository
from app.infra.logging.config import LogContext
from app.routing.dispatcher import Dispatcher, IncomingMessage

logger = logging.getLogger(__name__)

_DB_SCHEMA_HELP = (
    "DB schema is not initialized (tables are missing). "
    "Run `alembic upgrade head` or `python scripts/init_db.py` for the configured DB. "
    "If `alembic_version` is stamped at head but tables are missing, run "
    "`alembic stamp base && alembic upgrade head`."
)


def _is_missing_table_error(exc: BaseException) -> bool:
    """
    Best-effort detection of 'relation does not exist' for Postgres/asyncpg.
    We keep it string-based to avoid tight coupling to asyncpg classes.
    """

    msg = str(exc).lower()
    if "does not exist" in msg and ("relation" in msg or "table" in msg):
        return True
    return False


def _infer_source_type(chat: Any) -> str:
    # Must align with app.infra.db.models.SourceType values: channel/group/private
    if isinstance(chat, User):
        return DbSourceType.PRIVATE.value
    if isinstance(chat, Chat):
        return DbSourceType.GROUP.value
    if isinstance(chat, Channel):
        # Channel can represent both broadcast channels and megagroups.
        if getattr(chat, "megagroup", False):
            return DbSourceType.GROUP.value
        return DbSourceType.CHANNEL.value
    return DbSourceType.CHANNEL.value


def _infer_source_title(chat: Any) -> Optional[str]:
    if chat is None:
        return None
    if isinstance(chat, User):
        first = (chat.first_name or "").strip()
        last = (chat.last_name or "").strip()
        full = " ".join([p for p in [first, last] if p])
        return full or (chat.username or None)
    return getattr(chat, "title", None) or getattr(chat, "username", None)


def _infer_source_username(chat: Any) -> Optional[str]:
    if chat is None:
        return None
    return getattr(chat, "username", None)


def _message_metadata(msg: TgMessage) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "sender_id": getattr(msg, "sender_id", None),
        "reply_to_msg_id": getattr(getattr(msg, "reply_to", None), "reply_to_msg_id", None),
        "fwd_from": bool(getattr(msg, "fwd_from", None)),
        "via_bot_id": getattr(msg, "via_bot_id", None),
        "is_reply": bool(getattr(msg, "is_reply", False)),
        "is_forward": bool(getattr(msg, "is_forward", False)),
        "has_media": bool(getattr(msg, "media", None)),
    }
    if getattr(msg, "media", None) is not None:
        meta["media_type"] = msg.media.__class__.__name__
    if getattr(msg, "entities", None) is not None:
        meta["entities"] = [e.__class__.__name__ for e in (msg.entities or [])]
    return meta


async def telegram_event_to_incoming(event: events.NewMessage.Event) -> IncomingMessage:
    msg: TgMessage = event.message
    chat = event.chat
    if chat is None:
        try:
            chat = await event.get_chat()
        except Exception:
            chat = None

    # Telethon: `chat_id` is negative for groups/channels; keep as-is (Telegram uses signed ids)
    chat_id = int(event.chat_id) if event.chat_id is not None else int(msg.peer_id.channel_id)  # type: ignore[attr-defined]

    text = getattr(msg, "raw_text", None) or getattr(msg, "message", None)
    date: datetime = msg.date  # timezone-aware datetime from Telethon

    return IncomingMessage(
        telegram_message_id=int(msg.id),
        chat_id=chat_id,
        date=date,
        text=text,
        metadata=_message_metadata(msg),
        source_type=_infer_source_type(chat),
        source_title=_infer_source_title(chat),
        source_username=_infer_source_username(chat),
    )


@dataclass
class SourceCache:
    """
    In-memory cache for active source chat ids.

    We intentionally do NOT use Telethon `events.NewMessage(chats=...)` filter because sources
    can change at runtime (control-bot / DB updates). Instead we refresh a set periodically and
    filter inside the handler.
    """

    refresh_interval_seconds: int = 60
    _allowed_chat_ids: set[int] = None  # type: ignore[assignment]
    _lock: asyncio.Lock = None  # type: ignore[assignment]
    _schema_missing_logged: bool = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._allowed_chat_ids = set()
        self._lock = asyncio.Lock()
        self._schema_missing_logged = False

    async def refresh(self) -> None:
        async with self._lock:
            try:
                async with get_db_session() as session:
                    repo = SourceRepository(session)
                    sources = await repo.get_active_sources()
                    self._allowed_chat_ids = {int(s.telegram_chat_id) for s in sources}
            except ProgrammingError as e:
                # Most common first-run issue: DB exists but migrations not applied.
                if _is_missing_table_error(e) and not self._schema_missing_logged:
                    self._schema_missing_logged = True
                    logger.error(_DB_SCHEMA_HELP)
                    # Keep cache empty; user-bot will ignore all messages until DB is ready.
                    self._allowed_chat_ids = set()
                    return
                raise

            logger.info(
                "Refreshed active sources",
                extra={"extra_data": {"active_sources": len(self._allowed_chat_ids)}},
            )

    async def is_allowed(self, chat_id: int) -> bool:
        async with self._lock:
            return int(chat_id) in self._allowed_chat_ids

    async def run_forever(self, *, stop_event: asyncio.Event) -> None:
        # Initial load
        try:
            await self.refresh()
        except Exception:
            logger.exception("Failed to refresh sources on startup")

        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.refresh_interval_seconds)
            except asyncio.TimeoutError:
                pass

            if stop_event.is_set():
                break

            try:
                await self.refresh()
            except Exception:
                logger.exception("Failed to refresh sources")


def register_handlers(*, client: Any, source_cache: SourceCache) -> None:
    """
    Register Telethon event handlers.

    Args:
        client: Telethon TelegramClient instance
        source_cache: cache controlling which chat_ids are treated as sources
    """

    @client.on(events.NewMessage)
    async def on_new_message(event: events.NewMessage.Event) -> None:
        try:
            if event.chat_id is None or event.message is None:
                return

            chat_id = int(event.chat_id)
            if not await source_cache.is_allowed(chat_id):
                return

            incoming = await telegram_event_to_incoming(event)
            with LogContext(message_id=incoming.telegram_message_id):
                async with get_db_session() as session:
                    dispatcher = Dispatcher(session=session, forwarder=None)
                    await dispatcher.dispatch(incoming)

        except Exception:
            # Always keep user-bot alive; log full traceback.
            logger.exception("Unhandled exception in user-bot message handler")

