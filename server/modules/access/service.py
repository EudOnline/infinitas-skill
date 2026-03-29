from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import AccessGrant, Credential, Exposure, Principal, User, utcnow

TOKEN_HASH_PREFIX = "sha256:"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_token(raw: str | None) -> str:
    return str(raw or "").strip()


def hash_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{TOKEN_HASH_PREFIX}{digest}"


def token_matches_hash(token: str, stored_hash: str | None) -> bool:
    candidate = normalize_token(token)
    stored = str(stored_hash or "").strip()
    if not candidate or not stored:
        return False
    if not stored.startswith(TOKEN_HASH_PREFIX):
        return False
    return hmac.compare_digest(hash_token(candidate), stored)


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


def _active_credentials_query(now: datetime):
    return (
        select(Credential)
        .where(Credential.revoked_at.is_(None))
        .where((Credential.expires_at.is_(None)) | (Credential.expires_at > now))
        .order_by(Credential.id.desc())
    )


def resolve_credential_by_token(db: Session, token: str) -> Credential | None:
    normalized = normalize_token(token)
    if not normalized:
        return None
    now = _utcnow()
    return db.scalar(
        _active_credentials_query(now).where(Credential.hashed_secret == hash_token(normalized))
    )


def ensure_user_principal(db: Session, user: User) -> Principal:
    existing = db.scalar(
        select(Principal).where(Principal.kind == "user").where(Principal.slug == user.username)
    )
    if existing is not None:
        if existing.display_name != user.display_name:
            existing.display_name = user.display_name
            existing.updated_at = utcnow()
            db.add(existing)
        return existing

    principal = Principal(
        kind="user",
        slug=user.username,
        display_name=user.display_name,
    )
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
        select(Credential)
        .where(Credential.type == "personal_token")
        .where(Credential.principal_id == principal.id)
        .order_by(Credential.id.desc())
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

    updated = False
    if credential.hashed_secret != token_hash:
        credential.hashed_secret = token_hash
        updated = True
    if not credential.scopes_json:
        credential.scopes_json = default_scopes
        updated = True
    if updated:
        db.add(credential)
    return credential


@dataclass
class BridgedUserCredential:
    user: User
    principal: Principal
    credential: Credential


def bridge_legacy_user_token(db: Session, token: str) -> BridgedUserCredential | None:
    # Plaintext user tokens are migrated during schema upgrades and no longer act as
    # a runtime authentication fallback. Records that bypassed migration are rejected.
    return None


def get_principal(db: Session, principal_id: int | None) -> Principal | None:
    if principal_id is None:
        return None
    return db.get(Principal, principal_id)


def get_user_for_principal(db: Session, principal: Principal | None) -> User | None:
    if principal is None or principal.kind != "user":
        return None
    return db.scalar(select(User).where(User.username == principal.slug))


def has_scope(credential: Credential, scope: str) -> bool:
    return scope in parse_scopes(credential.scopes_json)


def create_grant_token(
    db: Session,
    *,
    grant: AccessGrant,
    scopes: set[str] | None = None,
    principal_id: int | None = None,
) -> tuple[str, Credential]:
    raw_token = f"grant_{secrets.token_urlsafe(24)}"
    credential = Credential(
        principal_id=principal_id,
        grant_id=grant.id,
        type="grant_token",
        hashed_secret=hash_token(raw_token),
        scopes_json=encode_scopes(scopes or {"artifact:download"}),
        resource_selector_json=json.dumps({"release_scope": "grant-bound"}, ensure_ascii=False),
        created_at=utcnow(),
    )
    db.add(credential)
    db.flush()
    return raw_token, credential


def grant_allows_release(db: Session, *, grant_id: int, release_id: int) -> bool:
    grant = db.get(AccessGrant, grant_id)
    if grant is None or grant.state != "active":
        return False
    exposure = db.get(Exposure, grant.exposure_id)
    if exposure is None:
        return False
    if exposure.state != "active" or exposure.install_mode != "enabled":
        return False
    return exposure.release_id == release_id
