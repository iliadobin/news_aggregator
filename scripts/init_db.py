#!/usr/bin/env python
"""
Database initialization script.

This script initializes the database schema.

Important:
- Prefer Alembic migrations for schema management.
- `create_all()` is kept only for special cases (e.g., quick local testing),
  but mixing `create_all()` and Alembic in the same database will lead to
  duplicate table errors.

Usage:
    python scripts/init_db.py              # Apply Alembic migrations (upgrade head)
    python scripts/init_db.py --drop       # Drop all tables and re-apply migrations (DANGER: deletes all data!)
    python scripts/init_db.py --drop --yes # Same as --drop, without interactive prompt
    python scripts/init_db.py --create-all # Create tables via SQLAlchemy metadata.create_all()
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

from app.config.settings import get_settings
from app.infra.db import close_database, get_db_manager
from app.infra.db.models import Base
from app.infra.logging.config import setup_logging

logger = logging.getLogger(__name__)


def _run_alembic_upgrade_head() -> None:
    """Run `alembic upgrade head` programmatically."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    command.upgrade(cfg, "head")


async def _drop_all_tables() -> None:
    """Drop all tables using SQLAlchemy metadata."""
    db_manager = get_db_manager()
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def main() -> None:
    """Initialize database."""
    parser = argparse.ArgumentParser(description="Initialize database")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all tables before applying migrations (WARNING: deletes all data!)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm dangerous operations without prompting (use with --drop).",
    )
    parser.add_argument(
        "--create-all",
        action="store_true",
        help="Use SQLAlchemy metadata.create_all() instead of Alembic migrations (not recommended).",
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging()

    # Get settings
    settings = get_settings()

    logger.info("Starting database initialization")
    logger.info(f"Database: {settings.database.database} at {settings.database.host}:{settings.database.port}")

    if args.drop:
        logger.warning("--drop flag specified: All existing tables will be dropped!")
        if not args.yes:
            if sys.stdin is not None and sys.stdin.isatty():
                response = input("Are you sure you want to drop all tables? (yes/no): ")
                if response.lower() != "yes":
                    logger.info("Aborted by user")
                    return
            else:
                raise RuntimeError(
                    "Non-interactive mode: pass --yes together with --drop to confirm."
                )

    try:
        if args.drop:
            logger.info("Dropping all database tables...")
            asyncio.run(_drop_all_tables())
            logger.info("All tables dropped")

        if args.create_all:
            logger.warning("Using create_all(); consider using Alembic instead")
            db_manager = get_db_manager()
            asyncio.run(db_manager.init_db(drop_existing=False))
        else:
            logger.info("Applying Alembic migrations (upgrade head)...")
            _run_alembic_upgrade_head()

        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        sys.exit(1)

    finally:
        asyncio.run(close_database())


if __name__ == "__main__":
    main()
