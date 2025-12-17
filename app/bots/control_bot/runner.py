"""
Control-bot runner (aiogram v3, long polling).
"""

from __future__ import annotations

import asyncio
import logging
import contextlib
from typing import Optional

from aiogram import Bot
from aiogram.types import BotCommand

from app.bots.control_bot.bot import create_bot, create_dispatcher
from app.bots.control_bot.forward_worker import deliver_pending_forever
from app.config.settings import TelegramBotSettings, get_bot_settings
from app.infra.logging.config import setup_logging

logger = logging.getLogger(__name__)


async def _set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Меню и регистрация"),
            BotCommand(command="settings", description="Настройки"),
            BotCommand(command="filters", description="Фильтры"),
            BotCommand(command="sources", description="Источники"),
            BotCommand(command="add_source", description="Добавить источник по ссылке/@username"),
            BotCommand(command="target", description="Целевой чат"),
            BotCommand(command="set_target", description="Сделать текущий чат целевым"),
            BotCommand(command="help", description="Справка"),
        ]
    )


async def run_control_bot(settings: Optional[TelegramBotSettings] = None) -> None:
    setup_logging()
    if settings is None:
        settings = get_bot_settings()

    bot = create_bot(bot_settings=settings)
    dp = create_dispatcher(bot_settings=settings)
    stop_event = asyncio.Event()
    worker_task: Optional[asyncio.Task[object]] = None

    await _set_commands(bot)
    me = await bot.get_me()
    logger.info(
        "Control-bot started",
        extra={"extra_data": {"me_id": getattr(me, "id", None), "username": getattr(me, "username", None)}},
    )

    worker_task = asyncio.create_task(
        deliver_pending_forever(bot=bot, stop_event=stop_event, interval_seconds=3),
        name="controlbot_deliver_pending",
    )

    try:
        await dp.start_polling(bot)
    finally:
        stop_event.set()
        if worker_task is not None:
            worker_task.cancel()
            with contextlib.suppress(Exception):
                await worker_task


if __name__ == "__main__":
    asyncio.run(run_control_bot())

