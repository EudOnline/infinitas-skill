from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from server.db import get_db
from server.models import User
from server.settings import get_settings

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


def _find_user_by_token(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    return db.query(User).filter(User.token == token).one_or_none()


def maybe_get_current_user(request: Request, db: Session) -> User | None:
    return _find_user_by_token(_resolve_request_token(request), db)


def get_current_user(
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization) or auth_cookie
    if not token:
        raise HTTPException(status_code=401, detail='missing bearer token')
    user = _find_user_by_token(token, db)
    if user is None:
        raise HTTPException(status_code=401, detail='invalid bearer token')
    return user


def require_role(*allowed_roles: str):
    allowed = set(allowed_roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail='insufficient role')
        return user

    return dependency


def require_registry_reader(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.registry_read_tokens:
        return

    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail='missing registry bearer token')
    if token not in settings.registry_read_tokens:
        raise HTTPException(status_code=401, detail='invalid registry bearer token')


def require_registry_reader_or_user(
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    if not settings.registry_read_tokens:
        return

    token = _extract_bearer_token(authorization)
    if token and token in settings.registry_read_tokens:
        return

    user = _find_user_by_token(token or auth_cookie, db)
    if user is not None:
        return

    if token or auth_cookie:
        raise HTTPException(status_code=401, detail='invalid registry bearer token')
    raise HTTPException(status_code=401, detail='missing registry bearer token')
