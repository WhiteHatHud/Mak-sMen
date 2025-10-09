# tests/perf/test_load_smoke.py
from __future__ import annotations
import asyncio
import pytest

@pytest.mark.asyncio
async def test_parallel_status_requests(aclient):
    # Smoke load: 50 parallel requests to a light endpoint
    N = 50
    async def one():
        return await aclient.get("/api/projects")
    rs = await asyncio.gather(*[one() for _ in range(N)])
    assert all(r.status_code == 200 for r in rs)
