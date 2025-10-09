# workers/webhook_worker.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os
import hmac
import hashlib
import time
import json
import logging


from celery import Celery
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

# Import the celery app from analysis_worker
from workers.analysis_worker import celery_app

# Reuse Celery instance
webhook_app = celery_app
logger = logging.getLogger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    import redis as redis_sync # type: ignore
    wredis = redis_sync.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    wredis = None


CB_FAIL_WINDOW = int(os.getenv("WEBHOOK_CB_WINDOW", "300")) # seconds
CB_THRESHOLD = int(os.getenv("WEBHOOK_CB_THRESHOLD", "5")) # open after N failures
CB_COOLDOWN = int(os.getenv("WEBHOOK_CB_COOLDOWN", "300")) # seconds


DLQ_KEY = os.getenv("WEBHOOK_DLQ_KEY", "webhooks:dlq")

def _cb_key(url: str) -> str:
    return f"wh:cb:{hashlib.sha1(url.encode()).hexdigest()}"


def _metrics_key(url: str) -> str:
    return f"wh:metrics:{hashlib.sha1(url.encode()).hexdigest()}"


def _increment_failure(url: str) -> None:
    if not wredis:
        return
    k = _cb_key(url)
    pipe = wredis.pipeline()
    pipe.incr(k)
    pipe.expire(k, CB_FAIL_WINDOW)
    pipe.execute()


def _should_open(url: str) -> bool:
    if not wredis:
        return False
    k = _cb_key(url)
    try:
        v = int(wredis.get(k) or 0)
        return v >= CB_THRESHOLD
    except Exception:
        return False

def _open_cb(url: str) -> None:
    if not wredis:
        return
    k = _cb_key(url) + ":open"
    wredis.setex(k, CB_COOLDOWN, "1")


def _cb_open(url: str) -> bool:
    if not wredis:
        return False
    return bool(wredis.get(_cb_key(url) + ":open"))


def _record_metric(url: str, ok: bool, ms: float) -> None:
    if not wredis:
        return
    key = _metrics_key(url)
    data = {"ts": int(time.time()), "ok": ok, "ms": ms}
    try:
        wredis.lpush(key, json.dumps(data))
        wredis.ltrim(key, 0, 999)
    except Exception:
        pass

def _sign(secret: str, body: bytes, ts: int) -> str:
    mac = hmac.new(secret.encode(), msg=f"{ts}.".encode() + body, digestmod=hashlib.sha256)
    return "sha256=" + mac.hexdigest()




class WebhookError(Exception):
    pass




@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=0.5, min=1, max=10), retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)))
def _deliver(url: str, body: bytes, headers: Dict[str, str]) -> httpx.Response:
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, content=body, headers=headers)
        resp.raise_for_status()
        return resp

@webhook_app.task(bind=True, name="trigger_webhook", acks_late=True)
def trigger_webhook(self, *, url: str, event: str, payload: Dict[str, Any], secret: Optional[str] = None, batch: bool = False) -> Dict[str, Any]:
    if _cb_open(url):
        # Circuit open: enqueue to DLQ directly
        if wredis:
            wredis.lpush(DLQ_KEY, json.dumps({"url": url, "event": event, "payload": payload, "reason": "circuit_open"}))
        return {"skipped": True, "reason": "circuit_open"}

    ts = int(time.time())
    body = json.dumps({"event": event, "payload": payload, "timestamp": ts}).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Event": event,
        "X-Timestamp": str(ts),
    }
    if secret:
        headers["X-Signature"] = _sign(secret, body, ts)

    start = time.time()
    try:
        resp = _deliver(url, body, headers)
        ms = (time.time() - start) * 1000.0
        _record_metric(url, True, ms)
        return {"status": resp.status_code, "latency_ms": ms}
    except Exception as e:
        ms = (time.time() - start) * 1000.0
        _record_metric(url, False, ms)
        _increment_failure(url)
        if _should_open(url):
            _open_cb(url)
        # DLQ after retries handled by tenacity; if still failing, push
        if wredis:
            wredis.lpush(DLQ_KEY, json.dumps({"url": url, "event": event, "payload": payload, "error": str(e)}))
        raise



@webhook_app.task(name="batch_webhooks", acks_late=True)
def batch_webhooks(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for it in items:
        try:
            r = trigger_webhook.apply_async(kwargs=it)
            results.append({"enqueued": True, "task_id": r.id})
        except Exception as e:
            results.append({"enqueued": False, "error": str(e)})
    return results
