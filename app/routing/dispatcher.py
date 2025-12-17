"""Message dispatcher.

The dispatcher is the glue between the Telegram user-bot (which reads messages) and the
filtering/forwarding subsystem.

Responsibilities:
- accept an incoming *normalized* message from user-bot
- load active subscriptions and filters from DB
- run the filtering pipeline
- persist match results and create forwarding tasks/records

Telegram integration is intentionally abstracted via an optional `Forwarder`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.domain.entities import (
    FilterConfig,
    FilterMode,
    FilterRule,
    KeywordOptions,
    NormalizedText,
    SemanticOptions,
)
from app.filters.pipeline import run_pipeline
from app.infra.db.models import (
    ForwardedStatus,
    MatchType as DbMatchType,
    SourceType as DbSourceType,
)
from app.infra.db.models import Filter as DbFilter
from app.infra.db.models import Subscription as DbSubscription
from app.infra.db.models import User as DbUser
from app.infra.db.repositories import (
    FilterMatchRepository,
    FilterRepository,
    ForwardedMessageRepository,
    MessageRepository,
    SourceRepository,
    SubscriptionRepository,
    UserRepository,
)
from app.nlp.preprocess import normalize_text

logger = logging.getLogger(__name__)


class Forwarder(Protocol):
    """Abstraction over Telegram forwarding/copying."""

    async def forward(
        self,
        *,
        from_chat_id: int,
        telegram_message_id: int,
        to_chat_id: int,
    ) -> int:
        """Forward message and return forwarded telegram message id."""


class IncomingMessage(BaseModel):
    """Incoming message payload from user-bot."""

    telegram_message_id: int
    chat_id: int
    date: datetime
    text: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Optional precomputed normalization.
    normalized_text: Optional[NormalizedText] = None

    # Optional source hints (used only if source is missing in DB)
    source_type: Optional[str] = None
    source_title: Optional[str] = None
    source_username: Optional[str] = None


@dataclass(frozen=True)
class DispatchResult:
    message_id: int
    source_id: int
    matched_filters: list[int]
    matches_created: int
    forwards_created: int
    forwards_sent: int


def _parse_source_type(v: Optional[str]) -> DbSourceType:
    if not v:
        return DbSourceType.CHANNEL
    s = v.strip().lower()
    for t in DbSourceType:
        if t.value == s:
            return t
    return DbSourceType.CHANNEL


def _safe_keyword_options(settings: Optional[dict[str, Any]]) -> KeywordOptions:
    if not settings:
        return KeywordOptions()
    try:
        return KeywordOptions(**settings)
    except Exception:
        logger.warning("Invalid keyword_options in filter.settings; using defaults")
        return KeywordOptions()


def _safe_semantic_options(settings: Optional[dict[str, Any]], *, threshold: float) -> SemanticOptions:
    base = SemanticOptions(threshold=threshold)
    if not settings:
        return base
    try:
        # Do not trust stored threshold; column is the source of truth.
        tmp = SemanticOptions(**{**settings, "threshold": threshold})
        return tmp
    except Exception:
        logger.warning("Invalid semantic_options in filter.settings; using defaults")
        return base


def _db_filter_to_rule(db_filter: DbFilter) -> FilterRule:
    extra = db_filter.settings or {}

    kw_opts = _safe_keyword_options(extra.get("keyword_options"))
    sem_opts = _safe_semantic_options(extra.get("semantic_options"), threshold=float(db_filter.semantic_threshold))

    require_all = bool(extra.get("require_all_keywords", False))

    cfg = FilterConfig(
        mode=FilterMode(db_filter.mode.value),
        keywords=list(db_filter.keywords or []),
        topics=list(db_filter.topics or []),
        keyword_options=kw_opts,
        semantic_options=sem_opts,
        require_all_keywords=require_all,
    )

    return FilterRule(
        id=int(db_filter.id),
        user_id=int(db_filter.user_id),
        name=str(db_filter.name),
        is_active=bool(db_filter.is_active),
        config=cfg,
        created_at=db_filter.created_at,
        updated_at=db_filter.updated_at,
    )


class Dispatcher:
    """Orchestrates message processing using DB repositories and filtering pipeline."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        forwarder: Optional[Forwarder] = None,
        user_repo: Optional[UserRepository] = None,
        source_repo: Optional[SourceRepository] = None,
        subscription_repo: Optional[SubscriptionRepository] = None,
        filter_repo: Optional[FilterRepository] = None,
        message_repo: Optional[MessageRepository] = None,
        match_repo: Optional[FilterMatchRepository] = None,
        forwarded_repo: Optional[ForwardedMessageRepository] = None,
    ):
        self._session = session
        self._forwarder = forwarder

        self._users = user_repo or UserRepository(session)
        self._sources = source_repo or SourceRepository(session)
        self._subs = subscription_repo or SubscriptionRepository(session)
        self._filters = filter_repo or FilterRepository(session)
        self._messages = message_repo or MessageRepository(session)
        self._matches = match_repo or FilterMatchRepository(session)
        self._forwards = forwarded_repo or ForwardedMessageRepository(session)

    async def dispatch(self, incoming: IncomingMessage) -> DispatchResult:
        """Process a single incoming message."""

        settings = get_settings()
        text = incoming.text or ""
        if settings.filter.max_message_length and len(text) > settings.filter.max_message_length:
            text = text[: settings.filter.max_message_length]

        # Ensure source exists.
        source = await self._sources.get_by_telegram_chat_id(incoming.chat_id)
        if source is None:
            source, _created = await self._sources.get_or_create_by_telegram_chat_id(
                incoming.chat_id,
                title=incoming.source_title,
                username=incoming.source_username,
                type=_parse_source_type(incoming.source_type),
            )

        # Persist message (dedupe by telegram_message_id + chat_id).
        msg, _created = await self._messages.get_or_create_message(
            telegram_message_id=incoming.telegram_message_id,
            chat_id=incoming.chat_id,
            source_id=int(source.id),
            text=text,
            date=incoming.date,
            meta=incoming.metadata,
        )

        # Normalization (prefer incoming if provided).
        normalized = incoming.normalized_text
        if normalized is None:
            normalized = normalize_text(text)

        # Find subscribers to this source.
        subs: list[DbSubscription] = await self._subs.get_source_subscribers(int(source.id), active_only=True)

        matches_created = 0
        forwards_created = 0
        forwards_sent = 0
        matched_filters: list[int] = []

        for sub in subs:
            user: Optional[DbUser] = getattr(sub, "user", None)
            if user is None:
                user = await self._users.get(int(sub.user_id))

            if user is None or not user.is_active:
                continue

            # Load active filters for this user.
            db_filters = await self._filters.get_user_filters(int(user.id), active_only=True)
            rules = [_db_filter_to_rule(f) for f in db_filters if f.is_active]

            # Apply pipeline.
            results = run_pipeline(
                text=text,
                message_id=int(msg.id),
                rules=rules,
                normalized_text=normalized,
            )

            for res in results:
                matched_filters.append(int(res.filter_id))

                # Persist match.
                db_match_type = DbMatchType(res.match_type.value)
                _match, created = await self._matches.get_or_create_match(
                    message_id=int(msg.id),
                    filter_id=int(res.filter_id),
                    match_type=db_match_type,
                    score=float(res.score),
                    details=res.details,
                )
                if created:
                    matches_created += 1

                # Create forwarding record and (optionally) forward immediately.
                if user.target_chat_id is None:
                    continue

                fw = await self._forwards.create(
                    user_id=int(user.id),
                    filter_id=int(res.filter_id),
                    message_id=int(msg.id),
                    target_chat_id=int(user.target_chat_id),
                    status=ForwardedStatus.PENDING,
                )
                forwards_created += 1

                if self._forwarder is not None:
                    try:
                        forwarded_telegram_message_id = await self._forwarder.forward(
                            from_chat_id=incoming.chat_id,
                            telegram_message_id=incoming.telegram_message_id,
                            to_chat_id=int(user.target_chat_id),
                        )
                        await self._forwards.mark_as_sent(int(fw.id), int(forwarded_telegram_message_id))
                        forwards_sent += 1
                    except Exception as e:
                        await self._forwards.mark_as_failed(int(fw.id), str(e))

        # Mark processed (even if no matches).
        await self._messages.mark_as_processed(int(msg.id))

        return DispatchResult(
            message_id=int(msg.id),
            source_id=int(source.id),
            matched_filters=matched_filters,
            matches_created=matches_created,
            forwards_created=forwards_created,
            forwards_sent=forwards_sent,
        )
