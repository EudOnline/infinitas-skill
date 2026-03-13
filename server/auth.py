from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from server.db import get_db
from server.models import User


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not isinstance(authorization, str):
        return None
    prefix = 'Bearer '
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail='missing bearer token')
    user = db.query(User).filter(User.token == token).one_or_none()
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
