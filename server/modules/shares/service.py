from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import hash_share_password, verify_password
from server.models import (
    AccessGrant,
    Credential,
    Exposure,
    Principal,
    Skill,
    SkillVersion,
    utcnow,
)
from server.modules.access import service as access_service
from server.modules.audit import service as audit_service
from server.modules.release import service as release_service
from server.modules.shared.actor import ActorRef, actor_ref_label as _actor_ref
from server.modules.shared.formatting import iso_format


class ShareLinkError(Exception):
    pass


class ShareLinkNotFoundError(ShareLinkError):
    pass


class ShareLinkForbiddenError(ShareLinkError):
    pass


class ShareLinkConflictError(ShareLinkError):
    pass


def _json_object(value: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _release_context(db: Session, *, release_id: int, actor: ActorRef | None = None):
    try:
        release = release_service.get_release_or_404(db, release_id)
    except release_service.NotFoundError as exc:
        raise ShareLinkNotFoundError(str(exc)) from exc
    if actor is not None:
        try:
            release_service.assert_release_owner(
                db,
                release,
                principal_id=actor.principal.id,
                is_maintainer=actor.is_maintainer,
            )
        except release_service.ForbiddenError as exc:
            raise ShareLinkForbiddenError(str(exc)) from exc
        except release_service.NotFoundError as exc:
            raise ShareLinkNotFoundError(str(exc)) from exc

    skill = db.get(Skill, release.skill_id)
    if skill is None:
        raise ShareLinkConflictError("release skill metadata missing")
    owner = db.get(Principal, skill.namespace_id)
    if owner is None:
        raise ShareLinkConflictError("release owner metadata missing")

    version_label = f"release-{release.id}"
    if release.skill_version_id is not None:
        version = db.get(SkillVersion, release.skill_version_id)
        if version is not None and version.version:
            version_label = version.version
    return release, skill, owner, version_label


def _active_grant_exposure(db: Session, *, release_id: int) -> Exposure:
    exposure = db.scalar(
        select(Exposure)
        .where(Exposure.release_id == release_id)
        .where(Exposure.audience_type == "grant")
        .where(Exposure.state == "active")
        .where(Exposure.install_mode == "enabled")
        .order_by(Exposure.id.desc())
    )
    if exposure is None:
        raise ShareLinkConflictError(
            "active grant visibility required before issuing share links"
        )
    return exposure


def _release_id_for_grant(db: Session, *, grant: AccessGrant) -> int:
    exposure = db.get(Exposure, grant.exposure_id)
    if exposure is None or exposure.audience_type != "grant":
        raise ShareLinkNotFoundError("share link not found")
    return int(exposure.release_id)


def _install_path(*, owner: Principal, skill: Skill, version: str) -> str:
    return f"/api/v1/install/grant/{owner.slug}/{skill.slug}@{version}"


def _share_credentials(db: Session, *, grant_id: int) -> list[Credential]:
    return db.scalars(
        select(Credential).where(Credential.grant_id == grant_id).order_by(Credential.id.desc())
    ).all()


def _password_credential(credentials: list[Credential]) -> Credential | None:
    for credential in credentials:
        if credential.type == "share_password":
            return credential
    return None


def _share_state(grant: AccessGrant, constraints: dict[str, Any]) -> str:
    if grant.state and grant.state != "active":
        return grant.state
    expires_at = constraints.get("expires_at")
    if isinstance(expires_at, str) and expires_at:
        try:
            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None and _as_aware(parsed) <= utcnow():
            return "expired"
    max_uses = constraints.get("max_uses", constraints.get("usage_limit"))
    used_count = int(constraints.get("used_count", constraints.get("usage_count") or 0))
    if max_uses is not None and used_count >= int(max_uses):
        return "exhausted"
    return "active"


def _share_link_payload(
    db: Session,
    grant: AccessGrant,
    *,
    install_path: str | None = None,
) -> dict:
    release_id = _release_id_for_grant(db, grant=grant)
    constraints = _json_object(grant.constraints_json)
    credentials = _share_credentials(db, grant_id=grant.id)
    password_credential = _password_credential(credentials)
    used_count = int(constraints.get("used_count", constraints.get("usage_count") or 0))
    max_uses = constraints.get("max_uses", constraints.get("usage_limit"))
    expires_at = constraints.get("expires_at")
    payload = {
        "id": grant.id,
        "grant_id": grant.id,
        "credential_id": password_credential.id if password_credential is not None else None,
        "release_id": release_id,
        "name": constraints.get("name") or constraints.get("label") or "",
        "slug": grant.subject_ref.removeprefix("share://"),
        "has_password": password_credential is not None,
        "expires_at": expires_at.replace("+00:00", "Z") if isinstance(expires_at, str) else None,
        "max_uses": int(max_uses) if max_uses is not None else None,
        "used_count": used_count,
        "state": _share_state(grant, constraints),
        "created_at": iso_format(grant.created_at),
    }
    if install_path is not None:
        payload["install_path"] = install_path
    return payload


def _get_share_grant(db: Session, *, share_id: int) -> AccessGrant:
    grant = db.get(AccessGrant, share_id)
    if grant is None or grant.grant_type != "link":
        raise ShareLinkNotFoundError("share link not found")
    return grant


def create_share_link(
    db: Session,
    *,
    release_id: int,
    name: str,
    password: str | None,
    expires_in_days: int | None,
    max_uses: int | None,
    actor: ActorRef,
) -> dict:
    _release, skill, owner, version_label = _release_context(
        db,
        release_id=release_id,
        actor=actor,
    )
    exposure = _active_grant_exposure(db, release_id=release_id)
    raw_password = str(password or "").strip()
    expires_at = utcnow() + timedelta(days=expires_in_days) if expires_in_days is not None else None
    constraints: dict[str, Any] = {
        "name": str(name or "").strip(),
        "used_count": 0,
    }
    if expires_at is not None:
        constraints["expires_at"] = expires_at.isoformat()
    if max_uses is not None:
        constraints["max_uses"] = max_uses

    grant = AccessGrant(
        exposure_id=exposure.id,
        grant_type="link",
        subject_ref=f"share://{skill.slug}/{secrets.token_urlsafe(12)}",
        constraints_json=json.dumps(constraints, ensure_ascii=False),
        state="active",
        created_by_principal_id=actor.principal.id,
    )
    db.add(grant)
    db.flush()

    credential_secret = raw_password or secrets.token_urlsafe(24)
    # Use bcrypt for user-chosen passwords (brute-force resistant), SHA-256 for random tokens
    if raw_password:
        hashed_secret = hash_share_password(raw_password)
        credential_type = "share_password"
    else:
        hashed_secret = access_service.hash_token(credential_secret)
        credential_type = "share_secret"
    credential = Credential(
        principal_id=None,
        grant_id=grant.id,
        type=credential_type,
        hashed_secret=hashed_secret,
        scopes_json=access_service.encode_scopes({"artifact:download"}),
        resource_selector_json=json.dumps({"release_scope": "grant-bound"}, ensure_ascii=False),
        expires_at=expires_at,
        created_at=utcnow(),
    )
    db.add(credential)
    db.flush()

    audit_service.append_audit_event(
        db,
        aggregate_type="share_link",
        aggregate_id=str(grant.id),
        event_type="share_link.created",
        actor_ref=_actor_ref(actor),
        payload={
            "release_id": release_id,
            "object_id": skill.id,
            "name": constraints["name"],
        },
    )
    return _share_link_payload(
        db,
        grant,
        install_path=_install_path(
            owner=owner,
            skill=skill,
            version=version_label,
        ),
    )


def list_share_links(db: Session, *, release_id: int, actor: ActorRef) -> list[dict]:
    _release_context(db, release_id=release_id, actor=actor)
    exposure = _active_grant_exposure(db, release_id=release_id)
    shares = db.scalars(
        select(AccessGrant)
        .where(AccessGrant.exposure_id == exposure.id)
        .where(AccessGrant.grant_type == "link")
        .order_by(AccessGrant.id.desc())
    ).all()
    return [_share_link_payload(db, share) for share in shares]


def revoke_share_link(db: Session, *, share_id: int, actor: ActorRef) -> dict:
    grant = _get_share_grant(db, share_id=share_id)
    release_id = _release_id_for_grant(db, grant=grant)
    _release_context(db, release_id=release_id, actor=actor)
    if grant.state != "revoked":
        grant.state = "revoked"
        db.add(grant)
        revoked_at = utcnow()
        for credential in _share_credentials(db, grant_id=grant.id):
            if credential.revoked_at is None:
                credential.revoked_at = revoked_at
                db.add(credential)
        audit_service.append_audit_event(
            db,
            aggregate_type="share_link",
            aggregate_id=str(grant.id),
            event_type="share_link.revoked",
            actor_ref=_actor_ref(actor),
            payload={"release_id": release_id},
        )
    return _share_link_payload(db, grant)


def resolve_share_link(db: Session, *, share_id: int, password: str | None) -> dict:
    grant = _get_share_grant(db, share_id=share_id)
    payload = _share_link_payload(db, grant)
    if payload["state"] != "active":
        raise ShareLinkConflictError(payload["state"])

    credentials = _share_credentials(db, grant_id=grant.id)
    password_credential = _password_credential(credentials)
    if password_credential is not None:
        stored_hash = password_credential.hashed_secret or ""
        # Support both bcrypt hashes (new) and SHA-256 hashes (legacy)
        if stored_hash.startswith("$2"):
            if not verify_password(password or "", stored_hash):
                raise ShareLinkForbiddenError("share link password is invalid")
        elif not access_service.token_matches_hash(password or "", stored_hash):
            raise ShareLinkForbiddenError("share link password is invalid")

    release_id = _release_id_for_grant(db, grant=grant)
    _release, skill, owner, version_label = _release_context(
        db,
        release_id=release_id,
    )
    constraints = _json_object(grant.constraints_json)
    constraints["used_count"] = (
        int(constraints.get("used_count", constraints.get("usage_count") or 0)) + 1
    )
    constraints["usage_count"] = constraints["used_count"]
    grant.constraints_json = json.dumps(constraints, ensure_ascii=False)
    db.add(grant)
    db.flush()
    audit_service.append_audit_event(
        db,
        aggregate_type="share_link",
        aggregate_id=str(grant.id),
        event_type="share_link.resolved",
        actor_ref="anonymous",
        payload={"release_id": release_id, "object_id": skill.id},
    )
    return _share_link_payload(
        db,
        grant,
        install_path=_install_path(
            owner=owner,
            skill=skill,
            version=version_label,
        ),
    )
