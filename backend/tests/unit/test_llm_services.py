# tests/unit/test_llm_services.py
from __future__ import annotations
from services.llm.explainer import ExplainerService


def test_explainer_basic(monkeypatch):
    from tests.fixtures.llm import patch_llm
    patch_llm(monkeypatch)
    s = ExplainerService()
    out = s.explain_anomaly({"amount": 1200}, 0.9, ["spike", "rare category"])
    assert out.text and 0 <= out.confidence <= 1
