"""
Database infrastructure module.

This module provides database connectivity, ORM models, and repositories.
"""

from app.infra.db.base import (
    DatabaseManager,
    close_database,
    get_db_manager,
    get_db_session,
    get_session,
    init_database,
)
from app.infra.db.models import (
    Base,
    Filter,
    FilterMatch,
    FilterMode,
    ForwardedMessage,
    ForwardedStatus,
    MatchType,
    Message,
    Source,
    SourceType,
    Subscription,
    User,
)
from app.infra.db.repositories import (
    BaseRepository,
    FilterMatchRepository,
    FilterRepository,
    ForwardedMessageRepository,
    MessageRepository,
    SourceRepository,
    SubscriptionRepository,
    UserRepository,
)

__all__ = [
    # Base
    "Base",
    "DatabaseManager",
    "init_database",
    "close_database",
    "get_db_manager",
    "get_session",
    "get_db_session",
    # Models
    "User",
    "Source",
    "Subscription",
    "Filter",
    "Message",
    "FilterMatch",
    "ForwardedMessage",
    # Enums
    "SourceType",
    "FilterMode",
    "MatchType",
    "ForwardedStatus",
    # Repositories
    "BaseRepository",
    "UserRepository",
    "SourceRepository",
    "SubscriptionRepository",
    "FilterRepository",
    "MessageRepository",
    "FilterMatchRepository",
    "ForwardedMessageRepository",
]
