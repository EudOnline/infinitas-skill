from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import server.modules.audit.service as audit_service
import server.modules.release.service as release_service
import server.modules.review.service as review_service
from server.exceptions_base import (
    ConflictError as BaseConflictError,
)
from server.exceptions_base import (
    ForbiddenError as BaseForbiddenError,
)
from server.exceptions_base import (
    NotFoundError as BaseNotFoundError,
)
from server.model_base import utcnow
from server.modules.authoring.models import Skill
from server.modules.exposure.models import Exposure
from server.modules.exposure.schemas import ExposureCreateRequest, ExposurePatchRequest
from server.modules.release.models import Release
from server.modules.review.policy import PolicyOutcome, evaluate_exposure_policy


class ExposureError(Exception):
    pass


class NotFoundError(ExposureError, BaseNotFoundError):
    pass


class ConflictError(ExposureError, BaseConflictError):
    pass


class ForbiddenError(ExposureError, BaseForbiddenError):
    pass


def _assert_public_compatibility(release: Release, audience_type: str) -> dict:
    try:
        compatibility = json.loads(release.platform_compatibility_json or "{}")
    except json.JSONDecodeError:
        compatibility = {}
    canonical = compatibility.get("canonical_runtime")
    state = canonical.get("state") if isinstance(canonical, dict) else None
    if audience_type == "public" and state in {"blocked", "broken", "unsupported"}:
        raise ConflictError(
            f"public visibility is blocked by canonical runtime compatibility state: {state}"
        )
    return compatibility if isinstance(compatibility, dict) else {}


def get_exposure_or_404(db: Session, exposure_id: int) -> Exposure:
    exposure = db.get(Exposure, exposure_id)
    if exposure is None:
        raise NotFoundError("exposure not found")
    return exposure


