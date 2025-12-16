"""
Database connection and session management.

This module provides:
- Async SQLAlchemy engine and session factory
- Database initialization and table creation
- Session context managers and dependencies
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config.settings import DatabaseSettings, get_settings
from app.infra.db.models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and sessions.

    Provides async SQLAlchemy engine and session factory.
    """

    def __init__(self, db_settings: Optional[DatabaseSettings] = None):
        """
        Initialize database manager.

        Args:
            db_settings: Database settings. If None, loads from global settings.
        """
        if db_settings is None:
            db_settings = get_settings().database

        self.settings = db_settings
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def _create_engine(self) -> AsyncEngine:
        """
        Create async SQLAlchemy engine.

        Returns:
            AsyncEngine: SQLAlchemy async engine
        """
        # NOTE:
        # - For async engines, SQLAlchemy uses an async-adapted pool by default.
        # - Explicitly setting a synchronous pool (e.g. QueuePool) will crash.
        # We only force NullPool for tests to avoid connection reuse issues.

        is_test_db = self.settings.database == "test" or "test" in self.settings.database

        engine_kwargs: dict = {
            "echo": self.settings.echo,
            "connect_args": {"server_settings": {"application_name": "news_aggregator"}},
        }

        if is_test_db:
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_size"] = self.settings.pool_size
            engine_kwargs["max_overflow"] = self.settings.max_overflow

        engine = create_async_engine(self.settings.dsn, **engine_kwargs)

        logger.info(
            "Database engine created",
            extra={
                "host": self.settings.host,
                "port": self.settings.port,
                "database": self.settings.database,
            },
        )

        return engine

    @property
    def engine(self) -> AsyncEngine:
        """
        Get or create async engine.

        Returns:
            AsyncEngine: SQLAlchemy async engine
        """
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """
        Get or create session factory.

        Returns:
            async_sessionmaker: Session factory
        """
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    async def init_db(self, drop_existing: bool = False) -> None:
        """
        Initialize database tables.

        Args:
            drop_existing: If True, drops all existing tables before creating new ones.
                          WARNING: This will delete all data!
        """
        async with self.engine.begin() as conn:
            if drop_existing:
                logger.warning("Dropping all existing database tables")
                await conn.run_sync(Base.metadata.drop_all)

            logger.info("Creating database tables")
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialization completed")

    async def close(self) -> None:
        """Close database connections and dispose of the engine."""
        if self._engine is not None:
            await self._engine.dispose()
            logger.info("Database engine disposed")
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for database sessions.

        Yields:
            AsyncSession: SQLAlchemy async session

        Example:
            async with db_manager.session() as session:
                result = await session.execute(query)
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Dependency for FastAPI/aiogram to get database session.

        Yields:
            AsyncSession: SQLAlchemy async session

        Example:
            @router.get("/users")
            async def get_users(session: AsyncSession = Depends(db_manager.get_session)):
                ...
        """
        async with self.session() as session:
            yield session


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get or create global database manager instance.

    Returns:
        DatabaseManager: Global database manager
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def init_database(drop_existing: bool = False) -> None:
    """
    Initialize database (create tables).

    Args:
        drop_existing: If True, drops all existing tables before creating new ones.

    Example:
        # In your application startup
        await init_database()
    """
    db_manager = get_db_manager()
    await db_manager.init_db(drop_existing=drop_existing)


async def close_database() -> None:
    """
    Close database connections.

    Example:
        # In your application shutdown
        await close_database()
    """
    global _db_manager
    if _db_manager is not None:
        await _db_manager.close()
        _db_manager = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session (for use as dependency).

    Yields:
        AsyncSession: SQLAlchemy async session

    Example:
        async def some_handler(session: AsyncSession = Depends(get_session)):
            ...
    """
    db_manager = get_db_manager()
    async with db_manager.get_session() as session:
        yield session


# Context manager for standalone usage
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager to get a database session for standalone usage.

    Yields:
        AsyncSession: SQLAlchemy async session

    Example:
        async with get_db_session() as session:
            user = await session.get(User, 1)
    """
    db_manager = get_db_manager()
    async with db_manager.session() as session:
        yield session
