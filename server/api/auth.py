"""Auth API for username/password authentication."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.auth import (
    AUTH_COOKIE_MAX_AGE,
    AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    _decode_auth_session_cookie,
    create_auth_session_cookie,
    generate_csrf_token,
    maybe_get_current_user,
)
from server.db import get_db
from server.logging import get_logger
from server.models import Credential, utcnow
from server.modules.access import service as access_service
from server.rate_limit import get_rate_limiter, resolve_rate_limit_key
from server.ui.i18n import pick_lang, resolve_language

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

log = get_logger(__name__)

_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 10  # attempts per window


def _check_login_rate_limit(request: Request, user_id: int | None = None) -> None:
    rate_limit_key = resolve_rate_limit_key(request, user_id)
    limiter = get_rate_limiter()
    if not limiter.check(
        rate_limit_key, max_attempts=_RATE_LIMIT_MAX, window_seconds=_RATE_LIMIT_WINDOW
    ):
        log.warning("login rate limit exceeded for key=%s", rate_limit_key)
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
        )
    limiter.record(rate_limit_key)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    success: bool
    username: str | None = None
    role: str | None = None
    error: str | None = None


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


def _set_csrf_cookie(response: Response, request: Request) -> str:
    token = generate_csrf_token()
    secure = _secure_cookie_requested(request)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=AUTH_COOKIE_MAX_AGE,
        path="/",
        samesite="lax",
        secure=secure,
        httponly=False,  # Must be readable by JS for double-submit pattern
    )
    return token


def _clear_csrf_cookie(response: Response, request: Request) -> None:
    secure = _secure_cookie_requested(request)
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        samesite="lax",
        secure=secure,
        httponly=False,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """Validate username/password and return user info."""
    # Check rate limit before attempting login (unauthenticated)
    _check_login_rate_limit(request, user_id=None)
    lang = resolve_language(request)
    client_ip = request.client.host if request.client else "unknown"

    result = access_service.resolve_user_by_password(
        db, payload.username, payload.password
    )
    if result is None:
        log.warning("login failed for username=%s ip=%s", payload.username, client_ip)
        response.status_code = 401
        return LoginResponse(
            success=False,
            error=pick_lang(lang, "用户名或密码错误", "Invalid username or password"),
        )

    user, principal = result

    # Ensure a personal_token credential exists for session cookie creation
    credential = access_service.ensure_session_credential(db, principal_id=principal.id)
    credential.last_used_at = utcnow()
    db.add(credential)

    secure_cookie = _secure_cookie_requested(request)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_auth_session_cookie(credential.id),
        max_age=AUTH_COOKIE_MAX_AGE,
        expires=AUTH_COOKIE_MAX_AGE,
        path="/",
        samesite="lax",
        secure=secure_cookie,
        httponly=True,
    )
    _set_csrf_cookie(response, request)
    log.info("login success username=%s role=%s ip=%s", user.username, user.role, client_ip)
    return LoginResponse(success=True, username=user.username, role=user.role)


@router.post("/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    """Revoke the session credential and clear browser cookies."""
    # Revoke the credential on the server side to prevent cookie reuse
    cookie_value = request.cookies.get(AUTH_COOKIE_NAME)
    decoded = _decode_auth_session_cookie(cookie_value)
    if isinstance(decoded, dict) and isinstance(decoded.get("credential_id"), int):
        credential = db.get(Credential, decoded["credential_id"])
        if credential is not None and credential.revoked_at is None:
            credential.revoked_at = utcnow()
            db.add(credential)
            db.commit()
            log.info("session credential revoked on logout credential_id=%s", credential.id)

    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        samesite="lax",
        secure=_secure_cookie_requested(request),
        httponly=True,
    )
    _clear_csrf_cookie(response, request)
    return {"success": True}


@router.get("/csrf")
def get_csrf_token(request: Request, response: Response):
    """Refresh and return a new CSRF token for the current session."""
    token = _set_csrf_cookie(response, request)
    return {"csrf_token": token}


@router.get("/me")
def get_current_user_info(request: Request, db: Session = Depends(get_db)):
    """Get current authenticated user info for browser session probing."""
    user = maybe_get_current_user(request, db)
    if user is None:
        return {"authenticated": False}
    return {"authenticated": True, "username": user.username, "role": user.role}
