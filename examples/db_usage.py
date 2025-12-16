#!/usr/bin/env python
"""
Database usage examples.

This file demonstrates how to use the database repositories.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infra.db import (
    FilterMode,
    FilterRepository,
    ForwardedMessageRepository,
    ForwardedStatus,
    MatchType,
    MessageRepository,
    SourceRepository,
    SourceType,
    SubscriptionRepository,
    UserRepository,
    FilterMatchRepository,
    get_db_session,
    init_database,
)
from app.infra.logging.config import setup_logging


async def example_user_operations():
    """Example of user operations."""
    print("\n=== User Operations ===")

    async with get_db_session() as session:
        user_repo = UserRepository(session)

        # Create or get user
        user, created = await user_repo.get_or_create_by_telegram_id(
            telegram_id=123456789,
            username="john_doe",
            first_name="John",
            last_name="Doe",
        )

        print(f"User: {user.username} (created: {created})")
        print(f"  ID: {user.id}")
        print(f"  Telegram ID: {user.telegram_id}")
        print(f"  Active: {user.is_active}")

        # Update preferences
        await user_repo.update_preferences(
            user.id, {"language": "ru", "timezone": "Europe/Moscow", "notifications": True}
        )
        print(f"  Preferences updated: {user.preferences}")

        return user


async def example_source_operations():
    """Example of source operations."""
    print("\n=== Source Operations ===")

    async with get_db_session() as session:
        source_repo = SourceRepository(session)

        # Create or get source
        source, created = await source_repo.get_or_create_by_telegram_chat_id(
            telegram_chat_id=-1001234567890,
            title="Tech News Channel",
            username="tech_news",
            type=SourceType.CHANNEL,
        )

        print(f"Source: {source.title} (created: {created})")
        print(f"  ID: {source.id}")
        print(f"  Telegram Chat ID: {source.telegram_chat_id}")
        print(f"  Type: {source.type}")
        print(f"  Active: {source.is_active}")

        return source


async def example_subscription_operations(user_id: int, source_id: int):
    """Example of subscription operations."""
    print("\n=== Subscription Operations ===")

    async with get_db_session() as session:
        sub_repo = SubscriptionRepository(session)

        # Create subscription
        subscription = await sub_repo.create_subscription(
            user_id=user_id, source_id=source_id, priority=10
        )

        print(f"Subscription created:")
        print(f"  ID: {subscription.id}")
        print(f"  User ID: {subscription.user_id}")
        print(f"  Source ID: {subscription.source_id}")
        print(f"  Priority: {subscription.priority}")

        # Get user subscriptions
        user_subs = await sub_repo.get_user_subscriptions(user_id=user_id)
        print(f"\nUser has {len(user_subs)} active subscription(s)")

        return subscription


async def example_filter_operations(user_id: int):
    """Example of filter operations."""
    print("\n=== Filter Operations ===")

    async with get_db_session() as session:
        filter_repo = FilterRepository(session)

        # Create filter
        filter_obj = await filter_repo.create(
            user_id=user_id,
            name="Python News",
            mode=FilterMode.COMBINED,
            keywords=["python", "django", "fastapi", "asyncio"],
            topics=["Python programming", "web development", "async programming"],
            semantic_threshold=0.75,
        )

        print(f"Filter created: {filter_obj.name}")
        print(f"  ID: {filter_obj.id}")
        print(f"  Mode: {filter_obj.mode}")
        print(f"  Keywords: {filter_obj.keywords}")
        print(f"  Topics: {filter_obj.topics}")
        print(f"  Semantic threshold: {filter_obj.semantic_threshold}")

        # Update keywords
        await filter_repo.update_keywords(
            filter_obj.id, ["python", "django", "fastapi", "asyncio", "pydantic"]
        )
        print(f"  Keywords updated")

        return filter_obj


async def example_message_operations(source_id: int):
    """Example of message operations."""
    print("\n=== Message Operations ===")

    async with get_db_session() as session:
        msg_repo = MessageRepository(session)

        # Create message
        message, created = await msg_repo.get_or_create_message(
            telegram_message_id=12345,
            chat_id=-1001234567890,
            source_id=source_id,
            text="Python 3.13 has been released with exciting new features!",
            date=datetime.utcnow(),
            meta={"has_photo": False, "has_video": False, "language": "en"},
        )

        print(f"Message: (created: {created})")
        print(f"  ID: {message.id}")
        print(f"  Telegram Message ID: {message.telegram_message_id}")
        print(f"  Text: {message.text[:50]}...")
        print(f"  Processed: {message.is_processed}")

        # Get unprocessed messages
        unprocessed = await msg_repo.get_unprocessed_messages(limit=10)
        print(f"\nUnprocessed messages: {len(unprocessed)}")

        return message


async def example_filter_match_operations(message_id: int, filter_id: int):
    """Example of filter match operations."""
    print("\n=== Filter Match Operations ===")

    async with get_db_session() as session:
        match_repo = FilterMatchRepository(session)

        # Create filter match
        match, created = await match_repo.get_or_create_match(
            message_id=message_id,
            filter_id=filter_id,
            match_type=MatchType.COMBINED,
            score=0.85,
            details={
                "matched_keywords": ["python"],
                "keyword_count": 1,
                "semantic_score": 0.85,
                "matched_topic": "Python programming",
            },
        )

        print(f"Filter match: (created: {created})")
        print(f"  ID: {match.id}")
        print(f"  Message ID: {match.message_id}")
        print(f"  Filter ID: {match.filter_id}")
        print(f"  Type: {match.match_type}")
        print(f"  Score: {match.score}")
        print(f"  Details: {match.details}")

        # Get message matches
        message_matches = await match_repo.get_message_matches(message_id)
        print(f"\nMessage has {len(message_matches)} match(es)")

        return match


async def example_forwarded_message_operations(user_id: int, filter_id: int, message_id: int):
    """Example of forwarded message operations."""
    print("\n=== Forwarded Message Operations ===")

    async with get_db_session() as session:
        fwd_repo = ForwardedMessageRepository(session)

        # Create forwarded message record
        forwarded = await fwd_repo.create(
            user_id=user_id,
            filter_id=filter_id,
            message_id=message_id,
            target_chat_id=123456789,
            status=ForwardedStatus.PENDING,
        )

        print(f"Forwarded message record created:")
        print(f"  ID: {forwarded.id}")
        print(f"  User ID: {forwarded.user_id}")
        print(f"  Message ID: {forwarded.message_id}")
        print(f"  Target Chat ID: {forwarded.target_chat_id}")
        print(f"  Status: {forwarded.status}")

        # Mark as sent
        await fwd_repo.mark_as_sent(forwarded.id, forwarded_telegram_message_id=67890)
        print(f"  Status updated to SENT")

        # Get pending forwards
        pending = await fwd_repo.get_pending_forwards(limit=10)
        print(f"\nPending forwards: {len(pending)}")

        return forwarded


async def main():
    """Run all examples."""
    # Setup logging
    setup_logging()

    print("=== Database Usage Examples ===")
    print("\nInitializing database...")

    # Initialize database (create tables if they don't exist)
    await init_database()

    try:
        # Run examples
        user = await example_user_operations()
        source = await example_source_operations()
        subscription = await example_subscription_operations(user.id, source.id)
        filter_obj = await example_filter_operations(user.id)
        message = await example_message_operations(source.id)
        match = await example_filter_match_operations(message.id, filter_obj.id)
        forwarded = await example_forwarded_message_operations(user.id, filter_obj.id, message.id)

        print("\n=== All Examples Completed Successfully ===")

    except Exception as e:
        print(f"\n!!! Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
