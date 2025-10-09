# tests/unit/test_models.py
from __future__ import annotations
import asyncio
import pytest
from models.project import Project
from models.base import Base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

@pytest.mark.asyncio
async def test_project_crud(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as s:
        p = Project(name="T", description="D", created_by="00000000-0000-0000-0000-000000000000")
        s.add(p)
        await s.commit()
        assert p.id is not None
