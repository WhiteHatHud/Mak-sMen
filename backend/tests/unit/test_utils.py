
# tests/unit/test_utils.py
from __future__ import annotations
import base64
from utils.helpers import encrypt_str, decrypt_str, TTLCache, ensure_range, is_uuid


def test_encrypt_roundtrip():
    s = "hello"
    enc = encrypt_str(s)
    dec = decrypt_str(enc)
    assert dec == s


def test_ttlcache_basic():
    c = TTLCache(ttl_seconds=1)
    c.set("a", 1)
    assert c.get("a") == 1


def test_ensure_range():
    assert ensure_range(0.5, 0, 1) == 0.5


def test_is_uuid_false():
    assert not is_uuid("nope")
