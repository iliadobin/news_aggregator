"""
Background worker to deliver pending forwarded messages to target chats via Bot API.

Important:
- Bot API usually cannot forward/copy messages from channels where the bot is not a member.
- Therefore, we send the stored message text (and optional source link) instead of forward/copy.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aiogram import Bot

from app.infra.db.base import get_db_session
from app.infra.db.repositories import ForwardedMessageRepository, SourceRepository

logger = logging.getLogger(__name__)


def _build_public_link(*, source_username: Optional[str], telegram_message_id: int) -> Optional[str]:
    if not source_username:
        return None
    username = source_username.lstrip("@")
    if not username:
        return None
    if telegram_message_id <= 0:
        return None
    return f"https://t.me/{username}/{telegram_message_id}"


def _truncate(text: str, *, limit: int = 3800) -> str:
    s = (text or "").strip()
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + "…"


def _format_delivery_text(*, source_title: str, source_username: Optional[str], fw) -> str:
    msg = getattr(fw, "message", None)
    flt = getattr(fw, "filter", None)

    telegram_message_id = int(getattr(msg, "telegram_message_id", 0) or 0)
    link = _build_public_link(source_username=source_username, telegram_message_id=telegram_message_id)

    text = getattr(msg, "text", None) or ""
    text = _truncate(text)
    filter_name = getattr(flt, "name", None) or f"filter_id={getattr(fw, 'filter_id', None)}"
    header = f"Источник: {source_title}\nФильтр: {filter_name}"
    if link:
        header += f"\nСсылка: {link}"

    if text:
        return header + "\n\n" + text
    return header + "\n\n(нет текста)"


async def deliver_pending_forever(
    *,
    bot: Bot,
    stop_event: asyncio.Event,
    interval_seconds: int = 3,
    batch_size: int = 50,
) -> None:
    """
    Poll DB for pending forwards and deliver them.
    """
    while not stop_event.is_set():
        try:
            async with get_db_session() as session:
                fwd_repo = ForwardedMessageRepository(session)
                source_repo = SourceRepository(session)
                pending = await fwd_repo.get_pending_forwards(limit=batch_size)

                for fw in pending:
                    if stop_event.is_set():
                        break

                    try:
                        msg = getattr(fw, "message", None)
                        if msg is None:
                            await fwd_repo.mark_as_failed(int(fw.id), "Missing message relation")
                            continue

                        source = await source_repo.get(int(getattr(msg, "source_id")))
                        source_title = (
                            getattr(source, "title", None)
                            or getattr(source, "username", None)
                            or f"source_id={getattr(msg, 'source_id', None)}"
                        )
                        source_username = getattr(source, "username", None) if source is not None else None

                        text = _format_delivery_text(
                            source_title=str(source_title), source_username=source_username, fw=fw
                        )
                        sent = await bot.send_message(
                            chat_id=int(fw.target_chat_id),
                            text=text,
                            disable_web_page_preview=True,
                        )
                        await fwd_repo.mark_as_sent(int(fw.id), int(getattr(sent, "message_id")))
                    except Exception as e:
                        logger.exception("Failed to deliver pending forward", extra={"extra_data": {"id": fw.id}})
                        await fwd_repo.mark_as_failed(int(fw.id), str(e))

        except Exception:
            logger.exception("Pending forwards worker crashed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass

