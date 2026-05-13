from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.jobs import enqueue_job, has_active_job
from server.models import AgentCodeSpec, AgentPresetSpec, RegistryObject, Skill
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.agent_codes import service as agent_code_service
from server.modules.agent_codes.schemas import AgentCodeCreateRequest, AgentCodeDraftCreateRequest
from server.modules.agent_presets import service as agent_preset_service
from server.modules.agent_presets.schemas import (
    AgentPresetCreateRequest,
    AgentPresetDraftCreateRequest,
)
from server.modules.authoring import service as authoring_service
from server.modules.authoring.schemas import SkillCreateRequest
from server.modules.release import service as release_service
from server.modules.release.materializer import release_requires_materialization
from server.settings import get_settings

router = APIRouter(tags=["publish"])


class PublishObjectRequest(BaseModel):
    kind: Literal["skill", "agent_preset", "agent_code"] = "skill"
    display_name: str = Field(min_length=1, max_length=200)
    summary: str = ""
    runtime_family: str = "openclaw"
    supported_memory_modes: list[str] = Field(default_factory=lambda: ["none"])
    default_memory_mode: str = "none"
    pinned_skill_dependencies: list[str] = Field(default_factory=list)
    language: str = "python"
    entrypoint: str = "main.py"


class PublishReleaseRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    content_ref: str = ""
    metadata: dict = Field(default_factory=dict)
    prompt: str = ""
    model: str = ""
    tools: list[str] = Field(default_factory=list)


def _require_actor(context: AccessContext) -> tuple[int, bool]:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="authoring principal required")
    if not require_any_scope(context, {"api:user", "authoring:write", "skill:write"}):
        raise HTTPException(status_code=403, detail="insufficient scope")
    is_maintainer = bool(context.user is not None and context.user.role == "maintainer")
    return context.principal.id, is_maintainer


def _object_payload(registry_object: RegistryObject, *, backing_id: int | None = None) -> dict:
    payload = {
        "id": registry_object.id,
        "kind": registry_object.kind,
        "slug": registry_object.slug,
        "display_name": registry_object.display_name,
        "summary": registry_object.summary,
        "status": registry_object.status,
    }
    if backing_id is not None:
        payload["backing_id"] = backing_id
    return payload


def _find_existing_object(
    db: Session,
    *,
    namespace_id: int,
    kind: str,
    slug: str,
) -> RegistryObject | None:
    return db.scalar(
        select(RegistryObject)
        .where(RegistryObject.namespace_id == namespace_id)
        .where(RegistryObject.kind == kind)
        .where(RegistryObject.slug == slug)
    )


