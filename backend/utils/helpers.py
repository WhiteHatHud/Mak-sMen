# utils/helpers.py
from __future__ import annotations
from typing import Any, Dict, Callable, Optional, Iterable, Tuple
from dataclasses import dataclass
import os
import json
import time
import uuid
import base64
import math
from datetime import datetime, timezone, timedelta
from functools import lru_cache, wraps

from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

# ------------------------
# Pagination
# ------------------------
@dataclass
class Page:
    items: list
    total: int
    page: int
    size: int


def to_pagination(items: list, total: int, page: int, size: int) -> Dict[str, Any]:
    return {"items": items, "total": total, "page": page, "size": size}


# ------------------------
# Datetime utilities
# ------------------------
ISO_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(ISO_FMT)


def from_iso(s: str) -> datetime:
    # Accept flexible ISO
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ------------------------
# Retry decorators (thin over tenacity)
# ------------------------
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


def retryable(max_attempts: int = 5, min_wait: float = 0.5, max_wait: float = 8.0, exceptions: Tuple[type, ...] = (Exception,)):
    return retry(reraise=True, stop=stop_after_attempt(max_attempts), wait=wait_exponential(multiplier=min_wait, max=max_wait), retry=retry_if_exception_type(exceptions))


# ------------------------
# Cache helpers
# ------------------------
class TTLCache:
    def __init__(self, ttl_seconds: int = 300, maxsize: int = 1024):
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item:
            return None
        ts, val = item
        if time.time() - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return val

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self.maxsize:
            # naive eviction: remove oldest
            oldest = min(self._store.items(), key=lambda kv: kv[1][0])[0]
            self._store.pop(oldest, None)
        self._store[key] = (time.time(), value)


# ------------------------
# Encryption / Decryption (AES-GCM)
# ------------------------
ENC_KEY = os.getenv("APP_ENC_KEY")


def _get_key() -> bytes:
    key_b64 = ENC_KEY or base64.b64encode(os.urandom(32)).decode()
    raw = base64.b64decode(key_b64)
    if len(raw) not in (16, 24, 32):
        # pad / trim to 32
        raw = (raw + b"0" * 32)[:32]
    return raw


def encrypt(plaintext: bytes, aad: Optional[bytes] = None) -> bytes:
    key = _get_key()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext, aad)
    return nonce + ct  # prepend nonce


def decrypt(blob: bytes, aad: Optional[bytes] = None) -> bytes:
    key = _get_key()
    aes = AESGCM(key)
    nonce, ct = blob[:12], blob[12:]
    return aes.decrypt(nonce, ct, aad)


def encrypt_str(s: str) -> str:
    return base64.b64encode(encrypt(s.encode("utf-8"))).decode()


def decrypt_str(s: str) -> str:
    return decrypt(base64.b64decode(s)).decode()


# ------------------------
# Serialization helpers
# ------------------------
class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        try:
            import decimal
            if isinstance(o, decimal.Decimal):
                return float(o)
        except Exception:
            pass
        if isinstance(o, (datetime,)):
            return to_iso(o)
        if hasattr(o, "dict"):
            return o.dict()  # pydantic models
        return json.JSONEncoder.default(self, o)


def to_json(data: Any) -> str:
    return json.dumps(data, cls=EnhancedJSONEncoder, ensure_ascii=False)


def from_json(s: str) -> Any:
    return json.loads(s)


# ------------------------
# Validation utilities
# ------------------------
import re
UUID_RX = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")


def is_uuid(s: str) -> bool:
    return bool(UUID_RX.match(s))


def ensure_range(x: float, lo: float, hi: float, name: str = "value") -> float:
    if not (lo <= x <= hi):
        raise ValueError(f"{name} out of range [{lo}, {hi}]")
    return x


# ------------------------
# Networking helpers
# ------------------------
from fastapi import Request

def get_client_ip(request: Request) -> str:
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or request.client.host
    return ip


# ------------------------
# Misc decorators
# ------------------------

def once(fn: Callable):
    """Ensure a function is called only once (per process)."""
    called = False
    result: Any = None
    @wraps(fn)
    def wrapper(*args, **kwargs):
        nonlocal called, result
        if not called:
            result = fn(*args, **kwargs)
            called = True
        return result
    return wrapper
