from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.agent_presets import service
from server.modules.agent_presets.schemas import (
    AgentPresetCreateRequest,
    AgentPresetDraftCreateRequest,
    AgentPresetView,
)
from server.modules.authoring.schemas import (
    SkillDraftSealRequest,
    SkillDraftSealResponse,
    SkillDraftView,
    SkillVersionView,
)

router = APIRouter(prefix="/api/v1", tags=["agent-presets"])


def _require_principal(context: AccessContext) -> tuple[int, bool]:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="authoring principal required")
    if not require_any_scope(context, {"api:user", "authoring:write", "skill:write"}):
        raise HTTPException(status_code=403, detail="insufficient scope")
    return context.principal.id, bool(context.user is not None and context.user.role == "maintainer")


@router.post("/agent-presets", response_model=AgentPresetView, status_code=status.HTTP_201_CREATED)
def create_agent_preset(
    payload: AgentPresetCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, _ = _require_principal(context)
    try:
        record = service.create_agent_preset(
            db,
            namespace_id=principal_id,
            actor_principal_id=principal_id,
            payload=payload,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentPresetView.from_model(
        record.spec,
        slug=record.skill.slug,
        display_name=record.skill.display_name,
        summary=record.skill.summary,
    )


@router.post(
    "/agent-presets/{preset_id}/drafts",
    response_model=SkillDraftView,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_preset_draft(
    preset_id: int,
    payload: AgentPresetDraftCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, is_maintainer = _require_principal(context)
    try:
        draft = service.create_agent_preset_draft(
            db,
            preset_id=preset_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            payload=payload,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SkillDraftView.from_model(draft)


@router.post(
    "/agent-preset-drafts/{draft_id}/seal",
    response_model=SkillDraftSealResponse,
    status_code=status.HTTP_201_CREATED,
)
def seal_agent_preset_draft(
    draft_id: int,
    payload: SkillDraftSealRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, is_maintainer = _require_principal(context)
    try:
        draft, skill_version = service.seal_agent_preset_draft(
            db,
            draft_id=draft_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            version=payload.version,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SkillDraftSealResponse(
        version=skill_version.version,
        draft=SkillDraftView.from_model(draft),
        skill_version=SkillVersionView.from_model(skill_version),
    )
