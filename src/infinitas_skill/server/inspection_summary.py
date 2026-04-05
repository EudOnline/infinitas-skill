"""Inspection summary aggregation helpers for hosted server operations."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _normalize_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def isoformat_or_none(value: Any) -> str | None:
    normalized = _normalize_datetime(value)
    if normalized is None:
        return None
    return normalized.isoformat().replace("+00:00", "Z")


def _seconds_since(value: Any, *, now: datetime) -> int | None:
    normalized = _normalize_datetime(value)
    if normalized is None:
        return None
    return max(int((now - normalized).total_seconds()), 0)


def _job_running_age_seconds(job: Any, *, now: datetime) -> int | None:
    started_at = getattr(job, "started_at", None) or getattr(job, "created_at", None)
    return _seconds_since(started_at, now=now)


def _job_is_stale_running(job: Any, *, now: datetime) -> bool:
    if getattr(job, "status", "") != "running":
        return False
    lease_expires_at = _normalize_datetime(getattr(job, "lease_expires_at", None))
    return lease_expires_at is None or lease_expires_at <= now


def serialize_job(job: Any) -> dict[str, Any]:
    from server.jobs import load_job_payload

    payload = load_job_payload(job)
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "release_id": job.release_id or payload.get("release_id"),
        "note": job.note or "",
        "error_message": job.error_message or "",
        "created_at": isoformat_or_none(job.created_at),
        "started_at": isoformat_or_none(job.started_at),
        "heartbeat_at": isoformat_or_none(getattr(job, "heartbeat_at", None)),
        "lease_expires_at": isoformat_or_none(getattr(job, "lease_expires_at", None)),
        "finished_at": isoformat_or_none(job.finished_at),
        "attempt_count": int(getattr(job, "attempt_count", 0) or 0),
    }


def load_latest_review_state_by_exposure(session: Session) -> dict[int, str]:
    from server.modules.review.models import ReviewCase

    latest: dict[int, str] = {}
    rows = session.execute(select(ReviewCase).order_by(ReviewCase.id.asc())).scalars()
    for item in rows:
        latest[item.exposure_id] = item.state or "none"
    return latest


def build_release_inspection_summary(session: Session) -> dict[str, Any]:
    from server.modules.exposure.models import Exposure

    latest_review_state = load_latest_review_state_by_exposure(session)
    audience_counts: Counter[str] = Counter()
    audience_review_state: defaultdict[str, Counter[str]] = defaultdict(Counter)

    exposures = session.execute(select(Exposure).order_by(Exposure.id.asc())).scalars()
    for exposure in exposures:
        audience = exposure.audience_type or "unknown"
        review_state = latest_review_state.get(exposure.id, "none")
        audience_counts[audience] += 1
        audience_review_state[audience][review_state] += 1

    return {
        "by_audience": dict(sorted(audience_counts.items())),
        "by_audience_review_state": {
            audience: dict(sorted(states.items()))
            for audience, states in sorted(audience_review_state.items())
        },
    }


def build_jobs_inspection_summary(
    session: Session,
    *,
    limit: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    from server.models import Job

    checked_at = now or datetime.now(timezone.utc)
    status_counts = {
        status: count
        for status, count in session.execute(
            select(Job.status, func.count()).group_by(Job.status)
        ).all()
    }
    warning_count = session.execute(
        select(func.count()).select_from(Job).where(Job.log.contains("WARNING:"))
    ).scalar_one()

    recent_failed = session.execute(
        select(Job).where(Job.status == "failed").order_by(Job.id.desc()).limit(limit)
    ).scalars()
    recent_active = session.execute(
        select(Job)
        .where(Job.status.in_(("queued", "running")))
        .order_by(Job.id.desc())
        .limit(limit)
    ).scalars()
    recent_warning = session.execute(
        select(Job).where(Job.log.contains("WARNING:")).order_by(Job.id.desc()).limit(limit)
    ).scalars()
    running_jobs = list(
        session.execute(
            select(Job).where(Job.status == "running").order_by(Job.id.desc())
        ).scalars()
    )
    queued_jobs = list(
        session.execute(
            select(Job).where(Job.status == "queued").order_by(Job.id.desc())
        ).scalars()
    )
    recent_reclaimed = session.execute(
        select(Job)
        .where(Job.log.contains("reclaimed stale lease"))
        .order_by(Job.id.desc())
        .limit(limit)
    ).scalars()
    stale_running = [job for job in running_jobs if _job_is_stale_running(job, now=checked_at)]
    running_ages = [
        age
        for age in (_job_running_age_seconds(job, now=checked_at) for job in running_jobs)
        if age is not None
    ]
    queued_ages = [
        age
        for age in (
            _seconds_since(getattr(job, "created_at", None), now=checked_at)
            for job in queued_jobs
        )
        if age is not None
    ]

    return {
        "counts": {
            "queued": int(status_counts.get("queued", 0)),
            "running": int(status_counts.get("running", 0)),
            "stale_running": len(stale_running),
            "failed": int(status_counts.get("failed", 0)),
            "completed": int(status_counts.get("completed", 0)),
            "warning": int(warning_count or 0),
        },
        "by_status": dict(sorted((str(key), int(value)) for key, value in status_counts.items())),
        "ages": {
            "longest_running_seconds": max(running_ages) if running_ages else None,
            "oldest_queued_seconds": max(queued_ages) if queued_ages else None,
        },
        "recent_failed": [serialize_job(item) for item in recent_failed],
        "recent_queued_or_running": [serialize_job(item) for item in recent_active],
        "recent_stale_running": [serialize_job(item) for item in stale_running[:limit]],
        "recent_reclaimed": [serialize_job(item) for item in recent_reclaimed],
        "recent_warning": [serialize_job(item) for item in recent_warning],
    }


def maybe_add_alert(
    alerts: list[dict[str, Any]], *, kind: str, label: str, actual: int, maximum: int | None
) -> None:
    if maximum is None:
        return
    if actual <= maximum:
        return
    alerts.append(
        {
            "kind": kind,
            "label": label,
            "actual": actual,
            "max": maximum,
            "message": f"{label} exceeded threshold: {actual} > {maximum}",
        }
    )


__all__ = [
    "build_jobs_inspection_summary",
    "build_release_inspection_summary",
    "load_latest_review_state_by_exposure",
    "maybe_add_alert",
    "serialize_job",
]
