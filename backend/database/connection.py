# database/connection.py
from __future__ import annotations
from typing import AsyncIterator, Optional
import asyncio
import os
import time
import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy import event, text
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from sqlalchemy.exc import OperationalError, DBAPIError

logger = logging.getLogger(__name__)

# --- Settings ---
WRITE_DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/beth")
READ_DB_URL = os.getenv("READ_DATABASE_URL", WRITE_DB_URL)  # optional replica
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
ECHO_SQL = os.getenv("SQL_ECHO", "false").lower() == "true"

# --- Engines ---
write_engine: AsyncEngine = create_async_engine(
    WRITE_DB_URL,
    echo=ECHO_SQL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_pre_ping=True,
)
read_engine: AsyncEngine = create_async_engine(
    READ_DB_URL,
    echo=ECHO_SQL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_pre_ping=True,
)

WriteSession = async_sessionmaker(write_engine, expire_on_commit=False)
ReadSession = async_sessionmaker(read_engine, expire_on_commit=False)

# --- Query logging (duration) ---
@event.listens_for(write_engine.sync_engine, "before_cursor_execute")
@event.listens_for(read_engine.sync_engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # pragma: no cover
    context._query_start_time = time.time()

@event.listens_for(write_engine.sync_engine, "after_cursor_execute")
@event.listens_for(read_engine.sync_engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # pragma: no cover
    total = (time.time() - getattr(context, "_query_start_time", time.time())) * 1000.0
    logger.info("sql", extra={"ms": round(total, 2), "stmt": statement.split("\n")[0][:200]})


# --- Retry helpers ---
@retry(wait=wait_exponential(multiplier=0.5, min=1, max=8), stop=stop_after_attempt(5), reraise=True,
       retry=retry_if_exception_type((OperationalError, DBAPIError)))
async def _healthcheck_once(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def healthcheck() -> dict:
    try:
        await _healthcheck_once(write_engine)
        await _healthcheck_once(read_engine)
        return {"ok": True}
    except Exception as e:
        logger.exception("db-health-failed")
        return {"ok": False, "error": str(e)}


# --- Session management & transactions ---
@asynccontextmanager
async def get_session(readonly: bool = False) -> AsyncIterator[AsyncSession]:
    Session = ReadSession if readonly else WriteSession
    async with Session() as session:
        try:
            yield session
            if not readonly:
                await session.commit()
        except Exception:
            if not readonly:
                await session.rollback()
            raise


@asynccontextmanager
async def transaction() -> AsyncIterator[AsyncSession]:
    async with WriteSession() as session:
        async with session.begin():
            yield session
