"""Auth API for username/password authentication."""

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import (
    AUTH_COOKIE_MAX_AGE,
    AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    create_auth_session_cookie,
    generate_csrf_token,
    maybe_get_current_user,
)
from server.db import get_db
from server.models import Credential, utcnow
from server.modules.access import service as access_service
from server.rate_limit import get_rate_limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 10  # attempts per window


def _check_login_rate_limit(client_ip: str) -> None:
    limiter = get_rate_limiter()
    if not limiter.check(client_ip, max_attempts=_RATE_LIMIT_MAX, window_seconds=_RATE_LIMIT_WINDOW):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
        )
    limiter.record(client_ip)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
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
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """Validate username/password and return user info."""
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_ip)
    lang = _resolve_language(request)

    result = access_service.resolve_user_by_password(
        db, payload.username, payload.password
    )
    if result is None:
        response.status_code = 401
        return LoginResponse(
            success=False,
            error=_pick_lang(lang, "用户名或密码错误", "Invalid username or password"),
        )

    user, principal = result

    # Ensure a personal_token credential exists for session cookie creation
    credential = db.scalar(
        select(Credential)
        .where(Credential.type == "personal_token")
        .where(Credential.principal_id == principal.id)
        .order_by(Credential.id.desc())
    )
    if credential is None:
        # Create a synthetic credential for password-based login users
        credential = Credential(
            principal_id=principal.id,
            grant_id=None,
            type="personal_token",
            hashed_secret="password-auth",
            scopes_json=access_service.encode_scopes({"session:user", "api:user"}),
            resource_selector_json="{}",
            created_at=utcnow(),
        )
        db.add(credential)
        db.flush()

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
    return LoginResponse(success=True, username=user.username, role=user.role)


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
    _clear_csrf_cookie(response, request)
    return {"success": True}


@router.get("/csrf")
async def get_csrf_token(request: Request, response: Response):
    """Refresh and return a new CSRF token for the current session."""
    token = _set_csrf_cookie(response, request)
    return {"csrf_token": token}


@router.get("/me")
async def get_current_user_info(request: Request, db: Session = Depends(get_db)):
    """Get current authenticated user info for browser session probing."""
    user = maybe_get_current_user(request, db)
    if user is None:
        return {"authenticated": False}
    return {"authenticated": True, "username": user.username, "role": user.role}
