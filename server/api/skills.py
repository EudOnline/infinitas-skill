from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.auth import get_current_user, require_role
from server.db import get_db
from server.jobs import enqueue_job, serialize_job
from server.models import Submission, User
from server.schemas import PublishRequest, SkillPublishResponse

router = APIRouter(prefix='/api/v1/skills', tags=['skills'])


@router.get('')
def list_known_skills(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    names = sorted({row[0] for row in db.query(Submission.skill_name).all() if row[0]})
    return {'skills': names}


@router.post('/{skill_name}/publish', response_model=SkillPublishResponse, status_code=status.HTTP_202_ACCEPTED)
def publish_skill(
    skill_name: str,
    payload: PublishRequest,
    user: User = Depends(require_role('maintainer')),
    db: Session = Depends(get_db),
):
    submission = None
    if payload.submission_id is not None:
        submission = db.query(Submission).filter(Submission.id == payload.submission_id).one_or_none()
    else:
        submission = (
            db.query(Submission)
            .filter(Submission.skill_name == skill_name)
            .order_by(Submission.id.desc())
            .first()
        )
    if submission is None:
        raise HTTPException(status_code=404, detail='submission not found for publish')
    if submission.skill_name != skill_name:
        raise HTTPException(status_code=409, detail='submission does not match requested skill name')
    if submission.status not in {'approved', 'validated', 'promoted'}:
        raise HTTPException(status_code=409, detail=f'submission status {submission.status!r} cannot be published')
    job = enqueue_job(
        db,
        kind='publish_submission',
        payload={'submission_id': submission.id, 'skill_name': submission.skill_name},
        requested_by=user,
        submission_id=submission.id,
        note=payload.note,
    )
    return SkillPublishResponse(
        ok=True,
        skill_name=skill_name,
        status='queued',
        detail='publish job queued',
        job=serialize_job(job),
    )
