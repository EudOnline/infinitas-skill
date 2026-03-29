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
    SkillDraftCreateRequest,
    SkillDraftPatchRequest,
    SkillDraftSealRequest,
    SkillDraftSealResponse,
    SkillDraftView,
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


@router.get("/skills/{skill_id}", response_model=SkillView)
def get_skill(
    skill_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_authoring_principal(context)
    try:
        skill = service.get_skill_or_404(db, skill_id)
        service.assert_namespace_owner(skill, principal_id=principal_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillView.from_model(skill)


@router.post("/skills/{skill_id}/drafts", response_model=SkillDraftView, status_code=status.HTTP_201_CREATED)
def create_draft(
    skill_id: int,
    payload: SkillDraftCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_authoring_principal(context)
    try:
        draft = service.create_draft(
            db,
            skill_id=skill_id,
            actor_principal_id=principal_id,
            payload=payload,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillDraftView.from_model(draft)


@router.patch("/drafts/{draft_id}", response_model=SkillDraftView)
def patch_draft(
    draft_id: int,
    payload: SkillDraftPatchRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_authoring_principal(context)
    try:
        draft = service.patch_draft(
            db,
            draft_id=draft_id,
            actor_principal_id=principal_id,
            payload=payload,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillDraftView.from_model(draft)


@router.post("/drafts/{draft_id}/seal", response_model=SkillDraftSealResponse, status_code=status.HTTP_201_CREATED)
def seal_draft(
    draft_id: int,
    payload: SkillDraftSealRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_authoring_principal(context)
    try:
        draft, skill_version = service.seal_draft(
            db,
            draft_id=draft_id,
            actor_principal_id=principal_id,
            version=payload.version,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SkillDraftSealResponse(
        version=skill_version.version,
        draft=SkillDraftView.from_model(draft),
        skill_version=SkillVersionView.from_model(skill_version),
    )
