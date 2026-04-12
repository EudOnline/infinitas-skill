from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.authz import require_any_scope
from server.modules.exposure.service import get_exposure_or_404
from server.modules.release import service as release_service
from server.modules.review import service
from server.modules.review.schemas import (
    ReviewCaseCreateRequest,
    ReviewCaseView,
    ReviewDecisionCreateRequest,
    ReviewDecisionView,
)

router = APIRouter(prefix="/api/v1", tags=["review"])


def _require_review_principal(context: AccessContext) -> int:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="review principal required")
    if not require_any_scope(
        context, {"api:user", "review:write", "release:write", "authoring:write"}
    ):
        raise HTTPException(status_code=403, detail="insufficient scope")
    return context.principal.id


def _require_review_case_owner(
    db: Session,
    *,
    review_case_id: int,
    principal_id: int,
    is_maintainer: bool = False,
):
    review_case = service.get_review_case_or_404(db, review_case_id)
    exposure = get_exposure_or_404(db, review_case.exposure_id)
    release = release_service.get_release_or_404(db, exposure.release_id)
    release_service.assert_release_owner(
        db,
        release,
        principal_id=principal_id,
        is_maintainer=is_maintainer,
    )
    return review_case


def _review_case_view(db: Session, review_case) -> ReviewCaseView:
    decisions = [
        ReviewDecisionView.from_model(item)
        for item in service.get_review_decisions(db, review_case.id)
    ]
    return ReviewCaseView.from_model(review_case, decisions=decisions)


@router.post(
    "/exposures/{exposure_id}/review-cases",
    response_model=ReviewCaseView,
    status_code=status.HTTP_201_CREATED,
)
def create_review_case(
    exposure_id: int,
    payload: ReviewCaseCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_review_principal(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        exposure = get_exposure_or_404(db, exposure_id)
        release = release_service.get_release_or_404(db, exposure.release_id)
        release_service.assert_release_owner(
            db,
            release,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
        review_case = service.open_review_case(
            db,
            exposure=exposure,
            actor_principal_id=principal_id,
            mode=payload.mode or exposure.review_requirement or "advisory",
        )
        db.commit()
        db.refresh(review_case)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except release_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except release_service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _review_case_view(db, review_case)


@router.post(
    "/review-cases/{review_case_id}/decisions",
    response_model=ReviewCaseView,
    status_code=status.HTTP_201_CREATED,
)
def create_review_decision(
    review_case_id: int,
    payload: ReviewDecisionCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_review_principal(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        _require_review_case_owner(
            db,
            review_case_id=review_case_id,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
        review_case, _ = service.record_decision(
            db,
            review_case_id=review_case_id,
            reviewer_principal_id=principal_id,
            reviewer_user=context.user,
            decision=payload.decision,
            note=payload.note,
            evidence=payload.evidence,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except release_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except release_service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _review_case_view(db, review_case)


@router.get("/review-cases/{review_case_id}", response_model=ReviewCaseView)
def get_review_case(
    review_case_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    principal_id = _require_review_principal(context)
    is_maintainer = context.user is not None and context.user.role == "maintainer"
    try:
        review_case = _require_review_case_owner(
            db,
            review_case_id=review_case_id,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except release_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except release_service.ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _review_case_view(db, review_case)
