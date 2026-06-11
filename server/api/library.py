from __future__ import annotations

import json
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.auth_guards import (
    build_actor_ref,
    require_user_with_context as _require_library_actor,
    require_principal_context as _require_library_principal,
)
from server.db import get_db
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
from server.modules.access.authn import AccessContext
from server.modules.audit import service as audit_service
from server.modules.release import service as release_service
from server.modules.shares import service as share_service
from server.pagination import (
    PaginationParams,
    create_paginated_response,
    query_pagination_params,
)
from server.ui.library_objects import get_library_object_detail, list_library_objects
from server.ui.library_releases import list_library_releases

router = APIRouter(prefix="/api/v1/library", tags=["library"])


class LibraryTokenCreateRequest(BaseModel):
    token_type: Literal["reader", "publisher"] = "reader"
    label: str | None = Field(default=None, max_length=200)


class LibraryShareCreateRequest(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    temporary_password: str | None = Field(default=None, max_length=200)
    expires_in_days: int = Field(default=7, ge=1, le=365)
    usage_limit: int | None = Field(default=5, ge=1, le=100000)


def _share_actor(context: AccessContext):
    return build_actor_ref(context)


def _require_release_write_context(
    db: Session,
    *,
    actor: AccessContext,
    release_id: int,
) -> tuple[Skill, Principal, str]:
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

    skill = db.get(Skill, release.skill_id)
    if skill is None:
        raise HTTPException(status_code=409, detail="release skill metadata missing")
    owner = db.get(Principal, skill.namespace_id)
    if owner is None:
        raise HTTPException(status_code=409, detail="release owner metadata missing")

    version_label = f"release-{release.id}"
    if release.skill_version_id is not None:
        version = db.get(SkillVersion, release.skill_version_id)
        if version is not None and version.version:
            version_label = version.version

    return skill, owner, version_label


def _require_active_grant_exposure(db: Session, *, release_id: int) -> Exposure:
    try:
        return access_service.require_active_grant_exposure(db, release_id=release_id)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail="active grant visibility required before issuing tokens or share links",
        )


def _build_install_path(*, owner: Principal, skill: Skill, version: str) -> str:
    return f"/api/v1/install/grant/{owner.slug}/{skill.slug}@{version}"


def _token_type_for_scopes(scopes_json: str | None) -> str:
    return access_service.token_type_for_scopes(scopes_json)


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


@router.get("/")
def library_list(
    pagination: PaginationParams = Depends(query_pagination_params),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    """List library objects with pagination.

    Query Parameters:
        skip: Number of items to skip (default: 0, max: 10000)
        limit: Maximum items to return (default: 20, max: 100)
    """
    actor = _require_library_actor(context)
    items, total = list_library_objects(
        db, actor=actor, skip=pagination.skip, limit=pagination.limit
    )

    return create_paginated_response(
        items=items,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{object_id}")
def library_detail(
    object_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_actor(context)
    detail = get_library_object_detail(db, actor=actor, object_id=object_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="object not found")
    return detail


@router.get("/{object_id}/releases")
def library_releases(
    object_id: int,
    pagination: PaginationParams = Depends(query_pagination_params),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    """List releases for a library object with pagination.

    Path Parameters:
        object_id: The library object ID

    Query Parameters:
        skip: Number of items to skip (default: 0, max: 10000)
        limit: Maximum items to return (default: 20, max: 100)
    """
    actor = _require_library_actor(context)
    all_items = list_library_releases(db, actor=actor, object_id=object_id)
    if all_items is None:
        raise HTTPException(status_code=404, detail="object not found")

    # Releases are already scoped to a single object — apply in-memory pagination
    total = len(all_items)
    paginated_items = all_items[pagination.skip : pagination.skip + pagination.limit]

    return create_paginated_response(
        items=paginated_items,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("/releases/{release_id}/tokens", status_code=status.HTTP_201_CREATED)
def issue_library_release_token(
    release_id: int,
    payload: LibraryTokenCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_principal(context)
    skill, _owner, version_label = _require_release_write_context(
        db,
        actor=actor,
        release_id=release_id,
    )
    exposure = _require_active_grant_exposure(db, release_id=release_id)

    grant = AccessGrant(
        exposure_id=exposure.id,
        grant_type="token",
        subject_ref=f"agent://{skill.slug}/{payload.token_type}-{secrets.token_hex(4)}",
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
    audit_service.append_audit_event(
        db,
        aggregate_type="token",
        aggregate_id=str(credential.id),
        event_type="token.created",
        actor_ref=f"principal:{actor.principal.slug}",
        payload={
            "object_id": skill.id,
            "object_name": skill.display_name,
            "release_id": release_id,
            "token_type": payload.token_type,
            "name": payload.label,
        },
    )
    db.commit()

    return {
        "grant_id": grant.id,
        "credential_id": credential.id,
        "token": raw_token,
        "token_type": payload.token_type,
        "label": payload.label,
        "scopes": sorted(scopes),
        "object_name": skill.display_name,
        "release_id": release_id,
        "release_version": version_label,
    }


@router.post(
    "/releases/{release_id}/share-links",
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
    _skill, _owner, version_label = _require_release_write_context(
        db,
        actor=actor,
        release_id=release_id,
    )
    temporary_password = (payload.temporary_password or "").strip() or secrets.token_urlsafe(10)
    try:
        share = share_service.create_share_link(
            db,
            release_id=release_id,
            name=payload.label or "",
            password=temporary_password,
            expires_in_days=payload.expires_in_days,
            max_uses=payload.usage_limit,
            actor=_share_actor(actor),
        )
    except share_service.ShareLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()

    base_url = str(request.base_url).rstrip("/")
    return {
        "share_id": share["grant_id"],
        "credential_id": share["credential_id"],
        "label": payload.label,
        "install_path": share["install_path"],
        "install_url": f"{base_url}{share['install_path']}",
        "temporary_password": temporary_password,
        "expires_at": share["expires_at"],
        "usage_limit": payload.usage_limit,
        "release_id": release_id,
        "release_version": version_label,
    }


@router.post("/tokens/{credential_id}/revoke")
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
        skill, _owner, _version_label = _require_release_write_context(
            db,
            actor=actor,
            release_id=release_id,
        )
        constraints = json.loads(grant.constraints_json or "{}")
        audit_service.append_audit_event(
            db,
            aggregate_type="token",
            aggregate_id=str(credential.id),
            event_type="token.revoked",
            actor_ref=f"principal:{actor.principal.slug}",
            payload={
                "object_id": skill.id,
                "object_name": skill.display_name,
                "release_id": release_id,
                "token_type": _token_type_for_scopes(credential.scopes_json),
                "name": constraints.get("label"),
            },
        )
        db.commit()

    return {
        "credential_id": credential.id,
        "grant_id": grant.id,
        "state": "revoked",
        "release_id": release_id,
    }


@router.post("/share-links/{grant_id}/revoke")
def revoke_library_share_link(
    grant_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_library_principal(context)
    try:
        share = share_service.revoke_share_link(
            db,
            share_id=grant_id,
            actor=_share_actor(actor),
        )
    except share_service.ShareLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except share_service.ShareLinkForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except share_service.ShareLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()

    credentials = db.scalars(
        select(Credential).where(Credential.grant_id == grant_id).order_by(Credential.id.desc())
    ).all()
    return {
        "share_id": share["grant_id"],
        "credential_ids": [credential.id for credential in credentials],
        "state": "revoked",
        "release_id": share["release_id"],
    }
