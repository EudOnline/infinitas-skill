"""Auth API for token-based authentication."""

import os

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth import AUTH_COOKIE_MAX_AGE, AUTH_COOKIE_NAME, maybe_get_current_user
from server.db import get_db
from server.modules.access.authn import resolve_access_context

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenLoginRequest(BaseModel):
    token: str


class TokenLoginResponse(BaseModel):
    success: bool
    username: str | None = None
    error: str | None = None


def _resolve_language(request: Request) -> str:
    lang = (request.query_params.get('lang') or request.headers.get('accept-language') or '').strip().lower()
    return 'en' if lang.startswith('en') else 'zh'


def _pick_lang(lang: str, zh: str, en: str) -> str:
    return en if lang == 'en' else zh


def _secure_cookie_requested(request: Request) -> bool:
    override = str(os.environ.get("INFINITAS_SERVER_SECURE_COOKIES") or "").strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    return request.url.scheme == "https" or forwarded_proto == "https"


@router.post("/login", response_model=TokenLoginResponse)
async def login(
    payload: TokenLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """Validate token and return user info."""
    lang = _resolve_language(request)
    context = resolve_access_context(db, payload.token, allow_user_bridge=True)
    if context is None or context.user is None:
        return TokenLoginResponse(success=False, error=_pick_lang(lang, "无效的 Token", "Invalid token"))
    user = context.user
    secure_cookie = _secure_cookie_requested(request)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=payload.token,
        max_age=AUTH_COOKIE_MAX_AGE,
        expires=AUTH_COOKIE_MAX_AGE,
        path="/",
        samesite="lax",
        secure=secure_cookie,
        httponly=True,
    )
    return TokenLoginResponse(success=True, username=user.username)


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
