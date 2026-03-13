from __future__ import annotations

import json

from sqlalchemy.orm import Session

from server.models import Job, User, utcnow
from server.schemas import JobView


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace('+00:00', 'Z')


def load_job_payload(job: Job) -> dict:
    try:
        payload = json.loads(job.payload_json or '{}')
    except json.JSONDecodeError:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def append_job_log(job: Job, *lines: str):
    existing = job.log or ''
    parts = [existing.rstrip()] if existing.strip() else []
    for line in lines:
        text = str(line).rstrip()
        if text:
            parts.append(text)
    job.log = '\n'.join(parts).strip() + ('\n' if parts else '')


def serialize_job(job: Job) -> JobView:
    return JobView(
        id=job.id,
        kind=job.kind,
        status=job.status,
        submission_id=job.submission_id,
        requested_by=job.requested_by.username if job.requested_by else None,
        note=job.note or '',
        log=job.log or '',
        error_message=job.error_message or '',
        created_at=_iso(job.created_at) or '',
        updated_at=_iso(job.updated_at) or '',
        started_at=_iso(job.started_at),
        finished_at=_iso(job.finished_at),
    )


def enqueue_job(
    db: Session,
    *,
    kind: str,
    payload: dict | None,
    requested_by: User,
    submission_id: int | None = None,
    note: str = '',
) -> Job:
    job = Job(
        kind=kind,
        status='queued',
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
        submission_id=submission_id,
        requested_by_user_id=requested_by.id,
        note=note or '',
    )
    append_job_log(job, f'queued job {kind}', f'payload={json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)}')
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job_or_404(db: Session, job_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if job is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail='job not found')
    return job


def claim_next_job(db: Session) -> Job | None:
    job = db.query(Job).filter(Job.status == 'queued').order_by(Job.id.asc()).first()
    if job is None:
        return None
    job.status = 'running'
    job.started_at = utcnow()
    append_job_log(job, f'claimed at {_iso(job.started_at)}')
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
