"""Auth API for token-based authentication."""

import os
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth import (
    AUTH_COOKIE_MAX_AGE,
    AUTH_COOKIE_NAME,
    create_auth_session_cookie,
    maybe_get_current_user,
)
from server.db import get_db
from server.modules.access.authn import resolve_access_context

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Simple in-memory rate limiter for login attempts
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 10  # attempts per window


def _check_login_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW
    attempts = _login_attempts[client_ip]
    _login_attempts[client_ip] = [t for t in attempts if t > cutoff]
    if len(_login_attempts[client_ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
        )
    _login_attempts[client_ip].append(now)


class TokenLoginRequest(BaseModel):
    token: str


class TokenLoginResponse(BaseModel):
    success: bool
    username: str | None = None
    role: str | None = None
    error: str | None = None


def _resolve_language(request: Request) -> str:
    lang = (
        (request.query_params.get('lang') or request.headers.get('accept-language') or '')
        .strip()
        .lower()
    )
    return 'en' if lang.startswith('en') else 'zh'


def _pick_lang(lang: str, zh: str, en: str) -> str:
    return en if lang == 'en' else zh


def _secure_cookie_requested(request: Request) -> bool:
    override = str(os.environ.get("INFINITAS_SERVER_SECURE_COOKIES") or "").strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False

    forwarded_proto = (
        (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    )
    return request.url.scheme == "https" or forwarded_proto == "https"


@router.post("/login", response_model=TokenLoginResponse)
async def login(
    payload: TokenLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """Validate token and return user info."""
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_ip)
    lang = _resolve_language(request)
    context = resolve_access_context(db, payload.token, allow_user_bridge=True)
    if context is not None and context.credential is not None:
        from server.models import utcnow
        context.credential.last_used_at = utcnow()
        db.add(context.credential)
    if context is None or context.user is None:
        return TokenLoginResponse(
            success=False,
            error=_pick_lang(lang, "无效的 Token", "Invalid token"),
        )
    user = context.user
    secure_cookie = _secure_cookie_requested(request)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_auth_session_cookie(context.credential.id),
        max_age=AUTH_COOKIE_MAX_AGE,
        expires=AUTH_COOKIE_MAX_AGE,
        path="/",
        samesite="lax",
        secure=secure_cookie,
        httponly=True,
    )
    return TokenLoginResponse(success=True, username=user.username, role=user.role)


@router.post("/logout")
async def logout(response: Response, request: Request):
    """Clear the browser auth cookie."""
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        samesite="lax",
        secure=_secure_cookie_requested(request),
        httponly=True,
    )
    return {"success": True}


@router.get("/me")
async def get_current_user_info(request: Request, db: Session = Depends(get_db)):
    """Get current authenticated user info for browser session probing."""
    user = maybe_get_current_user(request, db)
    if user is None:
        return {"authenticated": False}
    return {"authenticated": True, "username": user.username, "role": user.role}
