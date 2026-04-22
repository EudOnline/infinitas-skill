from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.jobs import enqueue_job, has_active_job
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.agent_presets import service
from server.modules.agent_presets.schemas import (
    AgentPresetCreateRequest,
    AgentPresetDraftCreateRequest,
    AgentPresetView,
)
from server.modules.authoring import service as authoring_service
from server.modules.authoring.schemas import (
    SkillDraftSealRequest,
    SkillDraftSealResponse,
    SkillDraftView,
    SkillVersionView,
)
from server.modules.release import service as release_service
from server.modules.release.materializer import release_requires_materialization
from server.modules.release.schemas import ReleaseView
from server.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["agent-presets"])


def _require_principal(context: AccessContext) -> tuple[int, bool]:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="authoring principal required")
    if not require_any_scope(context, {"api:user", "authoring:write", "skill:write"}):
        raise HTTPException(status_code=403, detail="insufficient scope")
    is_maintainer = bool(context.user is not None and context.user.role == "maintainer")
    return context.principal.id, is_maintainer


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
    except authoring_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except authoring_service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentPresetView.from_model(
        record.spec,
        slug=record.skill.slug,
        display_name=record.skill.display_name,
        summary=record.skill.summary,
    )


@router.get("/agent-presets/{preset_id}", response_model=AgentPresetView)
def get_agent_preset(
    preset_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, is_maintainer = _require_principal(context)
    try:
        record = service.get_agent_preset_or_404(db, preset_id)
        authoring_service.assert_namespace_owner(
            record.skill,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except authoring_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except authoring_service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
    except authoring_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except authoring_service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
    except authoring_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except authoring_service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SkillDraftSealResponse(
        version=skill_version.version,
        draft=SkillDraftView.from_model(draft),
        skill_version=SkillVersionView.from_model(skill_version),
    )


@router.post(
    "/agent-preset-versions/{version_id}/releases",
    response_model=ReleaseView,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_preset_release(
    version_id: int,
    response: Response,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, is_maintainer = _require_principal(context)
    user = context.user
    if user is None:
        raise HTTPException(
            status_code=403,
            detail="release actor must resolve to a user principal",
        )
    try:
        release, created = release_service.create_or_get_release(
            db,
            version_id=version_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except release_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except release_service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except release_service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if created:
        try:
            enqueue_job(
                db,
                kind="materialize_release",
                payload={"release_id": release.id},
                requested_by=user,
                note=f"materialize release {release.id}",
                commit=False,
            )
            db.commit()
            db.refresh(release)
        except Exception:
            db.rollback()
            db.refresh(release)
    else:
        settings = get_settings()
        if release_requires_materialization(
            db,
            release_id=release.id,
            artifact_root=settings.artifact_path,
            repo_root=settings.repo_path,
        ) and not has_active_job(
            db,
            kind="materialize_release",
            release_id=release.id,
            statuses=("queued", "running"),
        ):
            enqueue_job(
                db,
                kind="materialize_release",
                payload={"release_id": release.id},
                requested_by=user,
                note=f"rematerialize release {release.id}",
                commit=False,
            )
            db.commit()
            db.refresh(release)
        response.status_code = status.HTTP_200_OK
    return ReleaseView.from_model(release)
