

# utils/metrics.py
from __future__ import annotations
from typing import Optional, Dict, Any, Callable
import os
import time

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, push_to_gateway

# Prometheus registry (default global is fine for multiprocess-disabled)
REGISTRY = CollectorRegistry(auto_describe=True)

# Core metrics
HTTP_LATENCY = Histogram("http_latency_ms", "HTTP request latency (ms)", ["path", "method"], registry=REGISTRY, buckets=(5,10,25,50,100,250,500,1000,2000,5000))
WORKER_LATENCY = Histogram("worker_latency_ms", "Worker task latency (ms)", ["task", "label"], registry=REGISTRY, buckets=(10,50,100,250,500,1000,2000,5000,15000,60000))
EVENTS = Counter("events_total", "Generic events", ["type"], registry=REGISTRY)
BUSINESS = Counter("business_events_total", "Business domain events", ["name"], registry=REGISTRY)
SLA_ERRORS = Counter("sla_breaches_total", "SLA breach counter", ["metric"], registry=REGISTRY)
COST_TOKENS = Counter("llm_tokens_total", "LLM tokens used", ["model", "direction"], registry=REGISTRY)
COST_USD = Counter("llm_cost_usd_total", "LLM estimated cost (USD)", ["model"], registry=REGISTRY)
CACHE_HITS = Counter("cache_hits_total", "Cache hits", ["name"], registry=REGISTRY)
CACHE_MISSES = Counter("cache_misses_total", "Cache misses", ["name"], registry=REGISTRY)
GAUGE_ACTIVE_ANALYSES = Gauge("active_analyses", "In-flight analyses", registry=REGISTRY)

PUSHGATEWAY = os.getenv("PROM_PUSHGATEWAY")
JOB_NAME = os.getenv("PROM_JOB_NAME", "beth_backend")


def observe_latency_ms(kind: str, a: str, b: str, ms: float) -> None:
    if kind == "http_server":
        HTTP_LATENCY.labels(path=a, method=b).observe(ms)
    else:
        WORKER_LATENCY.labels(task=a, label=b).observe(ms)


def record_api_latency(fn: Callable):
    """Decorator for FastAPI handlers to record latency (works on sync/async)."""
    if hasattr(fn, "__call__"):
        import inspect
        if inspect.iscoroutinefunction(fn):
            async def _async(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return await fn(*args, **kwargs)
                finally:
                    ms = (time.perf_counter() - start) * 1000.0
                    # Guess path/method from FastAPI injection is non-trivial; record under function name
                    HTTP_LATENCY.labels(path=getattr(fn, "__name__", "unknown"), method="async").observe(ms)
            return _async
        else:
            def _sync(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return fn(*args, **kwargs)
                finally:
                    ms = (time.perf_counter() - start) * 1000.0
                    HTTP_LATENCY.labels(path=getattr(fn, "__name__", "unknown"), method="sync").observe(ms)
            return _sync
    return fn


def push_metrics(job: Optional[str] = None) -> None:
    if not PUSHGATEWAY:
        return
    push_to_gateway(PUSHGATEWAY, job=job or JOB_NAME, registry=REGISTRY)


def track_business(name: str, n: int = 1):
    BUSINESS.labels(name=name).inc(n)


def track_sla(metric: str, ok: bool, threshold_ms: float, actual_ms: float) -> None:
    if actual_ms > threshold_ms:
        SLA_ERRORS.labels(metric=metric).inc()


def track_llm_cost(model: str, in_tokens: int, out_tokens: int, in_cost: float, out_cost: float) -> None:
    COST_TOKENS.labels(model=model, direction="in").inc(in_tokens)
    COST_TOKENS.labels(model=model, direction="out").inc(out_tokens)
    COST_USD.labels(model=model).inc(in_cost + out_cost)