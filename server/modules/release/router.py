from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

import server.modules.release.service as service
from server.db import get_db
from server.jobs import enqueue_job, has_active_job
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.access.credential_policy import (
    CredentialPolicyForbidden,
    CredentialPublishQuotaExceeded,
    assert_credential_mutation_allowed,
    consume_credential_publish_quota,
)
from server.modules.access.product_scope import (
    ProductScopeForbidden,
    assert_product_token_skill_scope,
)
from server.modules.authoring.models import SkillVersion
from server.modules.identity.auth import get_current_access_context
from server.modules.identity.models import User
from server.modules.release.materializer import release_requires_materialization
from server.modules.release.schemas import ArtifactListView, ArtifactView, ReleaseView
from server.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["release"])


def _require_release_context(context: AccessContext) -> tuple[int, User]:
    if context.principal is None or context.user is None:
        raise HTTPException(
            status_code=403,
            detail="release actor must resolve to a user principal",
        )
    if not require_any_scope(
        context,
        {"api:user", "release:write", "authoring:write", "skill:write"},
    ):
        raise HTTPException(status_code=403, detail="insufficient scope")
    return context.principal.id, context.user


def _require_product_scope(context: AccessContext, db: Session, object_id: int | None) -> None:
    try:
        assert_product_token_skill_scope(db, context=context, skill_id=object_id)
    except ProductScopeForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _require_credential_mutation(context: AccessContext, db: Session) -> None:
    try:
        assert_credential_mutation_allowed(
            db,
            credential=context.credential,
            object_kind="skill",
        )
    except CredentialPolicyForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _consume_publish_quota(context: AccessContext, db: Session) -> None:
    try:
        consume_credential_publish_quota(db, credential=context.credential)
    except CredentialPublishQuotaExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


@router.post(
    "/versions/{version_id}/releases",
    response_model=ReleaseView,
    status_code=status.HTTP_201_CREATED,
)
def create_release(
    version_id: int,
    response: Response,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> ReleaseView:
    principal_id, user = _require_release_context(context)
    skill_version = db.get(SkillVersion, version_id)
    if skill_version is None:
        raise HTTPException(status_code=404, detail="skill version not found")
    _require_product_scope(context, db, skill_version.skill_id)
    _require_credential_mutation(context, db)
    is_maintainer = user.role == "maintainer"
    try:
        release, created = service.create_or_get_release(
            db,
            version_id=version_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if created:
        _consume_publish_quota(context, db)
        enqueue_job(
            db,
            kind="materialize_release",
            payload={"release_id": release.id},
            requested_by=user,
            note=f"materialize release {release.id}",
        )
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
            )
        response.status_code = status.HTTP_200_OK
    return ReleaseView.from_model(release)


@router.get("/releases/{release_id}", response_model=ReleaseView)
def get_release(
    release_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> ReleaseView:
    principal_id, _ = _require_release_context(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        release = service.get_release_or_404(db, release_id)
        _require_product_scope(context, db, release.skill_id)
        service.assert_release_owner(
            db,
            release,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ReleaseView.from_model(release)


@router.get("/releases/{release_id}/artifacts", response_model=ArtifactListView)
def list_release_artifacts(
    release_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> ArtifactListView:
    principal_id, _ = _require_release_context(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        release = service.get_release_or_404(db, release_id)
        _require_product_scope(context, db, release.skill_id)
        service.assert_release_owner(
            db,
            release,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    artifacts = service.get_current_artifacts_for_release(db, release)
    return ArtifactListView(
        items=[ArtifactView.from_model(artifact) for artifact in artifacts],
        total=len(artifacts),
    )
