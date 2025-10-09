"""Sliding-window rate limiter using Redis.
- Per-endpoint quotas (e.g., reads 100/min; analysis 10/min)
- User-based & IP-based keys
- Admin bypass
- 429 with Retry-After
- Request-ID, logging, perf metrics
"""
from __future__ import annotations
import time
from typing import Dict, Tuple
from dataclasses import dataclass
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


from utils.redis_client import redis
from utils.logger import logger
from utils.metrics import observe_latency_ms
from utils.helpers import get_client_ip


READ_WINDOW_SEC = 60
READ_LIMIT = 100
ANALYSIS_WINDOW_SEC = 60
ANALYSIS_LIMIT = 10
DEFAULT_WINDOW_SEC = 60
DEFAULT_LIMIT = 60


# Identify endpoints by path prefix or route name
ENDPOINT_LIMITS: Dict[str, Tuple[int, int]] = {
	"/api/projects": (READ_LIMIT, READ_WINDOW_SEC),
	"/api/files": (READ_LIMIT, READ_WINDOW_SEC),
	"/api/analysis/run": (ANALYSIS_LIMIT, ANALYSIS_WINDOW_SEC),
	"/api/analysis": (READ_LIMIT, READ_WINDOW_SEC),
	"/api/reports": (READ_LIMIT, READ_WINDOW_SEC),
}


def _match_limit(path: str) -> Tuple[int, int]:
	for prefix, (limit, window) in ENDPOINT_LIMITS.items():
		if path.startswith(prefix):
			return limit, window
	return DEFAULT_LIMIT, DEFAULT_WINDOW_SEC




def _key(prefix: str, identifier: str, path: str) -> str:
	return f"rl:{prefix}:{identifier}:{path}"



class RateLimiterMiddleware(BaseHTTPMiddleware):
	async def dispatch(self, request: Request, call_next):
		start = time.time()
		path = request.url.path
		method = request.method

		# Skip safe methods from strict limits except where defined
		limit, window = _match_limit(path)

		user_id = getattr(request.state, "user_id", None)
		role = getattr(request.state, "role", None)
		ip = get_client_ip(request)

		# Admin bypass
		if role == "admin":
			return await call_next(request)

		# Determine bucket key (prefer user, then IP)
		ident = str(user_id) if user_id else ip
		now_ms = int(time.time() * 1000)

		# Sliding window with Redis Sorted Set
		bucket = _key("z", ident, path)
		cutoff = now_ms - window * 1000
		try:
			# prune old
			await redis.zremrangebyscore(bucket, 0, cutoff)
			# count current
			count = await redis.zcard(bucket)
			if count and count >= limit:
				# find earliest entry to compute Retry-After
				oldest = await redis.zrange(bucket, 0, 0, withscores=True)
				if oldest:
					oldest_ts = int(oldest[0][1])
					retry_after = max(0, (oldest_ts + window * 1000 - now_ms) // 1000)
				else:
					retry_after = window
				payload = {"success": False, "error": {"code": "RATE_LIMIT", "message": "Rate limit exceeded"}}
				return JSONResponse(payload, status_code=429, headers={"Retry-After": str(retry_after)})
			# add this request
			await redis.zadd(bucket, {str(now_ms): now_ms})
			await redis.pexpire(bucket, window * 1000)
		except Exception:
			# On Redis failure, do not block requests; log
			logger.exception("RATE_LIMITER_DEGRADED")

		response = await call_next(request)
		observe_latency_ms("rate_limiter", path, method, (time.time() - start) * 1000.0)
		return response




def add_rate_limiter(app):
	app.add_middleware(RateLimiterMiddleware)