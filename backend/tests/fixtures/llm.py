# tests/fixtures/llm.py
from __future__ import annotations

class FakeLLM:
    def chat(self, messages, **kwargs):
        class U:  # usage stub
            completion_tokens = 10
        return ("This is a test summary.", SimpleNamespace(completion_tokens=10))


def patch_llm(monkeypatch):
    import services.llm.explainer as e
    client = e.LLMClient()
    client.chat = lambda messages, **kw: ("Plain-English explanation.", e.LLMUsage(10, 10, 0.0, 0.0, client.model))
    monkeypatch.setattr(e, "LLMClient", lambda: client)
    return client