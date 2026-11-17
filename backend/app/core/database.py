"""Async SQLAlchemy engine and session factory.

Supports:
  - SQLite (default local demo)
  - PostgreSQL / Supabase (set DATABASE_URL to postgresql+asyncpg://...)

Embeddings are stored as TEXT (JSON array) in both backends.
Cosine similarity is computed in Python for the demo scale (~200–300 chunks).
For production PostgreSQL, set PGVECTOR_ENABLED=true and add the pgvector
extension; the retriever service will use a native ANN query instead.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Shared declarative base for all models."""
    pass


def _make_engine():
    kwargs: dict = {}
    if settings.is_sqlite:
        # SQLite needs check_same_thread disabled in async context
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["echo"] = settings.app_env == "development"
    else:
        # PostgreSQL / asyncpg
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        kwargs["echo"] = settings.app_env == "development"
    return create_async_engine(settings.database_url, **kwargs)


engine = _make_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all tables. Called once at application startup."""
    # Import all models so Base.metadata knows about them
    import app.models.user          # noqa: F401
    import app.models.document      # noqa: F401
    import app.models.conversation  # noqa: F401
    import app.models.resolution    # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Alias used by app/main.py
init_db = create_tables
