from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.authoring import service
from server.modules.authoring.schemas import (
    SkillCreateRequest,
    SkillVersionCreateRequest,
    SkillVersionView,
    SkillView,
)

router = APIRouter(prefix="/api/v1", tags=["authoring"])


def _require_authoring_principal(context: AccessContext) -> int:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="authoring principal required")
    if not require_any_scope(context, {"api:user", "authoring:write", "skill:write"}):
        raise HTTPException(status_code=403, detail="insufficient scope")
    return context.principal.id


@router.post("/skills", response_model=SkillView, status_code=status.HTTP_201_CREATED)
def create_skill(
    payload: SkillCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_authoring_principal(context)
    try:
        skill = service.create_skill(
            db,
            namespace_id=principal_id,
            actor_principal_id=principal_id,
            payload=payload,
        )
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SkillView.from_model(skill)


@router.post(
    "/skills/{skill_id}/versions",
    response_model=SkillVersionView,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    skill_id: int,
    payload: SkillVersionCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_authoring_principal(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        skill_version = service.create_skill_version_snapshot(
            db,
            skill_id=skill_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            version=payload.version,
            content_mode=payload.content_mode,
            content_ref=payload.content_ref,
            content_upload_token=payload.content_upload_token,
            metadata=payload.metadata,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillVersionView.from_model(skill_version)


@router.get("/skills/{skill_id}", response_model=SkillView)
def get_skill(
    skill_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_authoring_principal(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        skill = service.get_skill_or_404(db, skill_id)
        service.assert_namespace_owner(
            db,
            skill,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillView.from_model(skill)


