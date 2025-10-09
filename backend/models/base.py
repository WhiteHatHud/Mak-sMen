# models/base.py
from __future__ import annotations
from typing import AsyncIterator
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy import types as satypes


# ---------- Engine / Session ----------
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/beth")
engine = create_async_engine(DB_URL, echo=os.getenv("SQL_ECHO", "false").lower() == "true")
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


# ---------- Types ----------
class GUID(satypes.TypeDecorator):
    """Platform-independent GUID/UUID type.
    Uses PostgreSQL UUID if available, otherwise stores as CHAR(36).
    """
    impl = satypes.CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pg.UUID(as_uuid=True))
        return dialect.type_descriptor(satypes.CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def JSONType():  # JSONB on PG, JSON elsewhere
    return pg.JSONB() if engine.url.get_dialect().name == 'postgresql' else satypes.JSON()


def now_utc():
    return datetime.now(timezone.utc)


# ---------- Declarative Base & Mixins ----------
class Base(DeclarativeBase):
    metadata = MetaData()

    @declared_attr.directive
    def __tablename__(cls) -> str:  # type: ignore[override]
        return cls.__name__.lower()


class TimestampMixin:
    created_at = pg.TIMESTAMP(timezone=True).as_generic(  # type: ignore[attr-defined]
        timezone=True
    ).with_variant(pg.TIMESTAMP(timezone=True), 'postgresql')  # type: ignore
    updated_at = pg.TIMESTAMP(timezone=True).as_generic(  # type: ignore[attr-defined]
        timezone=True
    ).with_variant(pg.TIMESTAMP(timezone=True), 'postgresql')  # type: ignore