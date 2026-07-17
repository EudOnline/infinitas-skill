from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from server.model_base import utcnow
from server.modules.identity.models import Credential, Principal, User
from server.modules.identity.passwords import verify_password

TOKEN_HASH_PREFIX = "sha256:"  # noqa: S105
BEARER_CREDENTIAL_TYPES = frozenset({"personal_token", "product_token", "grant_token"})


def normalize_token(raw: str | None) -> str:
    return str(raw or "").strip()


def hash_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{TOKEN_HASH_PREFIX}{digest}"


def parse_scopes(scopes_json: str | None) -> set[str]:
    if not scopes_json:
        return set()
    try:
        payload = json.loads(scopes_json)
    except json.JSONDecodeError:
        return set()
    if isinstance(payload, str):
        return {payload} if payload else set()
    if not isinstance(payload, list):
        return set()
    return {str(item).strip() for item in payload if str(item).strip()}


def encode_scopes(scopes: set[str] | list[str] | tuple[str, ...]) -> str:
    normalized = sorted({str(item).strip() for item in scopes if str(item).strip()})
    return json.dumps(normalized, ensure_ascii=False)


def token_type_for_scopes(scopes_json: str | None) -> str:
    scopes = parse_scopes(scopes_json)
    write_scopes = {"authoring:write", "publish:write", "registry:publish"}
    if any(scope.endswith(":write") or scope in write_scopes for scope in scopes):
        return "publisher"
    return "reader"


def _active_credentials_query(now: datetime) -> Select[tuple[Credential]]:
    return (
        select(Credential)
        .where(Credential.revoked_at.is_(None))
        .where((Credential.expires_at.is_(None)) | (Credential.expires_at > now))
        .order_by(Credential.id.desc())
    )


def _mark_credential_used(db: Session, credential: Credential, now: datetime) -> Credential:
    last_used_at = credential.last_used_at
    if last_used_at is not None and last_used_at.tzinfo is None:
        last_used_at = last_used_at.replace(tzinfo=timezone.utc)
    if last_used_at is None or now - last_used_at >= timedelta(minutes=5):
        credential.last_used_at = now
        db.add(credential)
    return credential


def resolve_credential_by_token(db: Session, token: str) -> Credential | None:
    normalized = normalize_token(token)
    if not normalized:
        return None
    now = utcnow()
    credential = db.scalar(
        _active_credentials_query(now).where(
            Credential.type.in_(BEARER_CREDENTIAL_TYPES),
            Credential.hashed_secret == hash_token(normalized),
        )
    )
    return None if credential is None else _mark_credential_used(db, credential, now)


def resolve_credential_by_id(db: Session, credential_id: int | None) -> Credential | None:
    if not isinstance(credential_id, int) or credential_id <= 0:
        return None
    now = utcnow()
    credential = db.scalar(_active_credentials_query(now).where(Credential.id == credential_id))
    return None if credential is None else _mark_credential_used(db, credential, now)


def ensure_user_principal(db: Session, user: User) -> Principal:
    existing = db.scalar(
        select(Principal).where(Principal.kind == "user").where(Principal.slug == user.username)
    )
    if existing is not None:
        if existing.display_name != user.display_name:
            existing.display_name = user.display_name
            cast(Any, existing).updated_at = utcnow()
            db.add(existing)
        return existing
    principal = Principal(kind="user", slug=user.username, display_name=user.display_name)
    db.add(principal)
    db.flush()
    return principal


def ensure_personal_credential_for_user(
    db: Session,
    *,
    user: User,
    principal: Principal,
    raw_token: str,
) -> Credential:
    credential = db.scalar(
        _active_credentials_query(utcnow())
        .where(Credential.type == "personal_token")
        .where(Credential.principal_id == principal.id)
    )
    token_hash = hash_token(raw_token)
    default_scopes = encode_scopes({"session:user", "api:user"})
    if credential is None:
        credential = Credential(
            principal_id=principal.id,
            grant_id=None,
            type="personal_token",
            hashed_secret=token_hash,
            scopes_json=default_scopes,
            resource_selector_json="{}",
            created_at=utcnow(),
        )
        db.add(credential)
        db.flush()
        return credential
    if credential.hashed_secret != token_hash:
        credential.hashed_secret = token_hash
    if not credential.scopes_json or credential.scopes_json in ("[]", "{}", ""):
        credential.scopes_json = default_scopes
    db.add(credential)
    return credential


def get_personal_credential(db: Session, *, principal_id: int) -> Credential | None:
    return db.scalar(
        _active_credentials_query(utcnow())
        .where(Credential.type == "personal_token")
        .where(Credential.principal_id == principal_id)
    )


def get_principal(db: Session, principal_id: int | None) -> Principal | None:
    return None if principal_id is None else db.get(Principal, principal_id)


def get_user_for_principal(db: Session, principal: Principal | None) -> User | None:
    if principal is None or principal.kind != "user":
        return None
    return db.scalar(select(User).where(User.username == principal.slug))


def get_principal_for_user(db: Session, user: User | None) -> Principal | None:
    if user is None:
        return None
    return db.scalar(
        select(Principal).where(Principal.kind == "user").where(Principal.slug == user.username)
    )


def resolve_user_by_password(
    db: Session,
    username: str,
    password: str,
) -> tuple[User, Principal] | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user, ensure_user_principal(db, user)


def create_fresh_session_credential(db: Session, *, principal_id: int) -> Credential:
    credentials = db.scalars(
        select(Credential)
        .where(Credential.principal_id == principal_id)
        .where(Credential.revoked_at.is_(None))
        .where(
            or_(
                Credential.type == "session",
                (Credential.type == "personal_token")
                & Credential.hashed_secret.startswith("session:"),
            )
        )
    ).all()
    for credential in credentials:
        cast(Any, credential).revoked_at = utcnow()
        db.add(credential)
    credential = Credential(
        principal_id=principal_id,
        grant_id=None,
        type="session",
        hashed_secret=f"session:{secrets.token_urlsafe(16)}",
        scopes_json=encode_scopes({"session:user", "api:user"}),
        resource_selector_json="{}",
        created_at=utcnow(),
        last_used_at=utcnow(),
    )
    db.add(credential)
    db.flush()
    return credential


def ensure_session_credential(db: Session, *, principal_id: int) -> Credential:
    credential = db.scalar(
        select(Credential)
        .where(Credential.type == "session")
        .where(Credential.principal_id == principal_id)
        .where(Credential.revoked_at.is_(None))
        .order_by(Credential.id.desc())
    )
    if credential is not None:
        return credential
    return create_fresh_session_credential(db, principal_id=principal_id)
