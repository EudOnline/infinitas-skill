from __future__ import annotations

import json

from sqlalchemy.orm import Session

from server.models import Job, User, utcnow


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


def _optional_positive_int(value: object) -> int | None:
    try:
        candidate = int(value or 0)
    except (TypeError, ValueError):
        return None
    return candidate if candidate > 0 else None


def append_job_log(job: Job, *lines: str):
    existing = job.log or ''
    parts = [existing.rstrip()] if existing.strip() else []
    for line in lines:
        text = str(line).rstrip()
        if text:
            parts.append(text)
    job.log = '\n'.join(parts).strip() + ('\n' if parts else '')


def enqueue_job(
    db: Session,
    *,
    kind: str,
    payload: dict | None,
    requested_by: User | None,
    release_id: int | None = None,
    note: str = '',
    commit: bool = True,
) -> Job:
    normalized_payload = payload or {}
    job = Job(
        kind=kind,
        status='queued',
        payload_json=json.dumps(normalized_payload, ensure_ascii=False),
        release_id=release_id or _optional_positive_int(normalized_payload.get('release_id')),
        requested_by_user_id=(requested_by.id if requested_by is not None else None),
        note=note or '',
    )
    append_job_log(job, f'queued job {kind}', f'payload={json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True)}')
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
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
