from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

import server.modules.authoring.collaboration_service as service
import server.modules.authoring.service as authoring_service
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.authoring.api_support import authoring_identity, authorize_skill
from server.modules.authoring.collaboration_schemas import (
    ChangeSetAcceptRequest,
    ChangeSetAcceptView,
    ChangeSetCreateRequest,
    ChangeSetView,
)
from server.modules.authoring.models import SkillChangeSet
from server.modules.identity.auth import get_current_access_context
from server.modules.identity.guards import actor_ref_for_context
from server.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["authoring-collaboration"])
_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Not authenticated"},
    403: {"description": "Forbidden"},
    404: {"description": "Skill or ChangeSet not found"},
    409: {"description": "ChangeSet state or latest-version conflict"},
}


def _view(db: Session, change_set: SkillChangeSet) -> ChangeSetView:
    return ChangeSetView.from_model(
        change_set, content_public_id=service.content_public_id(db, change_set)
    )


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, authoring_service.NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, authoring_service.ForbiddenError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/skills/{skill_id}/changesets",
    response_model=ChangeSetView,
    status_code=status.HTTP_201_CREATED,
    responses=_RESPONSES,
)
def create_change_set(
    payload: ChangeSetCreateRequest,
    skill_id: int = Path(gt=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> ChangeSetView:
    principal_id, is_maintainer = authoring_identity(context)
    authorize_skill(context, db, skill_id, mutate=True)
    try:
        result = service.create_change_set(
            db,
            skill_id=skill_id,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
            payload=payload,
            pending_ttl_hours=get_settings().content_pending_ttl_hours,
            actor=actor_ref_for_context(context, is_maintainer=is_maintainer),
        )
    except authoring_service.AuthoringError as exc:
        raise _translate(exc) from exc
    return _view(db, result)


@router.get(
    "/skills/{skill_id}/changesets", response_model=list[ChangeSetView], responses=_RESPONSES
)
def list_change_sets(
    skill_id: int = Path(gt=0),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> list[ChangeSetView]:
    principal_id, is_maintainer = authoring_identity(context)
    authorize_skill(context, db, skill_id, mutate=False)
    try:
        rows = service.list_change_sets(
            db, skill_id=skill_id, principal_id=principal_id, is_maintainer=is_maintainer
        )
    except authoring_service.AuthoringError as exc:
        raise _translate(exc) from exc
    return [_view(db, row) for row in rows]


@router.get(
    "/skills/{skill_id}/changesets/{change_set_id}",
    response_model=ChangeSetView,
    responses=_RESPONSES,
)
def get_change_set(
    skill_id: int = Path(gt=0),
    change_set_id: str = Path(pattern=r"^chg_[A-Za-z0-9_-]+$"),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> ChangeSetView:
    principal_id, is_maintainer = authoring_identity(context)
    authorize_skill(context, db, skill_id, mutate=False)
    try:
        row = service.get_change_set(
            db,
            skill_id=skill_id,
            public_id=change_set_id,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except authoring_service.AuthoringError as exc:
        raise _translate(exc) from exc
    return _view(db, row)


@router.post(
    "/skills/{skill_id}/changesets/{change_set_id}/submit",
    response_model=ChangeSetView,
    responses=_RESPONSES,
)
def submit_change_set(
    skill_id: int = Path(gt=0),
    change_set_id: str = Path(pattern=r"^chg_[A-Za-z0-9_-]+$"),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> ChangeSetView:
    principal_id, is_maintainer = authoring_identity(context)
    authorize_skill(context, db, skill_id, mutate=True)
    try:
        row = service.submit_change_set(
            db,
            skill_id=skill_id,
            public_id=change_set_id,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
            actor=actor_ref_for_context(context, is_maintainer=is_maintainer),
        )
    except authoring_service.AuthoringError as exc:
        raise _translate(exc) from exc
    return _view(db, row)


@router.post(
    "/skills/{skill_id}/changesets/{change_set_id}/reject",
    response_model=ChangeSetView,
    responses=_RESPONSES,
)
def reject_change_set(
    skill_id: int = Path(gt=0),
    change_set_id: str = Path(pattern=r"^chg_[A-Za-z0-9_-]+$"),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> ChangeSetView:
    principal_id, is_maintainer = authoring_identity(context)
    authorize_skill(context, db, skill_id, mutate=True)
    try:
        row = service.reject_change_set(
            db,
            skill_id=skill_id,
            public_id=change_set_id,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
            actor=actor_ref_for_context(context, is_maintainer=is_maintainer),
        )
    except authoring_service.AuthoringError as exc:
        raise _translate(exc) from exc
    return _view(db, row)


@router.post(
    "/skills/{skill_id}/changesets/{change_set_id}/accept",
    response_model=ChangeSetAcceptView,
    responses=_RESPONSES,
)
def accept_change_set(
    payload: ChangeSetAcceptRequest,
    skill_id: int = Path(gt=0),
    change_set_id: str = Path(pattern=r"^chg_[A-Za-z0-9_-]+$"),
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> ChangeSetAcceptView:
    principal_id, is_maintainer = authoring_identity(context)
    authorize_skill(context, db, skill_id, mutate=True)
    try:
        change_set, version = service.accept_change_set(
            db,
            skill_id=skill_id,
            public_id=change_set_id,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
            expected_latest_digest=payload.expected_latest_digest,
            pending_ttl_hours=get_settings().content_pending_ttl_hours,
            actor=actor_ref_for_context(context, is_maintainer=is_maintainer),
        )
    except authoring_service.AuthoringError as exc:
        raise _translate(exc) from exc
    return ChangeSetAcceptView(
        change_set=_view(db, change_set),
        version_id=version.id,
        version=version.version,
        content_digest=version.content_digest,
    )


__all__ = ["router"]
