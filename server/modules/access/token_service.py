from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import AccessGrant, Credential, Exposure, Principal, Skill, utcnow
from server.modules.access import service as access_service
from server.modules.audit import service as audit_service
from server.modules.release import service as release_service

TokenType = Literal["reader", "publisher"]
ScopeType = Literal["object", "release"]


class TokenServiceError(Exception):
    pass


class TokenNotFoundError(TokenServiceError):
    pass


class TokenForbiddenError(TokenServiceError):
    pass


class TokenConflictError(TokenServiceError):
    pass


@dataclass(frozen=True)
class ActorRef:
    principal: Principal
    is_maintainer: bool


def _actor_ref(actor: ActorRef) -> str:
    return f"principal:{actor.principal.slug}"


def _find_release_for_scope(
    db: Session,
    *,
    object_id: int,
    scope_type: ScopeType,
    scope_id: int,
) -> int:
    from server.models import Release

    if scope_type == "release":
        release = release_service.get_release_or_404(db, scope_id)
        if release.skill_id != object_id:
            raise TokenForbiddenError("release does not belong to object")
        return int(release.id)

    if scope_id != object_id:
        raise TokenForbiddenError("object token scope must match object")

    release = db.scalar(
        select(Release)
        .where(Release.skill_id == object_id)
        .where(Release.state == "ready")
        .order_by(Release.ready_at.desc(), Release.id.desc())
    )
    if release is None:
        raise TokenConflictError("object has no ready release for token anchoring")
    return int(release.id)


def _require_active_grant_exposure(db: Session, *, release_id: int) -> Exposure:
    try:
        return access_service.require_active_grant_exposure(db, release_id=release_id)
    except ValueError:
        raise TokenConflictError("active grant visibility required before issuing tokens")


def _assert_object_owner(
    db: Session,
    *,
    skill: Skill,
    actor: ActorRef,
) -> None:
    if actor.is_maintainer:
        return
    if skill.namespace_id != actor.principal.id:
        raise TokenForbiddenError("object namespace access denied")


def _token_scopes(token_type: TokenType) -> set[str]:
    scopes = {"artifact:download"}
    if token_type == "publisher":
        scopes.add("release:write")
        scopes.add("registry:publish")
    return scopes


def _token_metadata(credential: Credential) -> dict:
    state = "revoked" if credential.revoked_at is not None else "active"
    return {
        "id": credential.id,
        "name": credential.product_token_name,
        "type": credential.product_token_type or "reader",
        "scope_type": credential.product_scope_type or "release",
        "scope_id": credential.product_scope_id,
        "issued_for": credential.issued_for or None,
        "state": state,
        "scopes": sorted(access_service.parse_scopes(credential.scopes_json)),
        "expires_at": (
            credential.expires_at.isoformat().replace("+00:00", "Z")
            if credential.expires_at is not None
            else None
        ),
        "created_at": credential.created_at.isoformat().replace("+00:00", "Z"),
        "last_used_at": (
            credential.last_used_at.isoformat().replace("+00:00", "Z")
            if credential.last_used_at is not None
            else None
        ),
    }


def create_product_token(
    db: Session,
    *,
    object_id: int,
    name: str,
    token_type: TokenType,
    scope_type: ScopeType,
    scope_id: int,
    issued_for: str | None,
    expires_in_days: int | None,
    actor: ActorRef,
) -> tuple[str, dict]:
    skill = db.get(Skill, object_id)
    if skill is None:
        raise TokenNotFoundError("object not found")
    _assert_object_owner(db, skill=skill, actor=actor)

    release_id = _find_release_for_scope(
        db,
        object_id=object_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    exposure = _require_active_grant_exposure(db, release_id=release_id)

    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise TokenConflictError("token name is required")

    grant = AccessGrant(
        exposure_id=exposure.id,
        grant_type="token",
        subject_ref=f"agent://{skill.slug}/{token_type}-{secrets.token_hex(4)}",
        constraints_json=json.dumps(
            {
                "label": normalized_name,
                "product_token_type": token_type,
                "scope_type": scope_type,
                "scope_id": scope_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        state="active",
        created_by_principal_id=actor.principal.id,
    )
    db.add(grant)
    db.flush()

    raw_token = f"tok_{secrets.token_urlsafe(24)}"
    expires_at: datetime | None = None
    if expires_in_days is not None:
        expires_at = utcnow() + timedelta(days=expires_in_days)

    credential = Credential(
        principal_id=None,
        grant_id=grant.id,
        type="product_token",
        product_token_name=normalized_name,
        product_token_type=token_type,
        product_scope_type=scope_type,
        product_scope_id=scope_id,
        issued_for=str(issued_for or "").strip(),
        hashed_secret=access_service.hash_token(raw_token),
        scopes_json=access_service.encode_scopes(_token_scopes(token_type)),
        resource_selector_json=json.dumps(
            {
                "object_id": object_id,
                "release_id": release_id,
                "scope_type": scope_type,
                "scope_id": scope_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        expires_at=expires_at,
        created_at=utcnow(),
    )
    db.add(credential)
    db.flush()
    audit_service.append_audit_event(
        db,
        aggregate_type="token",
        aggregate_id=str(credential.id),
        event_type="token.created",
        actor_ref=_actor_ref(actor),
        payload={
            "object_id": object_id,
            "release_id": release_id,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "token_type": token_type,
            "name": normalized_name,
        },
    )
    return raw_token, _token_metadata(credential)


def list_product_tokens(db: Session, *, object_id: int, actor: ActorRef) -> list[dict]:
    skill = db.get(Skill, object_id)
    if skill is None:
        raise TokenNotFoundError("object not found")
    _assert_object_owner(db, skill=skill, actor=actor)

    credentials = db.scalars(
        select(Credential)
        .where(Credential.type == "product_token")
        .order_by(Credential.id.desc())
    ).all()
    rows: list[dict] = []
    for credential in credentials:
        selector = json.loads(credential.resource_selector_json or "{}")
        if int(selector.get("object_id") or 0) == object_id:
            rows.append(_token_metadata(credential))
    return rows


def revoke_product_token(db: Session, *, token_id: int, actor: ActorRef) -> dict:
    credential = db.get(Credential, token_id)
    if credential is None or credential.type != "product_token":
        raise TokenNotFoundError("token not found")
    selector = json.loads(credential.resource_selector_json or "{}")
    object_id = int(selector.get("object_id") or 0)
    skill = db.get(Skill, object_id)
    if skill is None:
        raise TokenNotFoundError("object not found")
    _assert_object_owner(db, skill=skill, actor=actor)

    if credential.revoked_at is None:
        credential.revoked_at = utcnow()
        db.add(credential)
        if credential.grant_id is not None:
            grant = db.get(AccessGrant, credential.grant_id)
            if grant is not None:
                grant.state = "revoked"
                db.add(grant)
        audit_service.append_audit_event(
            db,
            aggregate_type="token",
            aggregate_id=str(credential.id),
            event_type="token.revoked",
            actor_ref=_actor_ref(actor),
            payload={"object_id": object_id},
        )
    return _token_metadata(credential)
