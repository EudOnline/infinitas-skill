from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from server.auth import get_current_user, require_role
from server.db import get_db
from server.models import Submission, User
from server.schemas import SkillPublishResponse

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
    _: User = Depends(require_role('maintainer')),
):
    return SkillPublishResponse(
        ok=True,
        skill_name=skill_name,
        status='queued',
        detail='publish queueing is scaffolded; worker-backed execution lands in Task 5',
    )
