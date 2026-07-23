from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

import server.modules.access.service as access_service
import server.modules.audit.service as audit_service
import server.modules.identity.service as identity_service
import server.modules.release.service as release_service
from server.model_base import utcnow
from server.modules.access.models import AccessGrant
from server.modules.authoring.models import Skill
from server.modules.exposure.models import Exposure
from server.modules.identity.models import Credential
from server.modules.shared.actor import ActorRef
from server.modules.shared.actor import actor_ref_label as _actor_ref
from server.modules.shared.formatting import iso_format

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


def _find_release_for_scope(
    db: Session,
    *,
    object_id: int,
    scope_type: ScopeType,
    scope_id: int,
) -> int:
    from server.modules.release.models import Release

    if scope_type == "release":
        release = release_service.get_release_or_404(db, scope_id)
        if release.skill_id != object_id:
            raise TokenForbiddenError("release does not belong to object")
        return int(release.id)

    if scope_id != object_id:
        raise TokenForbiddenError("object token scope must match object")

    latest_release: Release | None = db.scalar(
        select(Release)
        .where(Release.skill_id == object_id)
        .where(Release.state == "ready")
        .order_by(Release.ready_at.desc(), Release.id.desc())
    )
    if latest_release is None:
        raise TokenConflictError("object has no ready release for token anchoring")
    return int(latest_release.id)


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
    try:
        release_service.assert_skill_owner(
            db,
            skill,
            principal_id=actor.principal.id,
            is_maintainer=actor.is_maintainer,
        )
    except release_service.ForbiddenError as exc:
        raise TokenForbiddenError("object namespace access denied") from exc


def _token_scopes(token_type: TokenType) -> set[str]:
    scopes = {"artifact:download"}
    if token_type == "publisher":  # noqa: S105
        scopes.add("exposure:write")
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
        "scopes": sorted(identity_service.parse_scopes(credential.scopes_json)),
        "expires_at": iso_format(credential.expires_at),
        "created_at": iso_format(credential.created_at),
        "last_used_at": iso_format(credential.last_used_at),
    }


def _create_token_grant(
    db: Session,
    *,
    exposure: Exposure | None,
    skill: Skill,
    normalized_name: str,
    token_type: TokenType,
    scope_type: ScopeType,
    scope_id: int,
    actor: ActorRef,
) -> AccessGrant | None:
    if exposure is None:
        return None
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
    return grant


def _build_product_credential(
    *,
    actor: ActorRef,
    grant: AccessGrant | None,
    object_id: int,
    release_id: int | None,
    scope_type: ScopeType,
    scope_id: int,
    token_type: TokenType,
    normalized_name: str,
    issued_for: str | None,
    raw_token: str,
    expires_at: datetime | None,
) -> Credential:
    return Credential(
        principal_id=actor.principal.id if token_type == "publisher" else None,  # noqa: S105
        grant_id=grant.id if grant is not None else None,
        type="product_token",
        product_token_name=normalized_name,
        product_token_type=token_type,
        product_object_id=object_id,
        product_scope_type=scope_type,
        product_scope_id=scope_id,
        issued_for=str(issued_for or "").strip(),
        hashed_secret=identity_service.hash_token(raw_token),
        scopes_json=identity_service.encode_scopes(_token_scopes(token_type)),
        resource_selector_json=json.dumps(
            {
                "object_id": object_id,
                **({"release_id": release_id} if release_id is not None else {}),
                "scope_type": scope_type,
                "scope_id": scope_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        expires_at=expires_at,
        created_at=utcnow(),
    )


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

    if scope_type == "object" and token_type != "publisher":  # noqa: S105
        raise TokenConflictError("object scope is only supported for publisher tokens")
    if scope_type == "object" and scope_id != object_id:
        raise TokenForbiddenError("object token scope must match object")

    release_id: int | None = None
    exposure: Exposure | None = None
    if scope_type == "release":
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

    grant = _create_token_grant(
        db,
        exposure=exposure,
        skill=skill,
        normalized_name=normalized_name,
        token_type=token_type,
        scope_type=scope_type,
        scope_id=scope_id,
        actor=actor,
    )

    raw_token = f"tok_{secrets.token_urlsafe(24)}"
    expires_at: datetime | None = None
    if expires_in_days is not None:
        expires_at = utcnow() + timedelta(days=expires_in_days)

    credential = _build_product_credential(
        actor=actor,
        grant=grant,
        object_id=object_id,
        release_id=release_id,
        scope_type=scope_type,
        scope_id=scope_id,
        token_type=token_type,
        normalized_name=normalized_name,
        issued_for=issued_for,
        raw_token=raw_token,
        expires_at=expires_at,
    )
    db.add(credential)
    db.flush()
    audit_service.append_audit_event(
        db,
        aggregate_type="token",
        aggregate_id=str(credential.id),
        event_type="token.created",
        actor_ref=_actor_ref(actor),
        owner_principal_id=actor.principal.id,
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
        .where(Credential.product_object_id == object_id)
        .order_by(Credential.id.desc())
    ).all()
    return [_token_metadata(credential) for credential in credentials]


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
        cast(Any, credential).revoked_at = utcnow()
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
            owner_principal_id=actor.principal.id,
            payload={"object_id": object_id},
        )
    return _token_metadata(credential)
