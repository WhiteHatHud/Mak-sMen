
#### `api/middleware/auth.py`
"""Auth middleware & dependencies.
- JWT Bearer auth with optional API Key fallback
- Role-based access control (admin, analyst, viewer)
- Token refresh helper (sliding-session via refresh cookie)
- Request-ID, request/response logging, latency metrics
"""
from __future__ import annotations
from typing import Optional, Dict, Any, Callable, Iterable
from datetime import datetime, timedelta, timezone
import os
import uuid

import jwt
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import BaseModel

from utils.logger import logger
from utils.metrics import observe_latency_ms
from services.azure_ml.config import settings as ml_settings  # example import (optional)
from models.project import User  # your ORM model
from utils.helpers import get_client_ip
from utils.redis_client import redis

ALGORITHM = os.getenv("JWT_ALG", "HS256")
ACCESS_SECRET = os.getenv("JWT_ACCESS_SECRET", "dev-access-secret")
REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "dev-refresh-secret")
ACCESS_TTL_MIN = int(os.getenv("JWT_ACCESS_TTL_MIN", "30"))
REFRESH_TTL_DAYS = int(os.getenv("JWT_REFRESH_TTL_DAYS", "7"))
REFRESH_THRESHOLD_MIN = int(os.getenv("JWT_REFRESH_THRESHOLD_MIN", "5"))
API_KEY_HEADER = os.getenv("API_KEY_HEADER", "X-API-Key")

security = HTTPBearer(auto_error=False)

class AuthedUser(BaseModel):
    id: int
    email: str
    role: str  # admin | analyst | viewer

# ---------- JWT helpers ----------

def sign_access_token(payload: dict) -> str:
    now = datetime.now(timezone.utc)
    body = {**payload, "exp": now + timedelta(minutes=ACCESS_TTL_MIN), "iat": now}
    return jwt.encode(body, ACCESS_SECRET, algorithm=ALGORITHM)


def sign_refresh_token(payload: dict) -> str:
    now = datetime.now(timezone.utc)
    body = {**payload, "exp": now + timedelta(days=REFRESH_TTL_DAYS), "iat": now}
    return jwt.encode(body, REFRESH_SECRET, algorithm=ALGORITHM)


def verify_token(token: str, refresh: bool = False) -> dict:
    """Verify and decode a JWT token.
    Raises jwt exceptions if invalid/expired.
    """
    secret = REFRESH_SECRET if refresh else ACCESS_SECRET
    return jwt.decode(token, secret, algorithms=[ALGORITHM])

# ---------- API Key helper ----------
async def resolve_api_key(key: str) -> Optional[AuthedUser]:
    # example: lookup API key in Redis/DB -> user record
    if not key:
        return None
    user_id = await redis.get(f"api_key:{key}")
    if not user_id:
        return None
    user = await User.get(int(user_id))  # implement ORM lookup
    if not user:
        return None
    return AuthedUser(id=user.id, email=user.email, role=user.role)

# ---------- Dependency ----------
async def get_current_user(request: Request, cred: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> AuthedUser:
    """Authenticate via Bearer access token or API key header."""
    # API Key fallback
    api_key = request.headers.get(API_KEY_HEADER)
    if api_key:
        authed = await resolve_api_key(api_key)
        if authed:
            request.state.user_id = authed.id
            request.state.role = authed.role
            return authed

    if not cred or cred.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

    token = cred.credentials
    try:
        payload = verify_token(token)
        user = await User.get(int(payload.get("sub")))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        request.state.user_id = user.id
        request.state.role = user.role
        # opportunistic refresh via cookie refresh token if exp near
        await maybe_issue_new_access_token(request, user)
        return AuthedUser(id=user.id, email=user.email, role=user.role)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def maybe_issue_new_access_token(request: Request, user: Any) -> None:
    """If access token is close to expiry and a valid refresh token cookie exists,
    attach a new access token in the response header via request.state._new_access_token.
    """
    try:
        authz = request.headers.get("authorization", "")
        if not authz.lower().startswith("bearer "):
            return
        token = authz.split(" ", 1)[1]
        payload = jwt.decode(token, ACCESS_SECRET, algorithms=[ALGORITHM], options={"verify_exp": False})
        exp = int(payload.get("exp", 0))
        now = int(datetime.now(timezone.utc).timestamp())
        if exp - now > REFRESH_THRESHOLD_MIN * 60:
            return
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            return
        verify_token(refresh_token, refresh=True)
        new_token = sign_access_token({"sub": str(user.id), "role": user.role})
        # store to be added by logging middleware to the response headers
        request.state._new_access_token = new_token
    except Exception:
        # do not fail request on refresh issues
        logger.debug("ACCESS_TOKEN_REFRESH_SKIPPED")

# ---------- RBAC helper ----------

def role_required(*allowed_roles: str) -> Callable:
    async def _dep(request: Request, user: AuthedUser = Depends(get_current_user)) -> AuthedUser:
        if allowed_roles and user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden: insufficient role")
        return user
    return _dep

# ---------- Logging / Request-ID / Perf Middleware ----------
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = datetime.now(timezone.utc)
        path = request.url.path
        method = request.method
        client_ip = get_client_ip(request)
        try:
            response: Response = await call_next(request)
        except Exception:
            logger.exception("REQUEST_FAILED", extra={"req_id": req_id, "path": path, "method": method})
            raise
        finally:
            elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            observe_latency_ms("http_server", path, method, elapsed_ms)
        if getattr(request.state, "_new_access_token", None):
            response.headers["X-New-Access-Token"] = request.state._new_access_token
        response.headers["X-Request-ID"] = req_id
        logger.info(
            "REQ",
            extra={"req_id": req_id, "path": path, "method": method, "ip": client_ip, "ms": f"{elapsed_ms:.2f}"},
        )
        return response

# ---------- FastAPI registration helper ----------

def add_auth_logging(app):
    app.add_middleware(LoggingMiddleware)


def auth_middleware(app):
    """Add authentication middleware to the FastAPI app."""
    add_auth_logging(app)