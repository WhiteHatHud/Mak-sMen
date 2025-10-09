# tests/integration/test_analysis_worker.py
from __future__ import annotations
import pytest
from workers.analysis_worker import celery_app, start_analysis, get_cached_results


def test_start_analysis_eager(monkeypatch):
    # run Celery in eager mode for test
    celery_app.conf.task_always_eager = True
    result = start_analysis.apply_async(kwargs={"user_id":1, "project_id":1, "file_ids":[], "ai_endpoint":"local", "enable_llm_explain":False}).get()
    assert "analysis_id" in result