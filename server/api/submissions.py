from __future__ import annotations

import json
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.auth import get_current_user, require_role
from server.db import get_db
from server.jobs import enqueue_job, serialize_job
from server.models import Review, Submission, User, utcnow
from server.schemas import JobEnqueueResponse, SubmissionCreateRequest, SubmissionView, TransitionRequest, ReviewView, StatusLogEntry

router = APIRouter(prefix='/api/v1/submissions', tags=['submissions'])


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace('+00:00', 'Z')


def _load_json(raw: str, fallback):
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _status_log(submission: Submission) -> list[dict]:
    payload = _load_json(submission.status_log_json or '[]', [])
    return payload if isinstance(payload, list) else []


def append_status_transition(submission: Submission, *, actor: User, to_status: str, note: str = ''):
    history = _status_log(submission)
    history.append(
        {
            'at': _iso(utcnow()),
            'actor_id': actor.id,
            'actor_username': actor.username,
            'actor_role': actor.role,
            'from_status': submission.status,
            'to': to_status,
            'note': note or '',
        }
    )
    submission.status_log_json = json.dumps(history, ensure_ascii=False)
    submission.status = to_status
    submission.updated_by_user_id = actor.id


def latest_review(db: Session, submission_id: int) -> Review | None:
    return (
        db.query(Review)
        .filter(Review.submission_id == submission_id)
        .order_by(Review.id.desc())
        .first()
    )


def serialize_review(review: Review | None) -> ReviewView | None:
    if review is None:
        return None
    return ReviewView(
        id=review.id,
        submission_id=review.submission_id,
        status=review.status,
        note=review.note or '',
        requested_by=review.requested_by.username if review.requested_by else None,
        reviewed_by=review.reviewed_by.username if review.reviewed_by else None,
        created_at=_iso(review.created_at) or '',
        updated_at=_iso(review.updated_at) or '',
    )


def serialize_submission(submission: Submission, review: Review | None = None) -> SubmissionView:
    return SubmissionView(
        id=submission.id,
        skill_name=submission.skill_name,
        publisher=submission.publisher,
        status=submission.status,
        payload_summary=submission.payload_summary or '',
        payload=_load_json(submission.payload_json or '{}', {}),
        created_by=submission.created_by.username if submission.created_by else None,
        updated_by=submission.updated_by.username if submission.updated_by else None,
        created_at=_iso(submission.created_at) or '',
        updated_at=_iso(submission.updated_at) or '',
        approved_at=_iso(submission.approved_at),
        status_log=[StatusLogEntry.model_validate(item) for item in _status_log(submission)],
        review=serialize_review(review),
    )


def get_submission_or_404(db: Session, submission_id: int) -> Submission:
    submission = db.query(Submission).filter(Submission.id == submission_id).one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail='submission not found')
    return submission


def require_status(submission: Submission, allowed: Iterable[str]):
    if submission.status not in set(allowed):
        raise HTTPException(
            status_code=409,
            detail=f'submission status {submission.status!r} does not allow this transition',
        )


@router.post('', response_model=SubmissionView, status_code=status.HTTP_201_CREATED)
def create_submission(
    payload: SubmissionCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    submission = Submission(
        skill_name=payload.skill_name,
        publisher=payload.publisher,
        payload_summary=payload.payload_summary or '',
        payload_json=json.dumps(payload.payload, ensure_ascii=False),
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    submission.status_log_json = json.dumps(
        [
            {
                'at': _iso(utcnow()),
                'actor_id': user.id,
                'actor_username': user.username,
                'actor_role': user.role,
                'from_status': None,
                'to': 'draft',
                'note': 'Submission created',
            }
        ],
        ensure_ascii=False,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return serialize_submission(submission)


@router.get('/{submission_id}', response_model=SubmissionView)
def get_submission(
    submission_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    submission = get_submission_or_404(db, submission_id)
    return serialize_submission(submission, latest_review(db, submission.id))


@router.post('/{submission_id}/request-validation', response_model=SubmissionView)
def request_validation(
    submission_id: int,
    payload: TransitionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    submission = get_submission_or_404(db, submission_id)
    require_status(submission, {'draft'})
    append_status_transition(submission, actor=user, to_status='validation_requested', note=payload.note)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return serialize_submission(submission, latest_review(db, submission.id))


@router.post('/{submission_id}/request-review', response_model=SubmissionView)
def request_review(
    submission_id: int,
    payload: TransitionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    submission = get_submission_or_404(db, submission_id)
    require_status(submission, {'draft', 'validation_requested'})
    append_status_transition(submission, actor=user, to_status='review_requested', note=payload.note)
    submission.review_requested_at = utcnow()
    review = Review(
        submission_id=submission.id,
        status='pending',
        note=payload.note or '',
        requested_by_user_id=user.id,
    )
    db.add(submission)
    db.add(review)
    db.commit()
    db.refresh(submission)
    db.refresh(review)
    return serialize_submission(submission, review)


@router.post('/{submission_id}/queue-validation', response_model=JobEnqueueResponse, status_code=status.HTTP_202_ACCEPTED)
def queue_validation(
    submission_id: int,
    payload: TransitionRequest,
    user: User = Depends(require_role('maintainer')),
    db: Session = Depends(get_db),
):
    submission = get_submission_or_404(db, submission_id)
    job = enqueue_job(
        db,
        kind='validate_submission',
        payload={'submission_id': submission.id, 'skill_name': submission.skill_name},
        requested_by=user,
        submission_id=submission.id,
        note=payload.note,
    )
    return JobEnqueueResponse(
        ok=True,
        status='queued',
        detail='validation job queued',
        job=serialize_job(job),
    )


@router.post('/{submission_id}/queue-promote', response_model=JobEnqueueResponse, status_code=status.HTTP_202_ACCEPTED)
def queue_promote(
    submission_id: int,
    payload: TransitionRequest,
    user: User = Depends(require_role('maintainer')),
    db: Session = Depends(get_db),
):
    submission = get_submission_or_404(db, submission_id)
    if submission.status not in {'approved', 'validated', 'review_requested'}:
        raise HTTPException(status_code=409, detail=f'submission status {submission.status!r} cannot be promoted')
    job = enqueue_job(
        db,
        kind='promote_submission',
        payload={'submission_id': submission.id, 'skill_name': submission.skill_name},
        requested_by=user,
        submission_id=submission.id,
        note=payload.note,
    )
    return JobEnqueueResponse(
        ok=True,
        status='queued',
        detail='promotion job queued',
        job=serialize_job(job),
    )
