# services/llm/explainer.py
from __future__ import annotations
from pydoc import text
from pyexpat import features
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import hashlib
import json
import logging
import os
import re
from functools import lru_cache
from xml.parsers.expat import model


try:
    import tiktoken # type: ignore
except Exception: # pragma: no cover
    tiktoken = None


logger = logging.getLogger(__name__)


# Optional Redis cache
_redis_url = os.getenv("REDIS_URL")
_redis = None
if _redis_url:
    try:
        import redis # type: ignore
        _redis = redis.Redis.from_url(_redis_url)
    except Exception: # pragma: no cover
        _redis = None


# Pricing table (USD / 1K tokens). Override via env like LLM_COST_gpt-4o=0.005_in,0.015_out
MODEL_COSTS = {
    "gpt-4o-mini": (0.0003, 0.001),
    "gpt-4o": (0.005, 0.015),
    "gpt-4.1-mini": (0.0005, 0.0015),
    "gpt-3.5-turbo": (0.0005, 0.0015),
}

def _load_model_cost(model: str) -> Tuple[float, float]:
    env = os.getenv(f"LLM_COST_{model}")
    if env and "," in env:
        a, b = env.split(",", 1)
    return float(a), float(b)
    return MODEL_COSTS.get(model, (0.001, 0.002))


@dataclass
class LLMUsage:
	input_tokens: int
	output_tokens: int
	input_cost: float
	output_cost: float
	model: str


@dataclass
class Explanation:
	text: str
	language: str
	confidence: float # 0..1
	usage: LLMUsage
	cached: bool
     
class LLMClient:
    """Minimal wrapper for OpenAI/Azure OpenAI with caching, token counting, and fallbacks."""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower() # 'openai' or 'azure'
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.fallback_model = os.getenv("LLM_FALLBACK_MODEL", "gpt-3.5-turbo")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "700"))
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("LLM API key not set; explainer will run in dry mode")
        # Deferred import to keep module importable without SDKs
        self._openai = None


    # ---------- Token & cost ----------
    def _count_tokens(self, text: str, model: Optional[str] = None) -> int:
        if not text:
            return 0
        if tiktoken is None:
            return max(1, len(text) // 4)
        try:
            enc = tiktoken.encoding_for_model(model or self.model)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))


    def _estimate_cost(self, in_tokens: int, out_tokens: int, model: Optional[str] = None) -> Tuple[float, float]:
        m = model or self.model
        cin, cout = _load_model_cost(m)
        return (in_tokens / 1000.0) * cin, (out_tokens / 1000.0) * cout


    # ---------- Cache ----------
    def _cache_key(self, payload: Dict[str, Any]) -> str:
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return f"llm:cache:{h}"

    def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        if _redis is not None:
            try:
                v = _redis.get(key)
                if v:
                    return json.loads(v)
            except Exception:
                pass
        return None


    def _set_cache(self, key: str, value: Dict[str, Any], ttl: int = 3600) -> None:
        if _redis is not None:
            try:
                _redis.setex(key, ttl, json.dumps(value))
            except Exception:
                pass

    # ---------- Safety filters ----------
    _REDACTIONS = [
        (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[redacted-email]"),
        (re.compile(r"\b\+?\d[\d\s\-]{7,}\b"), "[redacted-phone]"),
    ]


    def _sanitize(self, text: str) -> str:
        for rx, repl in self._REDACTIONS:
            text = rx.sub(repl, text)
        return text
    
    # ---------- Inference ----------
    def _ensure_sdk(self):
        if self._openai is not None:
            return self._openai
        if self.provider == "azure":
            from openai import AzureOpenAI # type: ignore
            self._openai = AzureOpenAI(api_key=self.api_key, api_version=self.azure_api_version, azure_endpoint=self.azure_endpoint)
        else:
            from openai import OpenAI # type: ignore
            self._openai = OpenAI(api_key=self.api_key)
        return self._openai


    def chat(self, messages: list[dict], model: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> Tuple[str, LLMUsage]:
        sdk = self._ensure_sdk()
        model = model or (self.azure_deployment if self.provider == "azure" else self.model)
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens


        # input token estimate
        in_tokens = self._count_tokens("\n".join(m.get("content", "") for m in messages), model=model)
        try:
            resp = sdk.chat.completions.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
            text = resp.choices[0].message.content or ""
            out_tokens = getattr(resp.usage, "completion_tokens", self._count_tokens(text, model))
        except Exception as e:
            logger.exception("LLM call failed on %s", model)
            raise e
        in_cost, out_cost = self._estimate_cost(in_tokens, out_tokens, model)
        usage = LLMUsage(input_tokens=in_tokens, output_tokens=out_tokens, input_cost=in_cost, output_cost=out_cost, model=model)
        return text, usage
    
class ExplainerService:
    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()
    def explain_anomaly(
        self,
        features: Dict[str, Any],
        anomaly_score: float,
        key_signals: list[str],
        language: str = "en",
        persona: str = "executive",
        cache_ttl: int = 3600,
    ) -> Explanation:
        from .prompts import system_prompt, few_shots
        payload = {
            "f": features,
            "s": round(float(anomaly_score), 4),
            "k": key_signals,
            "lang": language,
            "persona": persona,
            "v": "v1",
        }
        ckey = self.client._cache_key(payload)
        cached = self.client._get_cache(ckey)
        if cached:
            usage = LLMUsage(**cached["usage"]) if "usage" in cached else LLMUsage(0,0,0.0,0.0,self.client.model)
            return Explanation(text=cached["text"], language=language, confidence=cached.get("confidence", 0.75), usage=usage, cached=True)

        sys = system_prompt(locale=language, persona=persona)
        shots = few_shots(locale=language, persona=persona)
        user = (
            f"Explain this anomaly for a {persona} audience in {language}.\n"
            f"AnomalyScore: {anomaly_score:.3f} (0..1). KeySignals: {', '.join(key_signals)}.\n"
            f"Important features: {json.dumps(features)[:1200]}\n"
            "Output as 3-6 concise sentences; include a severity (low/med/high) and a 1-sentence recommendation."
        )
        messages = [
            {"role": "system", "content": sys},
            {"role": "user", "content": shots + "\n" + user},
        ]

        try:
            text, usage = self.client.chat(messages)
        except Exception:
            # fallback
            text = (
                f"Detected unusual behavior (score={anomaly_score:.2f}). Signals: {', '.join(key_signals)}. "
                "Recommend a quick review and validation of upstream data."
            )
            usage = LLMUsage(0, 0, 0.0, 0.0, self.client.fallback_model)

        text = self.client._sanitize(text)
        conf = self._confidence_from_text(text, anomaly_score, key_signals)
        out = {"text": text, "usage": usage.__dict__, "confidence": conf}
        self.client._set_cache(ckey, out, ttl=cache_ttl)
        return Explanation(text=text, language=language, confidence=conf, usage=usage, cached=False)
    
    @staticmethod
    def _confidence_from_text(text: str, score: float, signals: list[str]) -> float:
        # Heuristic: base on score + clarity metrics
        base = min(1.0, max(0.0, score))
        length = len(text)
        clarity_bonus = 0.05 if 280 <= length <= 1200 else 0.0
        signal_bonus = min(0.1, len(signals) * 0.02)
        hedges = len(re.findall(r"\b(might|may|possibly|unclear|unknown)\b", text.lower()))
        hedge_penalty = min(0.15, hedges * 0.03)
        return float(round(max(0.1, base + clarity_bonus + signal_bonus - hedge_penalty), 2))