from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from server.auth import get_current_user, require_role
from server.db import get_db
from server.jobs import get_job_or_404, serialize_job
from server.models import Job, Submission, User
from server.schemas import JobListView, JobView

router = APIRouter(prefix='/api/v1/jobs', tags=['jobs'])


@router.get('', response_model=JobListView)
def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if user.role != 'maintainer':
        query = query.join(Submission, Job.submission_id == Submission.id).filter(Submission.created_by_user_id == user.id)
    total = query.count()
    items = query.order_by(Job.updated_at.desc(), Job.id.desc()).limit(limit).all()
    return JobListView(items=[serialize_job(job) for job in items], total=total)


@router.get('/{job_id}', response_model=JobView)
def get_job(
    job_id: int,
    _: User = Depends(require_role('maintainer', 'contributor')),
    db: Session = Depends(get_db),
):
    return serialize_job(get_job_or_404(db, job_id))
