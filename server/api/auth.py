"""Auth API for token-based authentication."""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth import AUTH_COOKIE_MAX_AGE, AUTH_COOKIE_NAME, maybe_get_current_user
from server.db import get_db
from server.modules.access.authn import find_user_by_token

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


@router.post("/login", response_model=TokenLoginResponse)
async def login(
    payload: TokenLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """Validate token and return user info."""
    lang = _resolve_language(request)
    user = find_user_by_token(payload.token, db)
    if user is None:
        return TokenLoginResponse(success=False, error=_pick_lang(lang, "无效的 Token", "Invalid token"))
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=payload.token,
        max_age=AUTH_COOKIE_MAX_AGE,
        expires=AUTH_COOKIE_MAX_AGE,
        path="/",
        samesite="lax",
        httponly=False,
    )
    return TokenLoginResponse(success=True, username=user.username)


@router.post("/logout")
async def logout(response: Response):
    """Clear the browser auth cookie."""
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/", samesite="lax")
    return {"success": True}


@router.get("/me")
async def get_current_user_info(request: Request, db: Session = Depends(get_db)):
    """Get current authenticated user info for browser session probing."""
    user = maybe_get_current_user(request, db)
    if user is None:
        return {"authenticated": False}
    return {"authenticated": True, "username": user.username, "role": user.role}
