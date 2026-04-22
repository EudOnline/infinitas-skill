from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from server.models import Job, User, utcnow

DEFAULT_JOB_LEASE_SECONDS = 300
MAX_JOB_ATTEMPTS = 10


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


def _lease_deadline(claimed_at: datetime, *, lease_seconds: int) -> datetime:
    return claimed_at + timedelta(seconds=max(int(lease_seconds), 1))


def _running_job_is_stale(now: datetime):
    return and_(
        Job.status == 'running',
        or_(
            Job.lease_expires_at.is_(None),
            Job.lease_expires_at <= now,
        ),
    )


def _active_status_clause(status: str, *, now: datetime):
    if status != 'running':
        return Job.status == status
    return and_(
        Job.status == 'running',
        Job.lease_expires_at.is_not(None),
        Job.lease_expires_at > now,
    )


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
    append_job_log(
        job,
        f'queued job {kind}',
        f'payload={json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True)}',
    )
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    return job


def has_active_job(
    db: Session,
    *,
    kind: str,
    release_id: int | None = None,
    statuses: tuple[str, ...] = ('queued', 'running'),
    now: datetime | None = None,
) -> bool:
    checked_at = now or utcnow()
    predicates = [_active_status_clause(status, now=checked_at) for status in statuses]
    query = db.query(Job).filter(Job.kind == kind)
    if predicates:
        query = query.filter(or_(*predicates))
    if release_id is not None:
        query = query.filter(Job.release_id == release_id)
    return query.first() is not None


def claim_next_job(db: Session, *, lease_seconds: int = DEFAULT_JOB_LEASE_SECONDS) -> Job | None:
    claimed_at = utcnow()
    lease_expires_at = _lease_deadline(claimed_at, lease_seconds=lease_seconds)
    next_job_id = (
        select(Job.id)
        .where(Job.status == 'queued')
        .order_by(Job.id.asc())
        .limit(1)
        .scalar_subquery()
    )
    job_id = db.execute(
        update(Job)
        .where(Job.id == next_job_id)
        .where(Job.status == 'queued')
        .values(
            status='running',
            started_at=claimed_at,
            heartbeat_at=claimed_at,
            lease_expires_at=lease_expires_at,
            attempt_count=Job.attempt_count + 1,
            updated_at=claimed_at,
        )
        .returning(Job.id)
    ).scalar_one_or_none()

    reclaimed = False
    if job_id is None:
        stale_job_id = (
            select(Job.id)
            .where(_running_job_is_stale(claimed_at))
            .where(Job.attempt_count < MAX_JOB_ATTEMPTS)
            .order_by(Job.id.asc())
            .limit(1)
            .scalar_subquery()
        )
        job_id = db.execute(
            update(Job)
            .where(Job.id == stale_job_id)
            .where(_running_job_is_stale(claimed_at))
            .values(
                status='running',
                started_at=claimed_at,
                heartbeat_at=claimed_at,
                lease_expires_at=lease_expires_at,
                attempt_count=Job.attempt_count + 1,
                updated_at=claimed_at,
            )
            .returning(Job.id)
        ).scalar_one_or_none()
        reclaimed = job_id is not None

    if job_id is None:
        db.rollback()
        return None
    job = db.get(Job, int(job_id))
    if job is None:
        db.rollback()
        raise RuntimeError(f'claimed job {job_id} disappeared before refresh')
    if reclaimed:
        append_job_log(
            job,
            f'reclaimed stale lease at {_iso(claimed_at)}',
            f'lease_expires_at={_iso(lease_expires_at)}',
        )
    else:
        append_job_log(
            job,
            f'claimed at {_iso(claimed_at)}',
            f'lease_expires_at={_iso(lease_expires_at)}',
        )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def heartbeat_job(
    db: Session,
    job: Job,
    *,
    heartbeat_at: datetime | None = None,
    lease_seconds: int = DEFAULT_JOB_LEASE_SECONDS,
    commit: bool = True,
) -> Job:
    next_heartbeat = heartbeat_at or utcnow()
    job.heartbeat_at = next_heartbeat
    job.lease_expires_at = _lease_deadline(next_heartbeat, lease_seconds=lease_seconds)
    job.updated_at = next_heartbeat
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    return job


def complete_job(
    db: Session,
    job: Job,
    *,
    finished_at: datetime | None = None,
    commit: bool = True,
) -> Job:
    completed_at = finished_at or utcnow()
    job.status = 'completed'
    job.finished_at = completed_at
    job.heartbeat_at = None
    job.lease_expires_at = None
    job.error_message = ''
    job.updated_at = completed_at
    append_job_log(job, f'completed at {_iso(completed_at)}')
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    return job


def fail_job(
    db: Session,
    job: Job,
    *,
    error_message: str,
    finished_at: datetime | None = None,
    commit: bool = True,
) -> Job:
    failed_at = finished_at or utcnow()
    job.status = 'failed'
    job.finished_at = failed_at
    job.heartbeat_at = None
    job.lease_expires_at = None
    job.error_message = str(error_message)
    job.updated_at = failed_at
    append_job_log(job, f'ERROR: {error_message}')
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    return job
