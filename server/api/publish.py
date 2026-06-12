from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.auth_guards import require_authoring_principal as _require_actor
from server.db import get_db
from server.jobs import enqueue_job, has_active_job
from server.logging import get_logger
from server.models import Skill
from server.modules.access.authn import AccessContext
from server.modules.authoring import service as authoring_service
from server.modules.authoring.schemas import SkillCreateRequest
from server.modules.release import service as release_service
from server.modules.release.materializer import release_requires_materialization
from server.settings import get_settings

router = APIRouter(prefix="/api/v1/publish", tags=["publish"])

log = get_logger(__name__)


class PublishObjectRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=2000)


class PublishReleaseRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    content_ref: str = Field(default="", max_length=2000)
    metadata: dict = Field(default_factory=dict)


def _object_payload(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "kind": "skill",
        "slug": skill.slug,
        "display_name": skill.display_name,
        "summary": skill.summary,
        "status": skill.status,
    }


def _find_existing_skill(
    db: Session,
    *,
    namespace_id: int,
    slug: str,
) -> Skill | None:
    return db.scalar(
        select(Skill)
        .where(Skill.namespace_id == namespace_id)
        .where(Skill.slug == slug)
    )


@router.put("/objects/{slug}")
def upsert_publish_object(
    slug: str,
    payload: PublishObjectRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    """Create or update a skill object.

    If a skill with the given slug exists in the caller's namespace,
    updates it. Otherwise creates a new skill object.

    Path Parameters:
        slug: URL-safe skill identifier (no slashes, dots, or null bytes)

    Request Body:
        display_name: Human-readable skill name (1-200 chars)
        summary: Optional skill description
    """
    principal_id, _is_maintainer = _require_actor(context)
    # Security validation to prevent path traversal and injection attempts
    if ".." in slug or "/" in slug or "\\" in slug or "\x00" in slug:
        raise HTTPException(
            status_code=422,
            detail="Invalid slug format"
        )
    existing = _find_existing_skill(db, namespace_id=principal_id, slug=slug)
    if existing is not None:
        existing.display_name = payload.display_name
        existing.summary = payload.summary
        db.add(existing)
        db.commit()
        return _object_payload(existing)

    try:
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
        return _object_payload(skill)
    except authoring_service.AuthoringError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        log.exception(
            "unexpected error creating publish object slug=%s",
            slug,
        )
        raise HTTPException(
            status_code=500, detail="Internal error creating object"
        ) from exc


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


@router.post("/objects/{object_id}/releases", status_code=status.HTTP_201_CREATED)
def publish_object_release(
    object_id: int,
    payload: PublishReleaseRequest,
    response: Response,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    """Create a new release for a skill object.

    Creates a draft, seals it into a version, and creates a release.
    Automatically enqueues a background job to materialize artifacts
    (manifest, bundle, provenance, signature).

    Path Parameters:
        object_id: The skill object ID to release

    Request Body:
        version: Semantic version string (1-64 chars)
        content_ref: Optional content reference path
        metadata: Optional metadata dict
    """
    principal_id, is_maintainer = _require_actor(context)
    skill = db.get(Skill, object_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    if not is_maintainer and skill.namespace_id != principal_id:
        raise HTTPException(status_code=403, detail="skill namespace access denied")
    try:
        version = authoring_service.create_skill_version_snapshot(
            db,
            skill_id=skill.id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            version=payload.version,
            content_ref=payload.content_ref,
            metadata=payload.metadata,
        )
        release, created = release_service.create_or_get_release(
            db,
            version_id=version.id,
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
        skill=skill,
        release_id=release.id,
        release_state=release.state,
        version=payload.version,
    )


def _publish_status_payload(
    *,
    skill: Skill,
    release_id: int,
    release_state: str,
    version: str,
) -> dict:
    return {
        "object_id": skill.id,
        "object_kind": "skill",
        "object_slug": skill.slug,
        "release_id": release_id,
        "release_state": release_state,
        "version": version,
    }


@router.get("/releases/{release_id}/status")
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
    skill = db.get(Skill, release.skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    if not is_maintainer and skill.namespace_id != principal_id:
        raise HTTPException(status_code=403, detail="skill namespace access denied")
    version = f"release-{release.id}"
    return _publish_status_payload(
        skill=skill,
        release_id=release.id,
        release_state=release.state,
        version=version,
    )
