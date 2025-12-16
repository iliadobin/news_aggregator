"""
Repository layer for database operations.

This module provides CRUD operations for all entities:
- UserRepository: operations on User model
- SourceRepository: operations on Source model
- SubscriptionRepository: operations on Subscription model
- FilterRepository: operations on Filter model
- MessageRepository: operations on Message model
- FilterMatchRepository: operations on FilterMatch model
- ForwardedMessageRepository: operations on ForwardedMessage model
"""

import logging
from datetime import datetime
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import Select, and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infra.db.models import (
    Base,
    Filter,
    FilterMatch,
    ForwardedMessage,
    ForwardedStatus,
    Message,
    Source,
    SourceType,
    Subscription,
    User,
)

logger = logging.getLogger(__name__)

# Generic type for models
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with common CRUD operations.

    Provides generic operations that can be reused across all repositories.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def get(self, id: int) -> Optional[ModelType]:
        """
        Get entity by ID.

        Args:
            id: Entity ID

        Returns:
            Entity or None if not found
        """
        result = await self.session.get(self.model, id)
        return result

    async def get_all(
        self, skip: int = 0, limit: int = 100, order_by: Optional[str] = None
    ) -> List[ModelType]:
        """
        Get all entities with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Column name to order by

        Returns:
            List of entities
        """
        query = select(self.model).offset(skip).limit(limit)

        if order_by:
            query = query.order_by(getattr(self.model, order_by, self.model.id))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelType:
        """
        Create new entity.

        Args:
            **kwargs: Entity attributes

        Returns:
            Created entity
        """
        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """
        Update entity by ID.

        Args:
            id: Entity ID
            **kwargs: Attributes to update

        Returns:
            Updated entity or None if not found
        """
        entity = await self.get(id)
        if entity is None:
            return None

        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, id: int) -> bool:
        """
        Delete entity by ID.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False if not found
        """
        entity = await self.get(id)
        if entity is None:
            return False

        await self.session.delete(entity)
        await self.session.flush()
        return True

    async def count(self) -> int:
        """
        Count total number of entities.

        Returns:
            Total count
        """
        result = await self.session.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()


