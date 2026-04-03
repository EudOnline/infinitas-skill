from __future__ import annotations

import json

from sqlalchemy.orm import Session

from server.models import Exposure, Release, utcnow
from server.modules.exposure.schemas import ExposureCreateRequest, ExposurePatchRequest
from server.modules.memory.service import record_lifecycle_memory_event_best_effort
from server.modules.release import service as release_service
from server.modules.review import service as review_service
from server.modules.review.policy import evaluate_exposure_policy


class ExposureError(Exception):
    pass


class NotFoundError(ExposureError):
    pass


class ConflictError(ExposureError):
    pass


class ForbiddenError(ExposureError):
    pass


def get_exposure_or_404(db: Session, exposure_id: int) -> Exposure:
    exposure = db.get(Exposure, exposure_id)
    if exposure is None:
        raise NotFoundError("exposure not found")
    return exposure


def _assert_release_owner(db: Session, release: Release, *, principal_id: int) -> None:
    try:
        release_service.assert_release_owner(db, release, principal_id=principal_id)
    except release_service.NotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except release_service.ForbiddenError as exc:
        raise ForbiddenError(str(exc)) from exc


def create_exposure(
    db: Session,
    *,
    release_id: int,
    actor_principal_id: int,
    payload: ExposureCreateRequest,
) -> Exposure:
    try:
        release = release_service.get_release_or_404(db, release_id)
    except release_service.NotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    _assert_release_owner(db, release, principal_id=actor_principal_id)
    if release.state != "ready":
        raise ConflictError("only ready releases can be exposed")

    try:
        outcome = evaluate_exposure_policy(
            audience_type=payload.audience_type,
            requested_review_mode=payload.requested_review_mode,
        )
    except ValueError as exc:
        raise ConflictError(str(exc)) from exc

    policy_snapshot = {
        "audience_type": outcome.audience_type,
        "requested_review_mode": outcome.requested_review_mode,
        "review_requirement": outcome.review_requirement,
    }
    exposure = Exposure(
        release_id=release_id,
        audience_type=outcome.audience_type,
        listing_mode=payload.listing_mode,
        install_mode=payload.install_mode,
        review_requirement=outcome.review_requirement,
        state="pending_policy",
        requested_by_principal_id=actor_principal_id,
        policy_snapshot_json=json.dumps(policy_snapshot, ensure_ascii=False, sort_keys=True),
    )
    db.add(exposure)
    db.flush()

    if outcome.review_requirement in {"advisory", "blocking"}:
        review_service.open_review_case(
            db,
            exposure=exposure,
            actor_principal_id=actor_principal_id,
            mode=outcome.review_requirement,
        )

    if outcome.auto_activate:
        exposure.state = "active"
        exposure.activated_at = utcnow()
    else:
        exposure.state = "review_open"

    db.add(exposure)
    db.commit()
    db.refresh(exposure)
    record_lifecycle_memory_event_best_effort(
        db,
        lifecycle_event="task.exposure.create",
        aggregate_type="exposure",
        aggregate_id=str(exposure.id),
        actor_ref=f"principal:{actor_principal_id}",
        payload={
            "release_id": str(exposure.release_id),
            "audience_type": exposure.audience_type,
            "review_requirement": exposure.review_requirement,
            "state": exposure.state,
        },
    )
    if exposure.state == "active":
        record_lifecycle_memory_event_best_effort(
            db,
            lifecycle_event="task.exposure.activate",
            aggregate_type="exposure",
            aggregate_id=str(exposure.id),
            actor_ref=f"principal:{actor_principal_id}",
            payload={
                "release_id": str(exposure.release_id),
                "audience_type": exposure.audience_type,
                "activation_source": "create_exposure",
            },
        )
    return exposure


def patch_exposure(
    db: Session,
    *,
    exposure_id: int,
    actor_principal_id: int,
    payload: ExposurePatchRequest,
) -> Exposure:
    exposure = get_exposure_or_404(db, exposure_id)
    release = release_service.get_release_or_404(db, exposure.release_id)
    _assert_release_owner(db, release, principal_id=actor_principal_id)
    if exposure.state in {"revoked", "rejected"}:
        raise ConflictError("closed exposure cannot be patched")

    snapshot = json.loads(exposure.policy_snapshot_json or "{}")
    if payload.listing_mode is not None:
        exposure.listing_mode = payload.listing_mode
    if payload.install_mode is not None:
        exposure.install_mode = payload.install_mode
    if payload.requested_review_mode is not None:
        snapshot["requested_review_mode"] = payload.requested_review_mode
        exposure.policy_snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)

    db.add(exposure)
    db.commit()
    db.refresh(exposure)
    return exposure


def activate_exposure(db: Session, *, exposure_id: int, actor_principal_id: int) -> Exposure:
    exposure = get_exposure_or_404(db, exposure_id)
    release = release_service.get_release_or_404(db, exposure.release_id)
    _assert_release_owner(db, release, principal_id=actor_principal_id)
    if exposure.state == "active":
        return exposure
    if exposure.review_requirement == "blocking":
        review_case = review_service.get_open_review_case_for_exposure(db, exposure.id)
        if review_case is not None:
            raise ConflictError("blocking review must be resolved before activation")
        latest_case = review_service.get_latest_review_case_for_exposure(db, exposure.id)
        if latest_case is None or latest_case.state != "approved":
            raise ConflictError("blocking review must be approved before activation")
    exposure.state = "active"
    if exposure.activated_at is None:
        exposure.activated_at = utcnow()
    db.add(exposure)
    db.commit()
    db.refresh(exposure)
    record_lifecycle_memory_event_best_effort(
        db,
        lifecycle_event="task.exposure.activate",
        aggregate_type="exposure",
        aggregate_id=str(exposure.id),
        actor_ref=f"principal:{actor_principal_id}",
        payload={
            "release_id": str(exposure.release_id),
            "audience_type": exposure.audience_type,
            "activation_source": "manual_activate",
        },
    )
    return exposure


def revoke_exposure(db: Session, *, exposure_id: int, actor_principal_id: int) -> Exposure:
    exposure = get_exposure_or_404(db, exposure_id)
    release = release_service.get_release_or_404(db, exposure.release_id)
    _assert_release_owner(db, release, principal_id=actor_principal_id)
    if exposure.state == "revoked":
        return exposure
    exposure.state = "revoked"
    exposure.ended_at = utcnow()
    db.add(exposure)
    db.commit()
    db.refresh(exposure)
    return exposure
