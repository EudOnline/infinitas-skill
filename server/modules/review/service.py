from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import Exposure, ReviewCase, ReviewDecision, ReviewPolicy, utcnow
from server.modules.memory.service import record_lifecycle_memory_event_best_effort
from server.modules.review import default_policy


class ReviewError(Exception):
    pass


class NotFoundError(ReviewError):
    pass


class ConflictError(ReviewError):
    pass


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
    db.add(policy)
    db.flush()
    return policy


def get_review_case_or_404(db: Session, review_case_id: int) -> ReviewCase:
    review_case = db.get(ReviewCase, review_case_id)
    if review_case is None:
        raise NotFoundError("review case not found")
    return review_case


def get_review_decisions(db: Session, review_case_id: int) -> list[ReviewDecision]:
    return db.scalars(
        select(ReviewDecision)
        .where(ReviewDecision.review_case_id == review_case_id)
        .order_by(ReviewDecision.id.asc())
    ).all()


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
    db.add(review_case)
    db.flush()
    return review_case


def record_decision(
    db: Session,
    *,
    review_case_id: int,
    reviewer_principal_id: int,
    decision: str,
    note: str,
    evidence: dict | None,
) -> tuple[ReviewCase, Exposure]:
    review_case = get_review_case_or_404(db, review_case_id)
    if review_case.state != "open":
        raise ConflictError("review case is already closed")

    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"approve", "reject", "comment"}:
        raise ConflictError("unsupported review decision")

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

    if normalized_decision == "approve":
        review_case.state = "approved"
        review_case.closed_at = utcnow()
        if review_case.mode == "blocking":
            exposure.state = "active"
            if exposure.activated_at is None:
                exposure.activated_at = utcnow()
    elif normalized_decision == "reject":
        review_case.state = "rejected"
        review_case.closed_at = utcnow()
        if review_case.mode == "blocking":
            exposure.state = "rejected"
            exposure.ended_at = utcnow()

    db.add(review_case)
    db.add(exposure)
    db.commit()
    db.refresh(review_case)
    db.refresh(exposure)
    if normalized_decision in {"approve", "reject"}:
        record_lifecycle_memory_event_best_effort(
            db,
            lifecycle_event=(
                "task.review.approve"
                if normalized_decision == "approve"
                else "task.review.reject"
            ),
            aggregate_type="review_case",
            aggregate_id=str(review_case.id),
            actor_ref=f"principal:{reviewer_principal_id}",
            payload={
                "exposure_id": str(exposure.id),
                "decision": normalized_decision,
                "mode": review_case.mode,
                "state": review_case.state,
            },
        )
    if (
        normalized_decision == "approve"
        and review_case.mode == "blocking"
        and exposure.state == "active"
    ):
        record_lifecycle_memory_event_best_effort(
            db,
            lifecycle_event="task.exposure.activate",
            aggregate_type="exposure",
            aggregate_id=str(exposure.id),
            actor_ref=f"principal:{reviewer_principal_id}",
            payload={
                "release_id": str(exposure.release_id),
                "audience_type": exposure.audience_type,
                "activation_source": "review_approve",
            },
        )
    return review_case, exposure
