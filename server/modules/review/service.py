from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import server.modules.audit.service as audit_service
import server.modules.review.default_policy as default_policy
from server.exceptions_base import (
    ConflictError as BaseConflictError,
)
from server.exceptions_base import (
    NotFoundError as BaseNotFoundError,
)
from server.model_base import utcnow
from server.modules.authoring.models import Skill
from server.modules.exposure.models import Exposure
from server.modules.identity.models import User
from server.modules.release.models import Release
from server.modules.review.models import ReviewCase, ReviewDecision, ReviewPolicy


class ReviewError(Exception):
    pass


class NotFoundError(ReviewError, BaseNotFoundError):
    pass


class ConflictError(ReviewError, BaseConflictError):
    pass


def _owner_principal_id_for_exposure(db: Session, exposure: Exposure) -> int | None:
    release = db.get(Release, exposure.release_id)
    if release is None or release.skill_id is None:
        return exposure.requested_by_principal_id
    skill = db.get(Skill, release.skill_id)
    return skill.namespace_id if skill is not None else exposure.requested_by_principal_id


def _audit_exposure_activation(
    db: Session,
    *,
    exposure: Exposure,
    actor_principal_id: int,
) -> None:
    release = db.get(Release, exposure.release_id)
    audit_service.append_audit_event(
        db,
        aggregate_type="exposure",
        aggregate_id=str(exposure.id),
        event_type="exposure.activated",
        actor_ref=f"principal:{actor_principal_id}",
        owner_principal_id=_owner_principal_id_for_exposure(db, exposure),
        payload={
            "object_id": release.skill_id if release is not None else None,
            "release_id": exposure.release_id,
            "exposure_id": exposure.id,
            "audience_type": exposure.audience_type,
            "state": exposure.state,
        },
    )


def ensure_default_policy(db: Session) -> ReviewPolicy:
    policy = db.scalar(
        select(ReviewPolicy)
        .where(ReviewPolicy.name == default_policy.DEFAULT_POLICY_NAME)
        .where(ReviewPolicy.version == default_policy.DEFAULT_POLICY_VERSION)
        .order_by(ReviewPolicy.id.desc())
    )
    if policy is not None:
        return policy

    policy = ReviewPolicy(
        name=default_policy.DEFAULT_POLICY_NAME,
        version=default_policy.DEFAULT_POLICY_VERSION,
        is_active=True,
        rules_json=json.dumps(
            default_policy.DEFAULT_POLICY_RULES,
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    try:
        with db.begin_nested():
            db.add(policy)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(ReviewPolicy)
            .where(ReviewPolicy.name == default_policy.DEFAULT_POLICY_NAME)
            .where(ReviewPolicy.version == default_policy.DEFAULT_POLICY_VERSION)
        )
        if existing is None:
            raise
        return existing
    return policy


def get_review_case_or_404(db: Session, review_case_id: int) -> ReviewCase:
    review_case = db.get(ReviewCase, review_case_id)
    if review_case is None:
        raise NotFoundError("review case not found")
    return review_case


def get_review_decisions(db: Session, review_case_id: int) -> list[ReviewDecision]:
    return list(
        db.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.review_case_id == review_case_id)
            .order_by(ReviewDecision.id.asc())
        ).all()
    )


def get_open_review_case_for_exposure(db: Session, exposure_id: int) -> ReviewCase | None:
    return db.scalar(
        select(ReviewCase)
        .where(ReviewCase.exposure_id == exposure_id)
        .where(ReviewCase.state == "open")
        .order_by(ReviewCase.id.desc())
    )


def get_latest_review_case_for_exposure(db: Session, exposure_id: int) -> ReviewCase | None:
    return db.scalar(
        select(ReviewCase)
        .where(ReviewCase.exposure_id == exposure_id)
        .order_by(ReviewCase.id.desc())
    )


def close_review_case(db: Session, review_case: ReviewCase, *, reason: str) -> None:
    if review_case.state != "open":
        return
    review_case.state = "closed"
    cast(Any, review_case).closed_at = utcnow()
    db.add(review_case)


