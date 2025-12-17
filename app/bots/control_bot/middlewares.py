"""
Aiogram middlewares for control-bot.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from sqlalchemy.exc import ProgrammingError

from app.config.settings import TelegramBotSettings
from app.infra.db.base import get_db_session
from app.infra.db.repositories import (
    FilterRepository,
    SourceRepository,
    SubscriptionRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    """
    Inject DB session and repositories into handler `data`.

    Handlers can declare params: session, user_repo, filter_repo, source_repo, subscription_repo, bot_settings.
    """

    def __init__(self, *, bot_settings: TelegramBotSettings):
        super().__init__()
        self._bot_settings = bot_settings

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        data["bot_settings"] = self._bot_settings
        try:
            async with get_db_session() as session:
                data["session"] = session
                data["user_repo"] = UserRepository(session)
                data["filter_repo"] = FilterRepository(session)
                data["source_repo"] = SourceRepository(session)
                data["subscription_repo"] = SubscriptionRepository(session)
                return await handler(event, data)
        except ProgrammingError as e:
            # Most common local issue: migrations not applied. Keep it friendly.
            msg = str(e).lower()
            if "does not exist" in msg and ("relation" in msg or "table" in msg):
                logger.error("DB schema is not initialized for control-bot: %s", e)
            raise

