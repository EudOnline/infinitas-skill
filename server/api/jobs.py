from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.auth import require_role
from server.db import get_db
from server.jobs import get_job_or_404, serialize_job
from server.models import User
from server.schemas import JobView

router = APIRouter(prefix='/api/v1/jobs', tags=['jobs'])


@router.get('/{job_id}', response_model=JobView)
def get_job(
    job_id: int,
    _: User = Depends(require_role('maintainer', 'contributor')),
    db: Session = Depends(get_db),
):
    return serialize_job(get_job_or_404(db, job_id))