class UserRepository(BaseRepository[User]):
    """Repository for User model."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Get user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User or None if not found
        """
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_by_telegram_id(
        self, telegram_id: int, **kwargs
    ) -> tuple[User, bool]:
        """
        Get or create user by Telegram ID.

        Args:
            telegram_id: Telegram user ID
            **kwargs: Additional user attributes

        Returns:
            Tuple of (user, created) where created is True if user was created
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user, False

        user = await self.create(telegram_id=telegram_id, **kwargs)
        return user, True

    async def get_active_users(self) -> List[User]:
        """
        Get all active users.

        Returns:
            List of active users
        """
        result = await self.session.execute(select(User).where(User.is_active == True))
        return list(result.scalars().all())

    async def get_admins(self) -> List[User]:
        """
        Get all admin users.

        Returns:
            List of admin users
        """
        result = await self.session.execute(
            select(User).where(and_(User.is_active == True, User.is_admin == True))
        )
        return list(result.scalars().all())

    async def update_preferences(self, user_id: int, preferences: dict) -> Optional[User]:
        """
        Update user preferences.

        Args:
            user_id: User ID
            preferences: Preferences dictionary

        Returns:
            Updated user or None if not found
        """
        return await self.update(user_id, preferences=preferences, updated_at=datetime.utcnow())


class SourceRepository(BaseRepository[Source]):
    """Repository for Source model."""

    def __init__(self, session: AsyncSession):
        super().__init__(Source, session)

    async def get_by_telegram_chat_id(self, telegram_chat_id: int) -> Optional[Source]:
        """
        Get source by Telegram chat ID.

        Args:
            telegram_chat_id: Telegram chat ID

        Returns:
            Source or None if not found
        """
        result = await self.session.execute(
            select(Source).where(Source.telegram_chat_id == telegram_chat_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_by_telegram_chat_id(
        self, telegram_chat_id: int, **kwargs
    ) -> tuple[Source, bool]:
        """
        Get or create source by Telegram chat ID.

        Args:
            telegram_chat_id: Telegram chat ID
            **kwargs: Additional source attributes

        Returns:
            Tuple of (source, created) where created is True if source was created
        """
        source = await self.get_by_telegram_chat_id(telegram_chat_id)
        if source:
            return source, False

        source = await self.create(telegram_chat_id=telegram_chat_id, **kwargs)
        return source, True

    async def get_active_sources(self) -> List[Source]:
        """
        Get all active sources.

        Returns:
            List of active sources
        """
        result = await self.session.execute(select(Source).where(Source.is_active == True))
        return list(result.scalars().all())

    async def get_sources_by_type(self, source_type: SourceType) -> List[Source]:
        """
        Get sources by type.

        Args:
            source_type: Type of source (channel, group, private)

        Returns:
            List of sources
        """
        result = await self.session.execute(
            select(Source).where(and_(Source.type == source_type, Source.is_active == True))
        )
        return list(result.scalars().all())


class SubscriptionRepository(BaseRepository[Subscription]):
    """Repository for Subscription model."""

    def __init__(self, session: AsyncSession):
        super().__init__(Subscription, session)

    async def get_by_user_and_source(
        self, user_id: int, source_id: int
    ) -> Optional[Subscription]:
        """
        Get subscription by user and source.

        Args:
            user_id: User ID
            source_id: Source ID

        Returns:
            Subscription or None if not found
        """
        result = await self.session.execute(
            select(Subscription).where(
                and_(Subscription.user_id == user_id, Subscription.source_id == source_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_user_subscriptions(
        self, user_id: int, active_only: bool = True
    ) -> List[Subscription]:
        """
        Get all subscriptions for a user.

        Args:
            user_id: User ID
            active_only: If True, returns only active subscriptions

        Returns:
            List of subscriptions
        """
        query = (
            select(Subscription)
            .options(selectinload(Subscription.source))
            .where(Subscription.user_id == user_id)
        )

        if active_only:
            query = query.where(Subscription.is_active == True)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_source_subscribers(
        self, source_id: int, active_only: bool = True
    ) -> List[Subscription]:
        """
        Get all subscribers for a source.

        Args:
            source_id: Source ID
            active_only: If True, returns only active subscriptions

        Returns:
            List of subscriptions
        """
        query = (
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(Subscription.source_id == source_id)
        )

        if active_only:
            query = query.where(Subscription.is_active == True)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_subscription(
        self, user_id: int, source_id: int, priority: int = 0
    ) -> Optional[Subscription]:
        """
        Create subscription if it doesn't exist.

        Args:
            user_id: User ID
            source_id: Source ID
            priority: Subscription priority

        Returns:
            Subscription (new or existing) or None if creation failed
        """
        # Check if subscription already exists
        existing = await self.get_by_user_and_source(user_id, source_id)
        if existing:
            # Reactivate if inactive
            if not existing.is_active:
                return await self.update(
                    existing.id, is_active=True, updated_at=datetime.utcnow()
                )
            return existing

        return await self.create(user_id=user_id, source_id=source_id, priority=priority)

    async def deactivate_subscription(self, user_id: int, source_id: int) -> bool:
        """
        Deactivate subscription.

        Args:
            user_id: User ID
            source_id: Source ID

        Returns:
            True if deactivated, False if not found
        """
        subscription = await self.get_by_user_and_source(user_id, source_id)
        if not subscription:
            return False

        await self.update(subscription.id, is_active=False, updated_at=datetime.utcnow())
        return True


class FilterRepository(BaseRepository[Filter]):
    """Repository for Filter model."""

    def __init__(self, session: AsyncSession):
        super().__init__(Filter, session)

    async def get_user_filters(self, user_id: int, active_only: bool = True) -> List[Filter]:
        """
        Get all filters for a user.

        Args:
            user_id: User ID
            active_only: If True, returns only active filters

        Returns:
            List of filters
        """
        query = select(Filter).where(Filter.user_id == user_id)

        if active_only:
            query = query.where(Filter.is_active == True)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_filters(self) -> List[Filter]:
        """
        Get all active filters.

        Returns:
            List of active filters
        """
        result = await self.session.execute(select(Filter).where(Filter.is_active == True))
        return list(result.scalars().all())

    async def update_keywords(self, filter_id: int, keywords: list) -> Optional[Filter]:
        """
        Update filter keywords.

        Args:
            filter_id: Filter ID
            keywords: List of keywords

        Returns:
            Updated filter or None if not found
        """
        return await self.update(filter_id, keywords=keywords, updated_at=datetime.utcnow())

    async def update_topics(self, filter_id: int, topics: list) -> Optional[Filter]:
        """
        Update filter topics.

        Args:
            filter_id: Filter ID
            topics: List of topics

        Returns:
            Updated filter or None if not found
        """
        return await self.update(filter_id, topics=topics, updated_at=datetime.utcnow())

    async def update_threshold(self, filter_id: int, threshold: float) -> Optional[Filter]:
        """
        Update semantic threshold.

        Args:
            filter_id: Filter ID
            threshold: New threshold value (0.0-1.0)

        Returns:
            Updated filter or None if not found
        """
        return await self.update(
            filter_id, semantic_threshold=threshold, updated_at=datetime.utcnow()
        )


class MessageRepository(BaseRepository[Message]):
    """Repository for Message model."""

    def __init__(self, session: AsyncSession):
        super().__init__(Message, session)

    async def get_by_telegram_id(
        self, telegram_message_id: int, chat_id: int
    ) -> Optional[Message]:
        """
        Get message by Telegram message ID and chat ID.

        Args:
            telegram_message_id: Telegram message ID
            chat_id: Telegram chat ID

        Returns:
            Message or None if not found
        """
        result = await self.session.execute(
            select(Message).where(
                and_(
                    Message.telegram_message_id == telegram_message_id,
                    Message.chat_id == chat_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_message(
        self, telegram_message_id: int, chat_id: int, **kwargs
    ) -> tuple[Message, bool]:
        """
        Get or create message by Telegram message ID and chat ID.

        Args:
            telegram_message_id: Telegram message ID
            chat_id: Telegram chat ID
            **kwargs: Additional message attributes

        Returns:
            Tuple of (message, created) where created is True if message was created
        """
        message = await self.get_by_telegram_id(telegram_message_id, chat_id)
        if message:
            return message, False

        message = await self.create(
            telegram_message_id=telegram_message_id, chat_id=chat_id, **kwargs
        )
        return message, True

    async def get_source_messages(
        self, source_id: int, skip: int = 0, limit: int = 100
    ) -> List[Message]:
        """
        Get messages from a specific source.

        Args:
            source_id: Source ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of messages
        """
        result = await self.session.execute(
            select(Message)
            .where(Message.source_id == source_id)
            .order_by(Message.date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_unprocessed_messages(self, limit: int = 100) -> List[Message]:
        """
        Get unprocessed messages.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of unprocessed messages
        """
        result = await self.session.execute(
            select(Message)
            .where(Message.is_processed == False)
            .order_by(Message.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_as_processed(self, message_id: int) -> Optional[Message]:
        """
        Mark message as processed.

        Args:
            message_id: Message ID

        Returns:
            Updated message or None if not found
        """
        return await self.update(message_id, is_processed=True)

    async def get_messages_by_date_range(
        self, start_date: datetime, end_date: datetime, source_id: Optional[int] = None
    ) -> List[Message]:
        """
        Get messages within a date range.

        Args:
            start_date: Start date
            end_date: End date
            source_id: Optional source ID to filter by

        Returns:
            List of messages
        """
        query = select(Message).where(and_(Message.date >= start_date, Message.date <= end_date))

        if source_id:
            query = query.where(Message.source_id == source_id)

        query = query.order_by(Message.date.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())


class FilterMatchRepository(BaseRepository[FilterMatch]):
    """Repository for FilterMatch model."""

    def __init__(self, session: AsyncSession):
        super().__init__(FilterMatch, session)

    async def get_message_matches(self, message_id: int) -> List[FilterMatch]:
        """
        Get all filter matches for a message.

        Args:
            message_id: Message ID

        Returns:
            List of filter matches
        """
        result = await self.session.execute(
            select(FilterMatch)
            .options(selectinload(FilterMatch.filter))
            .where(FilterMatch.message_id == message_id)
            .order_by(FilterMatch.score.desc())
        )
        return list(result.scalars().all())

    async def get_filter_matches(self, filter_id: int, limit: int = 100) -> List[FilterMatch]:
        """
        Get all matches for a filter.

        Args:
            filter_id: Filter ID
            limit: Maximum number of matches to return

        Returns:
            List of filter matches
        """
        result = await self.session.execute(
            select(FilterMatch)
            .options(selectinload(FilterMatch.message))
            .where(FilterMatch.filter_id == filter_id)
            .order_by(FilterMatch.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_or_create_match(
        self, message_id: int, filter_id: int, **kwargs
    ) -> tuple[FilterMatch, bool]:
        """
        Get or create filter match.

        Args:
            message_id: Message ID
            filter_id: Filter ID
            **kwargs: Additional match attributes

        Returns:
            Tuple of (match, created) where created is True if match was created
        """
        result = await self.session.execute(
            select(FilterMatch).where(
                and_(FilterMatch.message_id == message_id, FilterMatch.filter_id == filter_id)
            )
        )
        match = result.scalar_one_or_none()

        if match:
            return match, False

        match = await self.create(message_id=message_id, filter_id=filter_id, **kwargs)
        return match, True

    async def get_top_matches(
        self, filter_id: int, min_score: float = 0.0, limit: int = 100
    ) -> List[FilterMatch]:
        """
        Get top matches for a filter by score.

        Args:
            filter_id: Filter ID
            min_score: Minimum score threshold
            limit: Maximum number of matches to return

        Returns:
            List of filter matches
        """
        result = await self.session.execute(
            select(FilterMatch)
            .options(selectinload(FilterMatch.message))
            .where(and_(FilterMatch.filter_id == filter_id, FilterMatch.score >= min_score))
            .order_by(FilterMatch.score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class ForwardedMessageRepository(BaseRepository[ForwardedMessage]):
    """Repository for ForwardedMessage model."""

    def __init__(self, session: AsyncSession):
        super().__init__(ForwardedMessage, session)

    async def get_user_forwarded_messages(
        self, user_id: int, limit: int = 100
    ) -> List[ForwardedMessage]:
        """
        Get forwarded messages for a user.

        Args:
            user_id: User ID
            limit: Maximum number of messages to return

        Returns:
            List of forwarded messages
        """
        result = await self.session.execute(
            select(ForwardedMessage)
            .options(
                selectinload(ForwardedMessage.message),
                selectinload(ForwardedMessage.filter),
            )
            .where(ForwardedMessage.user_id == user_id)
            .order_by(ForwardedMessage.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_forwards(self, limit: int = 100) -> List[ForwardedMessage]:
        """
        Get pending forwarded messages.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of pending forwarded messages
        """
        result = await self.session.execute(
            select(ForwardedMessage)
            .options(
                selectinload(ForwardedMessage.message),
                selectinload(ForwardedMessage.user),
                selectinload(ForwardedMessage.filter),
            )
            .where(ForwardedMessage.status == ForwardedStatus.PENDING)
            .order_by(ForwardedMessage.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_as_sent(
        self, forwarded_id: int, forwarded_telegram_message_id: int
    ) -> Optional[ForwardedMessage]:
        """
        Mark forwarded message as sent.

        Args:
            forwarded_id: ForwardedMessage ID
            forwarded_telegram_message_id: Telegram message ID of forwarded message

        Returns:
            Updated forwarded message or None if not found
        """
        return await self.update(
            forwarded_id,
            status=ForwardedStatus.SENT,
            forwarded_telegram_message_id=forwarded_telegram_message_id,
            forwarded_at=datetime.utcnow(),
        )

    async def mark_as_failed(
        self, forwarded_id: int, error_message: str
    ) -> Optional[ForwardedMessage]:
        """
        Mark forwarded message as failed.

        Args:
            forwarded_id: ForwardedMessage ID
            error_message: Error message

        Returns:
            Updated forwarded message or None if not found
        """
        return await self.update(
            forwarded_id, status=ForwardedStatus.FAILED, error_message=error_message
        )

    async def get_message_forwards(self, message_id: int) -> List[ForwardedMessage]:
        """
        Get all forwards of a specific message.

        Args:
            message_id: Message ID

        Returns:
            List of forwarded messages
        """
        result = await self.session.execute(
            select(ForwardedMessage)
            .options(selectinload(ForwardedMessage.user), selectinload(ForwardedMessage.filter))
            .where(ForwardedMessage.message_id == message_id)
            .order_by(ForwardedMessage.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_successful_forwards(
        self, user_id: Optional[int] = None, limit: int = 100
    ) -> List[ForwardedMessage]:
        """
        Get successfully forwarded messages.

        Args:
            user_id: Optional user ID to filter by
            limit: Maximum number of messages to return

        Returns:
            List of successful forwarded messages
        """
        query = (
            select(ForwardedMessage)
            .options(
                selectinload(ForwardedMessage.message), selectinload(ForwardedMessage.filter)
            )
            .where(ForwardedMessage.status == ForwardedStatus.SENT)
            .order_by(ForwardedMessage.forwarded_at.desc())
        )

        if user_id:
            query = query.where(ForwardedMessage.user_id == user_id)

        result = await self.session.execute(query.limit(limit))
        return list(result.scalars().all())
