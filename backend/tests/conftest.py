
# tests/conftest.py
from __future__ import annotations
import os
import io
import json
import asyncio
import tempfile
from typing import AsyncIterator, Iterator

import pytest
import fakeredis.aioredis  # type: ignore
from starlette.testclient import TestClient
from httpx import AsyncClient

# Ensure test settings
os.environ.setdefault("ENV", "test")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")  # not actually used; we patch with fakeredis
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("FILE_STORAGE_DIR", tempfile.mkdtemp(prefix="beth_test_storage_"))

# Patch utils.redis_client.redis to fakeredis where used by middlewares/workers
@pytest.fixture(autouse=True)
async def fake_redis(monkeypatch):
    r = await fakeredis.aioredis.create_redis_pool()
    try:
        # Some modules import as `redis` attr, others `rds`/`wredis`; unify via monkeypatch targets actually used
        import utils.redis_client as rc  # type: ignore
        monkeypatch.setattr(rc, "redis", r, raising=False)
        yield r
    finally:
        r.close()
        await r.wait_closed()


# FastAPI app fixture (imports your assembled app)
@pytest.fixture(scope="session")
def app() -> "FastAPI":
    from fastapi import FastAPI
    from api.middleware.auth import add_auth_logging
    from api.middleware.cors import add_cors
    from api.middleware.rate_limiter import add_rate_limiter
    from api.routes.projects import router as projects_router
    from api.routes.files import router as files_router
    from api.routes.analysis import router as analysis_router
    from api.routes.reports import router as reports_router
    from api.routes.webhooks import router as webhooks_router

    app = FastAPI()
    add_auth_logging(app)
    add_cors(app)
    add_rate_limiter(app)

    app.include_router(projects_router)
    app.include_router(files_router)
    app.include_router(analysis_router)
    app.include_router(reports_router)
    app.include_router(webhooks_router)
    return app


# Auth header helper (bypass real JWT by monkeypatching dependency in tests as needed)
@pytest.fixture
def auth_headers(monkeypatch):
    from api.middleware.auth import get_current_user, AuthedUser

    async def fake_user(*args, **kwargs):
        return AuthedUser(id=1, email="user@test", role="admin")

    monkeypatch.setattr("api.middleware.auth.get_current_user", fake_user)
    return {"Authorization": "Bearer test"}


@pytest.fixture
def client(app, auth_headers) -> Iterator[TestClient]:
    with TestClient(app) as c:
        c.headers.update(auth_headers)
        yield c


@pytest.fixture
async def aclient(app, auth_headers) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=app, base_url="http://test") as c:
        c.headers.update(auth_headers)
        yield c