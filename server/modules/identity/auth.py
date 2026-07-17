from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Callable
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

import server.modules.identity.service as identity_service
from server.db import get_db
from server.logging import get_logger
from server.modules.access.authn import AccessContext, resolve_access_context
from server.modules.identity.models import User
from server.settings import get_settings

AUTH_COOKIE_NAME = "infinitas_auth_token"
AUTH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
AUTH_SESSION_PREFIX = "session:"

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not isinstance(authorization, str):
        return None
    prefix = "Bearer "
    if not authorization[: len(prefix)].lower() == prefix.lower():
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def _resolve_request_token(request: Request) -> str | None:
    return _extract_bearer_token(request.headers.get("authorization"))


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _derive_aes_key() -> bytes:
    """Derive a 32-byte AES-256 key from the server secret using HKDF."""
    return HKDF(
        algorithm=SHA256(),
        length=32,
        salt=None,
        info=b"infinitas-session-encryption",
    ).derive(get_settings().secret_key.encode("utf-8"))


def _encrypt_payload(plaintext: bytes) -> bytes:
    """Encrypt payload using AES-256-GCM with an HKDF-derived key."""
    key = _derive_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext  # Return nonce + ciphertext


def _decrypt_payload(ciphertext: bytes) -> bytes | None:
    """Decrypt payload using AES-256-GCM with an HKDF-derived key.

    Returns None if decryption fails.
    """
    try:
        key = _derive_aes_key()
        aesgcm = AESGCM(key)
        nonce = ciphertext[:12]
        actual_ciphertext = ciphertext[12:]
        return aesgcm.decrypt(nonce, actual_ciphertext, None)
    except Exception:
        get_logger(__name__).debug("session cookie decrypt failed", exc_info=True)
        return None


def _session_signature(payload: str) -> str:
    secret = get_settings().secret_key.encode("utf-8")
    # hmac.new() is the canonical HMAC constructor in Python's hmac module
    digest = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).digest()
    return _urlsafe_b64encode(digest)


def create_auth_session_cookie(credential_id: int) -> str:
    plaintext = json.dumps(
        {
            "credential_id": credential_id,
            "issued_at": int(time.time()),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    ciphertext = _encrypt_payload(plaintext)
    payload = _urlsafe_b64encode(ciphertext)
    return f"{AUTH_SESSION_PREFIX}{payload}.{_session_signature(payload)}"


def _decode_auth_session_cookie(value: str | None) -> dict | None:
    raw = str(value or "").strip()
    if not raw.startswith(AUTH_SESSION_PREFIX):
        return None
    payload_and_sig = raw[len(AUTH_SESSION_PREFIX) :]
    payload, sep, signature = payload_and_sig.partition(".")
    if not payload or not sep or not signature:
        return None
    expected = _session_signature(payload)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        ciphertext = _urlsafe_b64decode(payload)
        plaintext = _decrypt_payload(ciphertext)
        if plaintext is None:
            return None
        decoded: dict[str, Any] | None = json.loads(plaintext.decode("utf-8"))
    except Exception:
        get_logger(__name__).debug("session cookie decode failed", exc_info=True)
        return None
    if not isinstance(decoded, dict):
        return None
    issued_at = decoded.get("issued_at")
    credential_id = decoded.get("credential_id")
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
    credential = identity_service.resolve_credential_by_id(db, decoded.get("credential_id"))
    if credential is None:
        return None
    if credential.revoked_at is not None:
        return None
    principal = identity_service.get_principal(db, credential.principal_id)
    user = identity_service.get_user_for_principal(db, principal)
    return AccessContext(
        credential=credential,
        principal=principal,
        user=user,
        scopes=identity_service.parse_scopes(credential.scopes_json),
    )


def maybe_get_current_access_context(request: Request, db: Session) -> AccessContext | None:
    bearer = _resolve_request_token(request)
    if bearer:
        return resolve_access_context(db, bearer)
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
        context = resolve_access_context(db, token)
    else:
        context = _resolve_session_access_context(db, auth_cookie)
    if not token and not auth_cookie:
        raise HTTPException(status_code=401, detail="missing bearer token")
    if context is None:
        raise HTTPException(status_code=401, detail="invalid bearer token")
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
        raise HTTPException(status_code=401, detail="invalid bearer token")
    return context.user


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    allowed = set(allowed_roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="insufficient role")
        return user

    return dependency


# ── CSRF Protection ────────────────────────────────────────────────────────


def generate_csrf_token() -> str:
    """Generate a cryptographically secure random CSRF token."""
    return secrets.token_urlsafe(32)


def validate_csrf_token(request: Request) -> None:
    """
    Validate CSRF token for cookie-authenticated state-changing requests.

    Skips validation when:
    - Request method is safe (GET, HEAD, OPTIONS, TRACE)
    - Bearer token authentication is used
    - No auth cookie is present (not logged in)
    """
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return

    # Bearer token auth is not vulnerable to CSRF
    if _resolve_request_token(request):
        return

    # No auth cookie means no session to protect
    if not request.cookies.get(AUTH_COOKIE_NAME):
        return

    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(CSRF_HEADER_NAME)

    if not csrf_cookie or not csrf_header:
        raise HTTPException(status_code=403, detail="CSRF token missing")

    if not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")