def list_release_exposures(
    db: Session,
    *,
    release_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
) -> list[Exposure]:
    release = release_service.get_release_or_404(db, release_id)
    _assert_release_owner(
        db,
        release,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    return list(
        db.scalars(
            select(Exposure).where(Exposure.release_id == release_id).order_by(Exposure.id.desc())
        ).all()
    )


def _assert_release_owner(
    db: Session,
    release: Release,
    *,
    principal_id: int,
    is_maintainer: bool = False,
) -> None:
    try:
        release_service.assert_release_owner(
            db,
            release,
            principal_id=principal_id,
            is_maintainer=is_maintainer,
        )
    except release_service.NotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except release_service.ForbiddenError as exc:
        raise ForbiddenError(str(exc)) from exc


def _resolve_audience_type(
    db: Session,
    *,
    release: Release,
    requested_audience_type: str | None,
) -> str:
    if requested_audience_type:
        return requested_audience_type
    if release.skill_id is None:
        raise ConflictError("audience_type is required for a release without a skill")
    skill = db.get(Skill, release.skill_id)
    if skill is None:
        raise NotFoundError("skill not found")
    profile = str(skill.default_visibility_profile or "").strip()
    if profile not in {"public", "grant", "authenticated", "private"}:
        raise ConflictError("audience_type is required when the skill has no visibility profile")
    return profile


def _evaluate_create_policy(
    *,
    audience_type: str,
    requested_review_mode: str,
) -> PolicyOutcome:
    try:
        return evaluate_exposure_policy(
            audience_type=audience_type,
            requested_review_mode=requested_review_mode,
        )
    except ValueError as exc:
        raise ConflictError(str(exc)) from exc


def _build_exposure(
    *,
    release_id: int,
    actor_principal_id: int,
    payload: ExposureCreateRequest,
    outcome: PolicyOutcome,
    compatibility: dict,
) -> Exposure:
    policy_snapshot = {
        "audience_type": outcome.audience_type,
        "requested_review_mode": outcome.requested_review_mode,
        "review_requirement": outcome.review_requirement,
        "platform_compatibility": compatibility,
    }
    return Exposure(
        release_id=release_id,
        audience_type=outcome.audience_type,
        listing_mode=payload.listing_mode,
        install_mode=payload.install_mode,
        review_requirement=outcome.review_requirement,
        state="pending_policy",
        requested_by_principal_id=actor_principal_id,
        policy_snapshot_json=json.dumps(policy_snapshot, ensure_ascii=False, sort_keys=True),
    )


def _audit_exposure(
    db: Session,
    *,
    exposure: Exposure,
    event_type: str,
    actor_principal_id: int,
) -> None:
    release = release_service.get_release_or_404(db, exposure.release_id)
    snapshot = release_service.get_release_snapshot(db, release.id)
    audit_service.append_audit_event(
        db,
        aggregate_type="exposure",
        aggregate_id=str(exposure.id),
        event_type=event_type,
        actor_ref=f"principal:{actor_principal_id}",
        owner_principal_id=snapshot.skill.namespace_id,
        payload={
            "object_id": release.skill_id,
            "release_id": release.id,
            "exposure_id": exposure.id,
            "audience_type": exposure.audience_type,
            "state": exposure.state,
        },
    )


def _resolve_create_policy(
    db: Session,
    *,
    release: Release,
    payload: ExposureCreateRequest,
) -> tuple[PolicyOutcome, dict]:
    if release.state != "ready":
        raise ConflictError("only ready releases can be exposed")
    audience_type = _resolve_audience_type(
        db,
        release=release,
        requested_audience_type=payload.audience_type,
    )
    compatibility = _assert_public_compatibility(release, audience_type)
    outcome = _evaluate_create_policy(
        audience_type=audience_type,
        requested_review_mode=payload.requested_review_mode,
    )
    return outcome, compatibility


def _persist_new_exposure(db: Session, exposure: Exposure) -> None:
    try:
        with db.begin_nested():
            db.add(exposure)
            db.flush()
    except IntegrityError as exc:
        raise ConflictError(
            f"active {exposure.audience_type} exposure already exists for this release"
        ) from exc


def create_exposure(
    db: Session,
    *,
    release_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    payload: ExposureCreateRequest,
) -> Exposure:
    """Create a new exposure for a release.

    An exposure controls the visibility of a release to different audiences
    (public, authenticated, grant, private). The exposure goes through
    policy evaluation to determine review requirements.

    Args:
        db: Database session
        release_id: The release to expose
        actor_principal_id: The principal creating the exposure
        is_maintainer: Whether the actor is a maintainer (bypasses ownership check)
        payload: Exposure creation parameters (audience_type, listing_mode, etc.)

    Returns:
        The created Exposure object

    Raises:
        NotFoundError: If the release doesn't exist
        ForbiddenError: If the actor doesn't own the release
        ConflictError: If the release isn't ready or policy evaluation fails
    """
    try:
        release = release_service.get_release_or_404(db, release_id)
    except release_service.NotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    _assert_release_owner(
        db,
        release,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    outcome, compatibility = _resolve_create_policy(db, release=release, payload=payload)
    existing = db.scalar(
        select(Exposure)
        .where(Exposure.release_id == release_id)
        .where(Exposure.audience_type == outcome.audience_type)
        .where(Exposure.state.notin_(["revoked", "rejected"]))
        .with_for_update()
    )
    if existing is not None:
        raise ConflictError(
            f"active {outcome.audience_type} exposure already exists for this release"
        )
    exposure = _build_exposure(
        release_id=release_id,
        actor_principal_id=actor_principal_id,
        payload=payload,
        outcome=outcome,
        compatibility=compatibility,
    )
    _persist_new_exposure(db, exposure)

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
    db.flush()
    _audit_exposure(
        db,
        exposure=exposure,
        event_type="exposure.created",
        actor_principal_id=actor_principal_id,
    )
    if exposure.state == "active":
        _audit_exposure(
            db,
            exposure=exposure,
            event_type="exposure.activated",
            actor_principal_id=actor_principal_id,
        )
    return exposure


def patch_exposure(
    db: Session,
    *,
    exposure_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    payload: ExposurePatchRequest,
) -> Exposure:
    exposure = get_exposure_or_404(db, exposure_id)
    release = release_service.get_release_or_404(db, exposure.release_id)
    _assert_release_owner(
        db,
        release,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    if exposure.state in {"revoked", "rejected"}:
        raise ConflictError("closed exposure cannot be patched")

    snapshot = json.loads(exposure.policy_snapshot_json or "{}")
    if payload.listing_mode is not None:
        exposure.listing_mode = payload.listing_mode
    if payload.install_mode is not None:
        exposure.install_mode = payload.install_mode
    if payload.requested_review_mode is not None:
        current_requested_review_mode = (
            str(snapshot.get("requested_review_mode") or "none").strip().lower()
        )
        next_requested_review_mode = str(payload.requested_review_mode or "none").strip().lower()
        if next_requested_review_mode != current_requested_review_mode:
            raise ConflictError("requested_review_mode cannot be changed after exposure creation")

    db.add(exposure)
    db.flush()
    _audit_exposure(
        db,
        exposure=exposure,
        event_type="exposure.updated",
        actor_principal_id=actor_principal_id,
    )
    return exposure


def activate_exposure(
    db: Session,
    *,
    exposure_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
) -> Exposure:
    exposure = get_exposure_or_404(db, exposure_id)
    release = release_service.get_release_or_404(db, exposure.release_id)
    _assert_release_owner(
        db,
        release,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    if exposure.state == "active":
        return exposure
    if exposure.state in {"revoked", "rejected"}:
        raise ConflictError("closed exposure cannot be re-activated")
    _assert_public_compatibility(release, exposure.audience_type)
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
    db.flush()
    _audit_exposure(
        db,
        exposure=exposure,
        event_type="exposure.activated",
        actor_principal_id=actor_principal_id,
    )
    return exposure


def revoke_exposure(
    db: Session,
    *,
    exposure_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
) -> Exposure:
    exposure = get_exposure_or_404(db, exposure_id)
    release = release_service.get_release_or_404(db, exposure.release_id)
    _assert_release_owner(
        db,
        release,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )
    if exposure.state == "revoked":
        return exposure
    exposure.state = "revoked"
    exposure.ended_at = utcnow()
    # Close any open review cases for this exposure
    open_case = review_service.get_open_review_case_for_exposure(db, exposure.id)
    if open_case is not None:
        review_service.close_review_case(db, open_case, reason="exposure_revoked")
    db.add(exposure)
    db.flush()
    _audit_exposure(
        db,
        exposure=exposure,
        event_type="exposure.revoked",
        actor_principal_id=actor_principal_id,
    )
    return exposure
