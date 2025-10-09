# tests/integration/test_report_worker.py
from __future__ import annotations
from workers.report_worker import report_app, generate_report_task


def test_generate_report_eager(monkeypatch):
    report_app.conf.task_always_eager = True
    # Seed cache as if analysis completed
    from workers.analysis_worker import cache_results
    cache_results("A1", {"summary": {"analysis_id": "A1"}, "anomalies": []})
    out = generate_report_task.apply_async(kwargs={"user_id":1, "analysis_id":"A1", "format":"json"}).get()
    assert out["bundle"].endswith(".zip")

