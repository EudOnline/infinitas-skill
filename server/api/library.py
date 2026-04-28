from __future__ import annotations

import json
import secrets
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.models import (
    AccessGrant,
    Credential,
    Exposure,
    Principal,
    RegistryObject,
    SkillVersion,
    utcnow,
)
from server.modules.access import service as access_service
from server.modules.access.authn import AccessContext
from server.modules.release import service as release_service
from server.ui import library as library_ui

router = APIRouter(tags=["library"])


def _require_library_actor(context: AccessContext) -> AccessContext:
    if context.user is None:
        raise HTTPException(status_code=403, detail="user session required")
    if context.user.role not in {"maintainer", "contributor"}:
        raise HTTPException(status_code=403, detail="insufficient role")
    return context


class LibraryTokenCreateRequest(BaseModel):
    token_type: Literal["reader", "publisher"] = "reader"
    label: str | None = Field(default=None, max_length=200)


class LibraryShareCreateRequest(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    temporary_password: str | None = Field(default=None, max_length=200)
    expires_in_days: int = Field(default=7, ge=1, le=365)
    usage_limit: int | None = Field(default=5, ge=1, le=100000)


def _require_library_principal(context: AccessContext) -> AccessContext:
    actor = _require_library_actor(context)
    if actor.principal is None:
        raise HTTPException(status_code=403, detail="principal required")
    return actor


def _require_release_write_context(
    db: Session,
    *,
    actor: AccessContext,
    release_id: int,
) -> tuple[RegistryObject, Principal, str]:
    try:
        release = release_service.get_release_or_404(db, release_id)
    except release_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        release_service.assert_release_owner(
            db,
            release,
            principal_id=actor.principal.id,
            is_maintainer=actor.user is not None and actor.user.role == "maintainer",
        )
    except release_service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except release_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    registry_object = db.get(RegistryObject, release.registry_object_id)
    if registry_object is None:
        raise HTTPException(status_code=409, detail="release object metadata missing")
    owner = db.get(Principal, registry_object.namespace_id)
    if owner is None:
        raise HTTPException(status_code=409, detail="release owner metadata missing")

    version_label = f"release-{release.id}"
    if release.skill_version_id is not None:
        version = db.get(SkillVersion, release.skill_version_id)
        if version is not None and version.version:
            version_label = version.version

    return registry_object, owner, version_label


def _require_active_grant_exposure(db: Session, *, release_id: int) -> Exposure:
    exposure = db.scalar(
        select(Exposure)
        .where(Exposure.release_id == release_id)
        .where(Exposure.audience_type == "grant")
        .where(Exposure.state == "active")
        .where(Exposure.install_mode == "enabled")
        .order_by(Exposure.id.desc())
    )
    if exposure is None:
        raise HTTPException(
            status_code=409,
            detail="active grant visibility required before issuing tokens or share links",
        )
    return exposure


def _build_install_path(*, owner: Principal, registry_object: RegistryObject, version: str) -> str:
    return f"/api/v1/install/grant/{owner.slug}/{registry_object.slug}@{version}"


def _require_grant(db: Session, *, grant_id: int, grant_type: str | None = None) -> AccessGrant:
    grant = db.get(AccessGrant, grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="grant not found")
    if grant_type is not None and grant.grant_type != grant_type:
        raise HTTPException(status_code=404, detail="grant not found")
    return grant


def _release_id_for_grant(db: Session, *, grant: AccessGrant) -> int:
    exposure = db.get(Exposure, grant.exposure_id)
    if exposure is None:
        raise HTTPException(status_code=404, detail="exposure not found")
    return int(exposure.release_id)


@router.get("/api/library")
def library_list(
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_actor(context)
    items = library_ui.list_library_objects(db, actor=actor)
    return {"items": items, "total": len(items)}


@router.get("/api/library/{object_id}")
def library_detail(
    object_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_actor(context)
    detail = library_ui.get_library_object_detail(db, actor=actor, object_id=object_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="object not found")
    return detail


@router.get("/api/library/{object_id}/releases")
def library_releases(
    object_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_actor(context)
    items = library_ui.list_library_releases(db, actor=actor, object_id=object_id)
    if items is None:
        raise HTTPException(status_code=404, detail="object not found")
    return {"items": items, "total": len(items)}


@router.post("/api/library/releases/{release_id}/tokens", status_code=status.HTTP_201_CREATED)
def issue_library_release_token(
    release_id: int,
    payload: LibraryTokenCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_principal(context)
    registry_object, _owner, version_label = _require_release_write_context(
        db,
        actor=actor,
        release_id=release_id,
    )
    exposure = _require_active_grant_exposure(db, release_id=release_id)

    grant = AccessGrant(
        exposure_id=exposure.id,
        grant_type="token",
        subject_ref=f"agent://{registry_object.slug}/{payload.token_type}-{secrets.token_hex(4)}",
        constraints_json=json.dumps({"label": payload.label} if payload.label else {}),
        state="active",
        created_by_principal_id=actor.principal.id,
    )
    db.add(grant)
    db.flush()

    scopes = {"artifact:download"}
    if payload.token_type == "publisher":
        scopes.add("release:write")
    raw_token, credential = access_service.create_grant_token(
        db,
        grant=grant,
        scopes=scopes,
    )
    db.commit()

    return {
        "grant_id": grant.id,
        "credential_id": credential.id,
        "token": raw_token,
        "token_type": payload.token_type,
        "label": payload.label,
        "scopes": sorted(scopes),
        "object_name": registry_object.display_name,
        "release_id": release_id,
        "release_version": version_label,
    }


@router.post(
    "/api/library/releases/{release_id}/share-links",
    status_code=status.HTTP_201_CREATED,
)
def create_library_release_share_link(
    release_id: int,
    payload: LibraryShareCreateRequest,
    request: Request,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_principal(context)
    registry_object, owner, version_label = _require_release_write_context(
        db,
        actor=actor,
        release_id=release_id,
    )
    exposure = _require_active_grant_exposure(db, release_id=release_id)

    expires_at = utcnow() + timedelta(days=payload.expires_in_days)
    temporary_password = (payload.temporary_password or "").strip() or secrets.token_urlsafe(10)
    constraints = {
        "expires_at": expires_at.isoformat(),
        "temporary_password": temporary_password,
        "usage_count": 0,
    }
    if payload.label:
        constraints["label"] = payload.label
    if payload.usage_limit is not None:
        constraints["usage_limit"] = payload.usage_limit

    grant = AccessGrant(
        exposure_id=exposure.id,
        grant_type="link",
        subject_ref=f"share://{registry_object.slug}/{secrets.token_hex(4)}",
        constraints_json=json.dumps(constraints, ensure_ascii=False),
        state="active",
        created_by_principal_id=actor.principal.id,
    )
    db.add(grant)
    db.flush()

    credential = Credential(
        principal_id=None,
        grant_id=grant.id,
        type="share_password",
        hashed_secret=access_service.hash_token(temporary_password),
        scopes_json=access_service.encode_scopes({"artifact:download"}),
        resource_selector_json=json.dumps({"release_scope": "grant-bound"}, ensure_ascii=False),
        expires_at=expires_at,
        created_at=utcnow(),
    )
    db.add(credential)
    db.commit()

    install_path = _build_install_path(
        owner=owner,
        registry_object=registry_object,
        version=version_label,
    )
    base_url = str(request.base_url).rstrip("/")
    return {
        "share_id": grant.id,
        "credential_id": credential.id,
        "label": payload.label,
        "install_path": install_path,
        "install_url": f"{base_url}{install_path}",
        "temporary_password": temporary_password,
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "usage_limit": payload.usage_limit,
        "release_id": release_id,
        "release_version": version_label,
    }


@router.post("/api/library/tokens/{credential_id}/revoke")
def revoke_library_token(
    credential_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_principal(context)
    credential = db.get(Credential, credential_id)
    if credential is None or credential.grant_id is None:
        raise HTTPException(status_code=404, detail="token not found")

    grant = _require_grant(db, grant_id=credential.grant_id, grant_type="token")
    release_id = _release_id_for_grant(db, grant=grant)
    _require_release_write_context(db, actor=actor, release_id=release_id)

    if credential.revoked_at is None:
        credential.revoked_at = utcnow()
        db.add(credential)
        db.commit()

    return {
        "credential_id": credential.id,
        "grant_id": grant.id,
        "state": "revoked",
        "release_id": release_id,
    }


@router.post("/api/library/share-links/{grant_id}/revoke")
def revoke_library_share_link(
    grant_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_principal(context)
    grant = _require_grant(db, grant_id=grant_id, grant_type="link")
    release_id = _release_id_for_grant(db, grant=grant)
    _require_release_write_context(db, actor=actor, release_id=release_id)

    if grant.state != "revoked":
        grant.state = "revoked"
        db.add(grant)

    credentials = db.scalars(
        select(Credential).where(Credential.grant_id == grant.id).order_by(Credential.id.desc())
    ).all()
    revoked_at = utcnow()
    for credential in credentials:
        if credential.revoked_at is None:
            credential.revoked_at = revoked_at
            db.add(credential)
    db.commit()

    return {
        "share_id": grant.id,
        "credential_ids": [credential.id for credential in credentials],
        "state": "revoked",
        "release_id": release_id,
    }
