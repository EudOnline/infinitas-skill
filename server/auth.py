from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from server.db import get_db
from server.models import User
from server.modules.access.authn import AccessContext, resolve_access_context

AUTH_COOKIE_NAME = 'infinitas_auth_token'
AUTH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not isinstance(authorization, str):
        return None
    prefix = 'Bearer '
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def _resolve_request_token(request: Request) -> str | None:
    return _extract_bearer_token(request.headers.get('authorization')) or request.cookies.get(AUTH_COOKIE_NAME)


def maybe_get_current_access_context(request: Request, db: Session) -> AccessContext | None:
    return resolve_access_context(db, _resolve_request_token(request), allow_user_bridge=True)


def maybe_get_current_user(request: Request, db: Session) -> User | None:
    context = maybe_get_current_access_context(request, db)
    if context is None:
        return None
    return context.user


def get_current_access_context(
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AccessContext:
    token = _extract_bearer_token(authorization) or auth_cookie
    if not token:
        raise HTTPException(status_code=401, detail='missing bearer token')
    context = resolve_access_context(db, token, allow_user_bridge=True)
    if context is None:
        raise HTTPException(status_code=401, detail='invalid bearer token')
    return context


def get_current_user(
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    context = get_current_access_context(
        authorization=authorization,
        auth_cookie=auth_cookie,
        db=db,
    )
    if context.user is None:
        raise HTTPException(status_code=401, detail='invalid bearer token')
    return context.user


def require_role(*allowed_roles: str):
    allowed = set(allowed_roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail='insufficient role')
        return user

    return dependency
