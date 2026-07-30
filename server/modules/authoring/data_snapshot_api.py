from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

import server.modules.authoring.data_snapshot_service as service
import server.modules.authoring.service as authoring_service
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.authoring.api_support import authoring_identity, authorize_skill
from server.modules.authoring.data_snapshot_schemas import (
    DataSnapshotRegisterRequest,
    DataSnapshotView,
)
from server.modules.authoring.models import SkillDataSnapshot
from server.modules.identity.auth import get_current_access_context
from server.modules.identity.guards import actor_ref_for_context

router = APIRouter(prefix="/api/v1", tags=["authoring-data-snapshots"])
_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Not authenticated"},
    403: {"description": "Forbidden"},
    404: {"description": "Skill, version, or data snapshot not found"},
    409: {"description": "Data snapshot conflict"},
}


def _view(db: Session, snapshot: SkillDataSnapshot) -> DataSnapshotView:
    return DataSnapshotView.from_model(
        snapshot, parent_public_id=service.parent_public_id(db, snapshot)
    )


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, authoring_service.NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, authoring_service.ForbiddenError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/skills/{skill_id}/data-snapshots",
    response_model=DataSnapshotView,
    status_code=status.HTTP_201_CREATED,
    responses=_RESPONSES,
)
def register_snapshot(
    payload: DataSnapshotRegisterRequest,
    skill_id: int = Path(gt=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> DataSnapshotView:
    principal_id, is_maintainer = authoring_identity(context)
    authorize_skill(context, db, skill_id, mutate=True)
    try:
        snapshot = service.register_snapshot(
            db,
            skill_id=skill_id,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
            payload=payload,
            actor=actor_ref_for_context(context, is_maintainer=is_maintainer),
        )
    except authoring_service.AuthoringError as exc:
        raise _translate(exc) from exc
    return _view(db, snapshot)


@router.get(
    "/skills/{skill_id}/data-snapshots",
    response_model=list[DataSnapshotView],
    responses=_RESPONSES,
)
def list_snapshots(
    skill_id: int = Path(gt=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> list[DataSnapshotView]:
    principal_id, is_maintainer = authoring_identity(context)
    authorize_skill(context, db, skill_id, mutate=False)
    try:
        snapshots = service.list_snapshots(
            db, skill_id=skill_id, principal_id=principal_id, is_maintainer=is_maintainer
        )
    except authoring_service.AuthoringError as exc:
        raise _translate(exc) from exc
    return [_view(db, snapshot) for snapshot in snapshots]


@router.get(
    "/skills/{skill_id}/data-snapshots/{snapshot_id}",
    response_model=DataSnapshotView,
    responses=_RESPONSES,
)
def get_snapshot(
    skill_id: int = Path(gt=0),
    snapshot_id: str = Path(pattern=r"^dsp_[A-Za-z0-9_-]+$"),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> DataSnapshotView:
    principal_id, is_maintainer = authoring_identity(context)
    authorize_skill(context, db, skill_id, mutate=False)
    try:
        authoring_service.assert_namespace_owner(
            db,
            authoring_service.get_skill_or_404(db, skill_id),
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
        snapshot = service.get_snapshot(db, skill_id=skill_id, public_id=snapshot_id)
    except authoring_service.AuthoringError as exc:
        raise _translate(exc) from exc
    return _view(db, snapshot)


__all__ = ["router"]
