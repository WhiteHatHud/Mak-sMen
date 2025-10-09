
# tests/fixtures/azure_ml.py
from __future__ import annotations
from types import SimpleNamespace

class FakeMLClient:
    def __init__(self):
        self.ok = True
    def score(self, endpoint: str, payload: dict):
        return {"predictions": [0.01] * len(payload.get("rows", []))}


def patch_azure_ml(monkeypatch):
    import services.azure_ml.client as c
    fake = FakeMLClient()
    monkeypatch.setattr(c, "get_ml_client", lambda: fake)
    return fake

















