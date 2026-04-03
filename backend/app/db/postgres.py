"""PostgreSQL async client using SQLAlchemy + asyncpg."""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from app.config import get_settings

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


class PostgresClient:
    def __init__(self) -> None:
        self._engine = None
        self._session_factory = None

    async def connect(self) -> None:
        settings = get_settings()
        try:
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
            import sqlalchemy
            self._engine = create_async_engine(
                settings.database_url,
                pool_size=5,
                max_overflow=15,
                pool_pre_ping=True,
                echo=settings.environment == "development",
            )
            self._session_factory = async_sessionmaker(
                self._engine,
                expire_on_commit=False,
                class_=AsyncSession,
            )
            # Verify connection
            async with self._engine.connect() as conn:
                await conn.execute(sqlalchemy.text("SELECT 1"))
            logger.info("PostgreSQL connected")
        except Exception as exc:
            logger.warning("PostgreSQL connection failed (non-fatal in local mode): %s", exc)
            self._engine = None
            self._session_factory = None

    async def disconnect(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("PostgreSQL disconnected")

    async def ping(self) -> bool:
        if not self._engine:
            return False
        try:
            import sqlalchemy
            async with self._engine.connect() as conn:
                await conn.execute(sqlalchemy.text("SELECT 1"))
            return True
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        return self._engine is not None

    def get_session(self) -> Any:
        """Return a new async session. Caller must close it."""
        if not self._session_factory:
            raise RuntimeError("PostgreSQL is not connected. Ensure STORAGE_MODE=postgres and DB is running.")
        return self._session_factory()

    async def session_scope(self) -> AsyncGenerator[Any, None]:
        """Async context manager that yields a session and commits/rolls back."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


postgres_client = PostgresClient()


async def get_db() -> AsyncGenerator[Any, None]:
    """FastAPI dependency: yields an async DB session."""
    async with postgres_client.session_scope() as session:
        yield session
