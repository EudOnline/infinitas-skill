from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.exposure import service
from server.modules.exposure.schemas import (
    ExposureCreateRequest,
    ExposurePatchRequest,
    ExposureView,
)

router = APIRouter(prefix="/api/v1", tags=["exposure"])


def _require_exposure_principal(context: AccessContext) -> int:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="exposure principal required")
    if not require_any_scope(
        context, {"api:user", "exposure:write", "release:write", "authoring:write"}
    ):
        raise HTTPException(status_code=403, detail="insufficient scope")
    return context.principal.id


@router.post(
    "/releases/{release_id}/exposures",
    response_model=ExposureView,
    status_code=status.HTTP_201_CREATED,
)
def create_exposure(
    release_id: int,
    payload: ExposureCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_exposure_principal(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        exposure = service.create_exposure(
            db,
            release_id=release_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            payload=payload,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ExposureView.from_model(exposure)


@router.patch("/exposures/{exposure_id}", response_model=ExposureView)
def patch_exposure(
    exposure_id: int,
    payload: ExposurePatchRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_exposure_principal(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        exposure = service.patch_exposure(
            db,
            exposure_id=exposure_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
            payload=payload,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ExposureView.from_model(exposure)


@router.post("/exposures/{exposure_id}/activate", response_model=ExposureView)
def activate_exposure(
    exposure_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_exposure_principal(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        exposure = service.activate_exposure(
            db,
            exposure_id=exposure_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ExposureView.from_model(exposure)


@router.post("/exposures/{exposure_id}/revoke", response_model=ExposureView)
def revoke_exposure(
    exposure_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_exposure_principal(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        exposure = service.revoke_exposure(
            db,
            exposure_id=exposure_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ExposureView.from_model(exposure)
