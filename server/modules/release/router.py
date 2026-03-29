from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.jobs import enqueue_job
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.release import service
from server.modules.release.schemas import ArtifactListView, ArtifactView, ReleaseView

router = APIRouter(prefix="/api/v1", tags=["release"])


def _require_release_context(context: AccessContext) -> tuple[int, object]:
    if context.principal is None or context.user is None:
        raise HTTPException(status_code=403, detail="release actor must resolve to a user principal")
    if not require_any_scope(context, {"api:user", "release:write", "authoring:write", "skill:write"}):
        raise HTTPException(status_code=403, detail="insufficient scope")
    return context.principal.id, context.user


@router.post("/versions/{version_id}/releases", response_model=ReleaseView, status_code=status.HTTP_201_CREATED)
def create_release(
    version_id: int,
    response: Response,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, user = _require_release_context(context)
    try:
        release, created = service.create_or_get_release(
            db,
            version_id=version_id,
            actor_principal_id=principal_id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
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
            raise
    else:
        response.status_code = status.HTTP_200_OK
    return ReleaseView.from_model(release)


@router.get("/releases/{release_id}", response_model=ReleaseView)
def get_release(
    release_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id, _ = _require_release_context(context)
    try:
        release = service.get_release_or_404(db, release_id)
        service.assert_release_owner(db, release, principal_id=principal_id)
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
):
    principal_id, _ = _require_release_context(context)
    try:
        release = service.get_release_or_404(db, release_id)
        service.assert_release_owner(db, release, principal_id=principal_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    artifacts = service.get_artifacts_for_release(db, release_id)
    return ArtifactListView(
        items=[ArtifactView.from_model(artifact) for artifact in artifacts],
        total=len(artifacts),
    )