@router.put("/api/publish/objects/{slug}")
def upsert_publish_object(
    slug: str,
    payload: PublishObjectRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, _is_maintainer = _require_actor(context)
    existing = _find_existing_object(
        db,
        namespace_id=principal_id,
        kind=payload.kind,
        slug=slug,
    )
    if existing is not None:
        existing.display_name = payload.display_name
        existing.summary = payload.summary
        db.add(existing)
        db.commit()
        return _object_payload(existing, backing_id=_backing_id_for_object(db, existing))

    try:
        if payload.kind == "skill":
            skill = authoring_service.create_skill(
                db,
                namespace_id=principal_id,
                actor_principal_id=principal_id,
                payload=SkillCreateRequest(
                    slug=slug,
                    display_name=payload.display_name,
                    summary=payload.summary,
                ),
            )
            registry_object = db.get(RegistryObject, skill.registry_object_id)
            return _object_payload(registry_object, backing_id=skill.id)
        if payload.kind == "agent_preset":
            record = agent_preset_service.create_agent_preset(
                db,
                namespace_id=principal_id,
                actor_principal_id=principal_id,
                payload=AgentPresetCreateRequest(
                    slug=slug,
                    display_name=payload.display_name,
                    summary=payload.summary,
                    runtime_family=payload.runtime_family,
                    supported_memory_modes=payload.supported_memory_modes,
                    default_memory_mode=payload.default_memory_mode,
                    pinned_skill_dependencies=payload.pinned_skill_dependencies,
                ),
            )
            return _object_payload(record.registry_object, backing_id=record.spec.id)
        record = agent_code_service.create_agent_code(
            db,
            namespace_id=principal_id,
            actor_principal_id=principal_id,
            payload=AgentCodeCreateRequest(
                slug=slug,
                display_name=payload.display_name,
                summary=payload.summary,
                runtime_family=payload.runtime_family,
                language=payload.language,
                entrypoint=payload.entrypoint,
            ),
        )
        return _object_payload(record.registry_object, backing_id=record.spec.id)
    except authoring_service.AuthoringError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _backing_id_for_object(db: Session, registry_object: RegistryObject) -> int | None:
    if registry_object.kind == "skill":
        skill = db.scalar(select(Skill).where(Skill.registry_object_id == registry_object.id))
        return skill.id if skill is not None else None
    if registry_object.kind == "agent_preset":
        spec = db.scalar(
            select(AgentPresetSpec).where(AgentPresetSpec.registry_object_id == registry_object.id)
        )
        return spec.id if spec is not None else None
    spec = db.scalar(
        select(AgentCodeSpec).where(AgentCodeSpec.registry_object_id == registry_object.id)
    )
    return spec.id if spec is not None else None


def _skill_for_object(db: Session, registry_object: RegistryObject) -> Skill:
    skill = db.scalar(select(Skill).where(Skill.registry_object_id == registry_object.id))
    if skill is None:
        raise HTTPException(status_code=404, detail="object backing skill not found")
    return skill


def _create_version_for_object(
    db: Session,
    *,
    registry_object: RegistryObject,
    payload: PublishReleaseRequest,
    principal_id: int,
    is_maintainer: bool,
) -> int:
    skill = _skill_for_object(db, registry_object)
    if registry_object.kind == "skill":
        version = authoring_service.create_skill_version_snapshot(
            db,
            skill_id=skill.id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            version=payload.version,
            content_ref=payload.content_ref,
            metadata=payload.metadata,
        )
        return version.id

    if registry_object.kind == "agent_preset":
        spec = db.scalar(
            select(AgentPresetSpec).where(AgentPresetSpec.registry_object_id == registry_object.id)
        )
        if spec is None:
            raise HTTPException(status_code=404, detail="agent preset backing spec not found")
        version = agent_preset_service.create_agent_preset_version_snapshot(
            db,
            preset_id=spec.id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            payload=AgentPresetDraftCreateRequest(
                prompt=payload.prompt,
                model=payload.model,
                tools=payload.tools,
            ),
            version=payload.version,
        )
        return version.id

    spec = db.scalar(
        select(AgentCodeSpec).where(AgentCodeSpec.registry_object_id == registry_object.id)
    )
    if spec is None:
        raise HTTPException(status_code=404, detail="agent code backing spec not found")
    version = agent_code_service.create_agent_code_version_snapshot(
        db,
        code_id=spec.id,
        actor_principal_id=principal_id,
        is_maintainer=is_maintainer,
        payload=AgentCodeDraftCreateRequest(content_ref=payload.content_ref),
        version=payload.version,
    )
    return version.id


def _enqueue_materialization(db: Session, *, release_id: int, context: AccessContext) -> None:
    if context.user is None:
        return
    enqueue_job(
        db,
        kind="materialize_release",
        payload={"release_id": release_id},
        requested_by=context.user,
        note=f"materialize release {release_id}",
        commit=False,
    )


@router.post("/api/publish/objects/{object_id}/releases", status_code=status.HTTP_201_CREATED)
def publish_object_release(
    object_id: int,
    payload: PublishReleaseRequest,
    response: Response,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, is_maintainer = _require_actor(context)
    registry_object = db.get(RegistryObject, object_id)
    if registry_object is None:
        raise HTTPException(status_code=404, detail="object not found")
    if not is_maintainer and registry_object.namespace_id != principal_id:
        raise HTTPException(status_code=403, detail="object namespace access denied")
    try:
        version_id = _create_version_for_object(
            db,
            registry_object=registry_object,
            payload=payload,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
        release, created = release_service.create_or_get_release(
            db,
            version_id=version_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except authoring_service.AuthoringError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except release_service.ReleaseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if created:
        _enqueue_materialization(db, release_id=release.id, context=context)
    else:
        response.status_code = status.HTTP_200_OK
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
            _enqueue_materialization(db, release_id=release.id, context=context)
    db.commit()
    db.refresh(release)
    return _publish_status_payload(
        registry_object=registry_object,
        release_id=release.id,
        release_state=release.state,
        version=payload.version,
    )


def _publish_status_payload(
    *,
    registry_object: RegistryObject,
    release_id: int,
    release_state: str,
    version: str,
) -> dict:
    return {
        "object_id": registry_object.id,
        "object_kind": registry_object.kind,
        "object_slug": registry_object.slug,
        "release_id": release_id,
        "release_state": release_state,
        "version": version,
    }


@router.get("/api/publish/releases/{release_id}/status")
def publish_release_status(
    release_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, is_maintainer = _require_actor(context)
    try:
        release = release_service.get_release_or_404(db, release_id)
    except release_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    registry_object = db.get(RegistryObject, release.registry_object_id)
    if registry_object is None:
        raise HTTPException(status_code=404, detail="object not found")
    if not is_maintainer and registry_object.namespace_id != principal_id:
        raise HTTPException(status_code=403, detail="object namespace access denied")
    version = f"release-{release.id}"
    return _publish_status_payload(
        registry_object=registry_object,
        release_id=release.id,
        release_state=release.state,
        version=version,
    )
