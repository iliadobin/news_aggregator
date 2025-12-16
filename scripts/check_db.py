#!/usr/bin/env python
"""
Database connection check script.

This script verifies that the database connection is working correctly
and displays information about the database schema.

Usage:
    python scripts/check_db.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text

from app.config.settings import get_settings
from app.infra.db import get_db_manager, close_database
from app.infra.logging.config import setup_logging

logger = logging.getLogger(__name__)


async def check_connection():
    """Check database connection."""
    db_manager = get_db_manager()

    try:
        async with db_manager.session() as session:
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"Database connection successful!")
            logger.info(f"PostgreSQL version: {version}")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


async def list_tables():
    """List all tables in the database."""
    db_manager = get_db_manager()

    try:
        async with db_manager.engine.connect() as conn:
            # Get inspector
            def _get_tables(sync_conn):
                inspector = inspect(sync_conn)
                return inspector.get_table_names()

            tables = await conn.run_sync(_get_tables)

            if tables:
                logger.info(f"Found {len(tables)} tables:")
                for table in sorted(tables):
                    logger.info(f"  - {table}")
            else:
                logger.warning("No tables found in database")
                logger.info("Run 'alembic upgrade head' or 'python scripts/init_db.py' to create tables")

            return tables

    except Exception as e:
        logger.error(f"Failed to list tables: {e}")
        return []


async def get_table_info(table_name: str):
    """Get information about a specific table."""
    db_manager = get_db_manager()

    try:
        async with db_manager.engine.connect() as conn:

            def _get_columns(sync_conn):
                inspector = inspect(sync_conn)
                return inspector.get_columns(table_name)

            columns = await conn.run_sync(_get_columns)

            logger.info(f"\nTable: {table_name}")
            logger.info("Columns:")
            for col in columns:
                nullable = "NULL" if col["nullable"] else "NOT NULL"
                col_type = str(col["type"])
                logger.info(f"  - {col['name']}: {col_type} {nullable}")

    except Exception as e:
        logger.error(f"Failed to get table info: {e}")


async def main():
    """Main function."""
    # Setup logging
    setup_logging()

    # Get settings
    settings = get_settings()

    logger.info("=== Database Connection Check ===")
    logger.info(f"Host: {settings.database.host}")
    logger.info(f"Port: {settings.database.port}")
    logger.info(f"Database: {settings.database.database}")
    logger.info(f"User: {settings.database.user}")
    logger.info("")

    # Check connection
    if not await check_connection():
        logger.error("Database connection failed!")
        sys.exit(1)

    logger.info("")

    # List tables
    tables = await list_tables()

    # Get info about main tables
    if tables:
        logger.info("")
        logger.info("=== Table Details ===")
        main_tables = ["users", "sources", "subscriptions", "filters", "messages"]
        for table in main_tables:
            if table in tables:
                await get_table_info(table)

    # Close database
    await close_database()

    logger.info("")
    logger.info("=== Check Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
