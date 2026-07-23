from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import server.modules.exposure.service as service
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.access.product_scope import (
    ProductScopeForbidden,
    assert_product_token_skill_scope,
)
from server.modules.exposure.models import Exposure
from server.modules.exposure.schemas import (
    ExposureCreateRequest,
    ExposurePatchRequest,
    ExposureView,
)
from server.modules.identity.auth import get_current_access_context
from server.modules.release.models import Release

router = APIRouter(prefix="/api/v1", tags=["exposure"])


def _require_exposure_principal(context: AccessContext) -> int:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="exposure principal required")
    if not require_any_scope(context, {"api:user", "exposure:write", "authoring:write"}):
        raise HTTPException(status_code=403, detail="insufficient scope")
    return context.principal.id


def _require_release_scope(db: Session, *, context: AccessContext, release_id: int) -> None:
    release = db.get(Release, release_id)
    if release is None:
        return
    try:
        assert_product_token_skill_scope(db, context=context, skill_id=release.skill_id)
    except ProductScopeForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _require_exposure_scope(db: Session, *, context: AccessContext, exposure_id: int) -> None:
    exposure = db.get(Exposure, exposure_id)
    if exposure is not None:
        _require_release_scope(db, context=context, release_id=exposure.release_id)


@router.get("/releases/{release_id}/exposures", response_model=list[ExposureView])
def list_exposures(
    release_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> list[ExposureView]:
    principal_id = _require_exposure_principal(context)
    _require_release_scope(db, context=context, release_id=release_id)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        exposures = service.list_release_exposures(
            db,
            release_id=release_id,
            actor_principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return [ExposureView.from_model(exposure) for exposure in exposures]


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
) -> ExposureView:
    principal_id = _require_exposure_principal(context)
    _require_release_scope(db, context=context, release_id=release_id)
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
) -> ExposureView:
    principal_id = _require_exposure_principal(context)
    _require_exposure_scope(db, context=context, exposure_id=exposure_id)
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
) -> ExposureView:
    principal_id = _require_exposure_principal(context)
    _require_exposure_scope(db, context=context, exposure_id=exposure_id)
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
) -> ExposureView:
    principal_id = _require_exposure_principal(context)
    _require_exposure_scope(db, context=context, exposure_id=exposure_id)
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