def open_review_case(
    db: Session,
    *,
    exposure: Exposure,
    actor_principal_id: int,
    mode: str,
) -> ReviewCase:
    existing = get_open_review_case_for_exposure(db, exposure.id)
    if existing is not None:
        return existing

    policy = ensure_default_policy(db)
    review_case = ReviewCase(
        exposure_id=exposure.id,
        policy_id=policy.id,
        mode=mode,
        state="open",
        opened_by_principal_id=actor_principal_id,
    )
    try:
        with db.begin_nested():
            db.add(review_case)
            db.flush()
    except IntegrityError:
        existing = get_open_review_case_for_exposure(db, exposure.id)
        if existing is None:
            raise
        return existing
    audit_service.append_audit_event(
        db,
        aggregate_type="review_case",
        aggregate_id=str(review_case.id),
        event_type="review_case.opened",
        actor_ref=f"principal:{actor_principal_id}",
        owner_principal_id=_owner_principal_id_for_exposure(db, exposure),
        payload={
            "release_id": exposure.release_id,
            "exposure_id": exposure.id,
            "review_case_id": review_case.id,
            "mode": mode,
        },
    )
    return review_case


def record_decision(
    db: Session,
    *,
    review_case_id: int,
    reviewer_principal_id: int,
    reviewer_user: User | None = None,
    decision: str,
    note: str,
    evidence: dict | None,
) -> tuple[ReviewCase, Exposure]:
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"approve", "reject", "comment"}:
        raise ConflictError("unsupported review decision")

    review_case = get_review_case_or_404(db, review_case_id)
    next_state = {
        "approve": "approved",
        "reject": "rejected",
        "comment": "open",
    }[normalized_decision]
    values: dict[str, Any] = {"state": next_state}
    if normalized_decision != "comment":
        values["closed_at"] = utcnow()
    result = db.execute(
        update(ReviewCase)
        .where(ReviewCase.id == review_case_id)
        .where(ReviewCase.state == "open")
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if cast(Any, result).rowcount != 1:
        db.expire(review_case)
        raise ConflictError("review case is already closed")
    db.refresh(review_case)

    # Authorization is the caller's responsibility; router layer verifies
    # ownership via assert_release_owner before invoking this function.

    exposure = db.get(Exposure, review_case.exposure_id)
    if exposure is None:
        raise NotFoundError("exposure not found")

    decision_row = ReviewDecision(
        review_case_id=review_case.id,
        reviewer_principal_id=reviewer_principal_id,
        decision=normalized_decision,
        note=note or "",
        evidence_json=json.dumps(evidence or {}, ensure_ascii=False, sort_keys=True),
    )
    db.add(decision_row)
    db.flush()

    exposure_activated = False
    if normalized_decision == "approve":
        if review_case.mode == "blocking":
            exposure_activated = exposure.state != "active"
            exposure.state = "active"
            if exposure.activated_at is None:
                cast(Any, exposure).activated_at = utcnow()
    elif normalized_decision == "reject":
        if review_case.mode == "blocking":
            exposure.state = "rejected"
            cast(Any, exposure).ended_at = utcnow()

    db.add(review_case)
    db.add(exposure)
    db.flush()
    audit_service.append_audit_event(
        db,
        aggregate_type="review_case",
        aggregate_id=str(review_case.id),
        event_type="review_decision.recorded",
        actor_ref=f"principal:{reviewer_principal_id}",
        owner_principal_id=_owner_principal_id_for_exposure(db, exposure),
        payload={
            "release_id": exposure.release_id,
            "exposure_id": exposure.id,
            "review_case_id": review_case.id,
            "decision": normalized_decision,
            "state": review_case.state,
        },
    )
    if exposure_activated:
        _audit_exposure_activation(
            db,
            exposure=exposure,
            actor_principal_id=reviewer_principal_id,
        )
    return review_case, exposure
