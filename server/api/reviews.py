from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from server.auth import get_current_user, require_role
from server.db import get_db
from server.models import Review, Submission, User, utcnow
from server.schemas import ReviewDecisionRequest, ReviewListView, SubmissionView
from server.api.submissions import append_status_transition, get_submission_or_404, serialize_review, serialize_submission

router = APIRouter(prefix='/api/v1/reviews', tags=['reviews'])


def get_review_or_404(db: Session, review_id: int) -> Review:
    review = db.query(Review).filter(Review.id == review_id).one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail='review not found')
    return review


@router.get('', response_model=ReviewListView)
def list_reviews(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Review).join(Submission, Review.submission_id == Submission.id)
    if user.role != 'maintainer':
        query = query.filter(Submission.created_by_user_id == user.id)
    total = query.count()
    items = query.order_by(Review.updated_at.desc(), Review.id.desc()).limit(limit).all()
    return ReviewListView(items=[serialize_review(review) for review in items], total=total)


@router.post('/{review_id}/approve', response_model=SubmissionView)
def approve_review(
    review_id: int,
    payload: ReviewDecisionRequest,
    user: User = Depends(require_role('maintainer')),
    db: Session = Depends(get_db),
):
    review = get_review_or_404(db, review_id)
    if review.status != 'pending':
        raise HTTPException(status_code=409, detail=f'review status {review.status!r} cannot be approved')
    submission = get_submission_or_404(db, review.submission_id)
    append_status_transition(submission, actor=user, to_status='approved', note=payload.note)
    submission.approved_at = utcnow()
    review.status = 'approved'
    review.note = payload.note or ''
    review.reviewed_by_user_id = user.id
    db.add(review)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    db.refresh(review)
    return serialize_submission(submission, review)


@router.post('/{review_id}/reject', response_model=SubmissionView)
def reject_review(
    review_id: int,
    payload: ReviewDecisionRequest,
    user: User = Depends(require_role('maintainer')),
    db: Session = Depends(get_db),
):
    review = get_review_or_404(db, review_id)
    if review.status != 'pending':
        raise HTTPException(status_code=409, detail=f'review status {review.status!r} cannot be rejected')
    submission = get_submission_or_404(db, review.submission_id)
    append_status_transition(submission, actor=user, to_status='rejected', note=payload.note)
    review.status = 'rejected'
    review.note = payload.note or ''
    review.reviewed_by_user_id = user.id
    db.add(review)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    db.refresh(review)
    return serialize_submission(submission, review)
