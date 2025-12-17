"""
Control-bot initialization (aiogram v3).
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bots.control_bot.handlers_filters import router as filters_router
from app.bots.control_bot.handlers_settings import router as settings_router
from app.bots.control_bot.handlers_sources import router as sources_router
from app.bots.control_bot.middlewares import DbSessionMiddleware
from app.config.settings import TelegramBotSettings


def create_dispatcher(*, bot_settings: TelegramBotSettings) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DbSessionMiddleware(bot_settings=bot_settings))
    dp.include_router(settings_router)
    dp.include_router(filters_router)
    dp.include_router(sources_router)
    return dp


def create_bot(*, bot_settings: TelegramBotSettings) -> Bot:
    if bot_settings.token is None:
        raise RuntimeError("BOT_TOKEN is not set")
    return Bot(token=bot_settings.token)

