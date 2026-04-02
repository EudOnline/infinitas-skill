"""Inspection summary aggregation helpers for hosted server operations."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def isoformat_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


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
        "finished_at": isoformat_or_none(job.finished_at),
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


def build_jobs_inspection_summary(session: Session, *, limit: int) -> dict[str, Any]:
    from server.models import Job

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

    return {
        "counts": {
            "queued": int(status_counts.get("queued", 0)),
            "running": int(status_counts.get("running", 0)),
            "failed": int(status_counts.get("failed", 0)),
            "completed": int(status_counts.get("completed", 0)),
            "warning": int(warning_count or 0),
        },
        "by_status": dict(sorted((str(key), int(value)) for key, value in status_counts.items())),
        "recent_failed": [serialize_job(item) for item in recent_failed],
        "recent_queued_or_running": [serialize_job(item) for item in recent_active],
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
