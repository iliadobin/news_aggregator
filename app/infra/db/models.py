"""
ORM models for News Aggregator.

This module defines SQLAlchemy ORM models for all entities in the application:
- User: system users interacting with the control bot
- Source: news sources (channels, groups, private chats)
- Subscription: user subscriptions to sources
- Filter: filtering rules for message selection
- Message: original messages from sources
- FilterMatch: results of applying filters to messages
- ForwardedMessage: records of message delivery to target chats
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class SourceType(str, Enum):
    """Type of Telegram source."""

    CHANNEL = "channel"
    GROUP = "group"
    PRIVATE = "private"


class FilterMode(str, Enum):
    """Filter matching mode."""

    KEYWORD_ONLY = "keyword_only"
    SEMANTIC_ONLY = "semantic_only"
    COMBINED = "combined"


class MatchType(str, Enum):
    """Type of filter match."""

    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    COMBINED = "combined"


class ForwardedStatus(str, Enum):
    """Status of forwarded message."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class User(Base):
    """
    User entity representing a system user.

    Users interact with the control bot to manage filters and sources.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Target chat for message delivery (can be user's private chat or a channel)
    target_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # User preferences stored as JSON
    preferences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )
    filters: Mapped[list["Filter"]] = relationship(
        "Filter", back_populates="user", cascade="all, delete-orphan"
    )
    forwarded_messages: Mapped[list["ForwardedMessage"]] = relationship(
        "ForwardedMessage", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Source(Base):
    """
    Source entity representing a Telegram news source.

    Sources can be channels, groups, or private chats.
    """

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Additional metadata stored as JSON
    # NOTE: attribute name `metadata` is reserved by SQLAlchemy Declarative API.
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="source", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Source(id={self.id}, telegram_chat_id={self.telegram_chat_id}, title={self.title})>"


class Subscription(Base):
    """
    Subscription entity linking users to sources.

    Represents which sources a user is subscribed to.
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Priority/importance level (higher = more important)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    source: Mapped["Source"] = relationship("Source", back_populates="subscriptions")

    # Ensure one subscription per user-source pair
    __table_args__ = (UniqueConstraint("user_id", "source_id", name="uq_user_source"),)

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, source_id={self.source_id})>"


class Filter(Base):
    """
    Filter entity defining rules for message selection.

    Filters can use keyword matching, semantic matching, or both.
    """

    __tablename__ = "filters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Filter mode
    mode: Mapped[FilterMode] = mapped_column(
        SQLEnum(FilterMode), default=FilterMode.COMBINED, nullable=False
    )

    # Keywords/phrases for keyword matching (list stored as JSON)
    keywords: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    # Topics/tags for semantic matching (list stored as JSON)
    topics: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    # Semantic similarity threshold (0.0-1.0)
    semantic_threshold: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)

    # Additional filter settings stored as JSON
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="filters")
    filter_matches: Mapped[list["FilterMatch"]] = relationship(
        "FilterMatch", back_populates="filter", cascade="all, delete-orphan"
    )
    forwarded_messages: Mapped[list["ForwardedMessage"]] = relationship(
        "ForwardedMessage", back_populates="filter", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Filter(id={self.id}, user_id={self.user_id}, name={self.name}, mode={self.mode})>"


class Message(Base):
    """
    Message entity representing original messages from sources.

    Stores messages read by the user bot from Telegram sources.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Message content
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Message date from Telegram
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Message metadata (media, links, language, etc.) stored as JSON
    # NOTE: attribute name `metadata` is reserved by SQLAlchemy Declarative API.
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True, default=dict)

    # Processing status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="messages")
    filter_matches: Mapped[list["FilterMatch"]] = relationship(
        "FilterMatch", back_populates="message", cascade="all, delete-orphan"
    )
    forwarded_messages: Mapped[list["ForwardedMessage"]] = relationship(
        "ForwardedMessage", back_populates="message", cascade="all, delete-orphan"
    )

    # Ensure one message per telegram_message_id and chat_id pair
    __table_args__ = (
        UniqueConstraint("telegram_message_id", "chat_id", name="uq_telegram_message_chat"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, telegram_message_id={self.telegram_message_id}, chat_id={self.chat_id})>"


class FilterMatch(Base):
    """
    FilterMatch entity representing the result of applying a filter to a message.

    Records which filters matched which messages and with what score.
    """

    __tablename__ = "filter_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("filters.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Type of match (keyword, semantic, or combined)
    match_type: Mapped[MatchType] = mapped_column(SQLEnum(MatchType), nullable=False)

    # Match score (for semantic matches, this is similarity; for keyword, can be count or binary)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Additional match details stored as JSON (matched keywords, semantic similarity details, etc.)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="filter_matches")
    filter: Mapped["Filter"] = relationship("Filter", back_populates="filter_matches")

    # Ensure one match per message-filter pair
    __table_args__ = (UniqueConstraint("message_id", "filter_id", name="uq_message_filter"),)

    def __repr__(self) -> str:
        return f"<FilterMatch(id={self.id}, message_id={self.message_id}, filter_id={self.filter_id}, score={self.score})>"


class ForwardedMessage(Base):
    """
    ForwardedMessage entity representing actual message delivery to target chats.

    Records when and where messages were forwarded after matching filters.
    """

    __tablename__ = "forwarded_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("filters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Target chat where message was forwarded
    target_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Telegram message ID of the forwarded message
    forwarded_telegram_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )

    # Forwarding status
    status: Mapped[ForwardedStatus] = mapped_column(
        SQLEnum(ForwardedStatus), default=ForwardedStatus.PENDING, nullable=False
    )

    # Error message if forwarding failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    forwarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="forwarded_messages")
    filter: Mapped["Filter"] = relationship("Filter", back_populates="forwarded_messages")
    message: Mapped["Message"] = relationship("Message", back_populates="forwarded_messages")

    def __repr__(self) -> str:
        return f"<ForwardedMessage(id={self.id}, message_id={self.message_id}, target_chat_id={self.target_chat_id}, status={self.status})>"
