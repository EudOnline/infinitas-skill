from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from server.db import get_db
from server.models import User
from server.modules.access import service as access_service
from server.modules.access.authn import AccessContext, resolve_access_context
from server.settings import get_settings

AUTH_COOKIE_NAME = 'infinitas_auth_token'
AUTH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
AUTH_SESSION_PREFIX = 'session:'


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not isinstance(authorization, str):
        return None
    prefix = 'Bearer '
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def _resolve_request_token(request: Request) -> str | None:
    return _extract_bearer_token(request.headers.get('authorization'))


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _urlsafe_b64decode(raw: str) -> bytes:
    padding = '=' * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode('ascii'))


def _session_signature(payload: str) -> str:
    secret = get_settings().secret_key.encode('utf-8')
    digest = hmac.new(secret, payload.encode('utf-8'), hashlib.sha256).digest()
    return _urlsafe_b64encode(digest)


def create_auth_session_cookie(credential_id: int) -> str:
    payload = _urlsafe_b64encode(
        json.dumps(
            {
                'credential_id': credential_id,
                'issued_at': int(time.time()),
            },
            separators=(',', ':'),
            sort_keys=True,
        ).encode('utf-8')
    )
    return f'{AUTH_SESSION_PREFIX}{payload}.{_session_signature(payload)}'


def _decode_auth_session_cookie(value: str | None) -> dict | None:
    raw = str(value or '').strip()
    if not raw.startswith(AUTH_SESSION_PREFIX):
        return None
    payload_and_sig = raw[len(AUTH_SESSION_PREFIX) :]
    payload, sep, signature = payload_and_sig.partition('.')
    if not payload or not sep or not signature:
        return None
    expected = _session_signature(payload)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        decoded = json.loads(_urlsafe_b64decode(payload).decode('utf-8'))
    except Exception:
        return None
    issued_at = decoded.get('issued_at')
    credential_id = decoded.get('credential_id')
    if not isinstance(issued_at, int) or not isinstance(credential_id, int):
        return None
    now = int(time.time())
    if issued_at > now + 60:
        return None
    if now - issued_at > AUTH_COOKIE_MAX_AGE:
        return None
    return decoded


def _resolve_session_access_context(db: Session, auth_cookie: str | None) -> AccessContext | None:
    decoded = _decode_auth_session_cookie(auth_cookie)
    if not isinstance(decoded, dict):
        return None
    credential = access_service.resolve_credential_by_id(db, decoded.get('credential_id'))
    if credential is None:
        return None
    if credential.revoked_at is not None:
        return None
    principal = access_service.get_principal(db, credential.principal_id)
    user = access_service.get_user_for_principal(db, principal)
    return AccessContext(
        credential=credential,
        principal=principal,
        user=user,
        scopes=access_service.parse_scopes(credential.scopes_json),
    )


def maybe_get_current_access_context(request: Request, db: Session) -> AccessContext | None:
    bearer = _resolve_request_token(request)
    if bearer:
        return resolve_access_context(db, bearer, allow_user_bridge=True)
    return _resolve_session_access_context(db, request.cookies.get(AUTH_COOKIE_NAME))


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
    token = _extract_bearer_token(authorization)
    if token:
        context = resolve_access_context(db, token, allow_user_bridge=True)
    else:
        context = _resolve_session_access_context(db, auth_cookie)
    if not token and not auth_cookie:
        raise HTTPException(status_code=401, detail='missing bearer token')
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
