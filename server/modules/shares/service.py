from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import Principal, RegistryObject, ShareLink, SkillVersion, utcnow
from server.modules.access import service as access_service
from server.modules.audit import service as audit_service
from server.modules.release import service as release_service


class ShareLinkError(Exception):
    pass


class ShareLinkNotFoundError(ShareLinkError):
    pass


class ShareLinkForbiddenError(ShareLinkError):
    pass


class ShareLinkConflictError(ShareLinkError):
    pass


@dataclass(frozen=True)
class ActorRef:
    principal: Principal
    is_maintainer: bool


def _actor_ref(actor: ActorRef) -> str:
    return f"principal:{actor.principal.slug}"


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

    registry_object = db.get(RegistryObject, release.registry_object_id)
    if registry_object is None:
        raise ShareLinkConflictError("release object metadata missing")
    owner = db.get(Principal, registry_object.namespace_id)
    if owner is None:
        raise ShareLinkConflictError("release owner metadata missing")

    version_label = f"release-{release.id}"
    if release.skill_version_id is not None:
        version = db.get(SkillVersion, release.skill_version_id)
        if version is not None and version.version:
            version_label = version.version
    return release, registry_object, owner, version_label


def _install_path(*, owner: Principal, registry_object: RegistryObject, version: str) -> str:
    return f"/api/v1/install/grant/{owner.slug}/{registry_object.slug}@{version}"


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def share_link_payload(
    share: ShareLink,
    *,
    install_path: str | None = None,
) -> dict:
    now = utcnow()
    state = "active"
    if share.revoked_at is not None:
        state = "revoked"
    elif share.expires_at is not None and _as_aware(share.expires_at) <= now:
        state = "expired"
    elif share.max_uses is not None and share.used_count >= share.max_uses:
        state = "exhausted"
    payload = {
        "id": share.id,
        "release_id": share.release_id,
        "name": share.name,
        "slug": share.slug,
        "has_password": bool(share.password_hash),
        "expires_at": (
            share.expires_at.isoformat().replace("+00:00", "Z")
            if share.expires_at is not None
            else None
        ),
        "max_uses": share.max_uses,
        "used_count": share.used_count,
        "state": state,
        "created_at": share.created_at.isoformat().replace("+00:00", "Z"),
    }
    if install_path is not None:
        payload["install_path"] = install_path
    return payload


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
    _release, registry_object, owner, version_label = _release_context(
        db,
        release_id=release_id,
        actor=actor,
    )
    raw_password = str(password or "").strip()
    expires_at = utcnow() + timedelta(days=expires_in_days) if expires_in_days is not None else None
    share = ShareLink(
        release_id=release_id,
        name=str(name or "").strip(),
        slug=secrets.token_urlsafe(12),
        password_hash=access_service.hash_token(raw_password) if raw_password else "",
        expires_at=expires_at,
        max_uses=max_uses,
        used_count=0,
        created_by_principal_id=actor.principal.id,
        created_at=utcnow(),
    )
    db.add(share)
    db.flush()
    audit_service.append_audit_event(
        db,
        aggregate_type="share_link",
        aggregate_id=str(share.id),
        event_type="share_link.created",
        actor_ref=_actor_ref(actor),
        payload={"release_id": release_id, "object_id": registry_object.id, "name": share.name},
    )
    return share_link_payload(
        share,
        install_path=_install_path(
            owner=owner,
            registry_object=registry_object,
            version=version_label,
        ),
    )


def list_share_links(db: Session, *, release_id: int, actor: ActorRef) -> list[dict]:
    _release_context(db, release_id=release_id, actor=actor)
    shares = db.scalars(
        select(ShareLink)
        .where(ShareLink.release_id == release_id)
        .order_by(ShareLink.id.desc())
    ).all()
    return [share_link_payload(share) for share in shares]


def revoke_share_link(db: Session, *, share_id: int, actor: ActorRef) -> dict:
    share = db.get(ShareLink, share_id)
    if share is None:
        raise ShareLinkNotFoundError("share link not found")
    _release_context(db, release_id=share.release_id, actor=actor)
    if share.revoked_at is None:
        share.revoked_at = utcnow()
        db.add(share)
        audit_service.append_audit_event(
            db,
            aggregate_type="share_link",
            aggregate_id=str(share.id),
            event_type="share_link.revoked",
            actor_ref=_actor_ref(actor),
            payload={"release_id": share.release_id},
        )
    return share_link_payload(share)


def resolve_share_link(db: Session, *, share_id: int, password: str | None) -> dict:
    share = db.get(ShareLink, share_id)
    if share is None:
        raise ShareLinkNotFoundError("share link not found")
    payload = share_link_payload(share)
    if payload["state"] != "active":
        raise ShareLinkConflictError(payload["state"])
    if share.password_hash and not access_service.token_matches_hash(
        password or "",
        share.password_hash,
    ):
        raise ShareLinkForbiddenError("share link password is invalid")

    _release, registry_object, owner, version_label = _release_context(
        db,
        release_id=share.release_id,
    )
    share.used_count += 1
    db.add(share)
    db.flush()
    audit_service.append_audit_event(
        db,
        aggregate_type="share_link",
        aggregate_id=str(share.id),
        event_type="share_link.resolved",
        actor_ref="anonymous",
        payload={"release_id": share.release_id, "object_id": registry_object.id},
    )
    return share_link_payload(
        share,
        install_path=_install_path(
            owner=owner,
            registry_object=registry_object,
            version=version_label,
        ),
    )
