from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import AuditEvent, Job


def _payload(raw: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_datetime(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    return datetime.now(timezone.utc)


def _normalized_event_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _status_rate_summary(statuses: list[str]) -> dict[str, float]:
    counts: Counter[str] = Counter(statuses)
    total = len(statuses)
    if total <= 0:
        return {}
    return {key: round(value / total, 3) for key, value in sorted(counts.items())}


def _delta(recent: float, previous: float) -> float:
    return round(recent - previous, 3)


def _window_bounds(now: datetime, window_hours: int) -> tuple[datetime, datetime]:
    window = timedelta(hours=window_hours)
    return now - window, now - (window * 2)


def _event_window(
    event_time: datetime | None,
    *,
    recent_start: datetime,
    previous_start: datetime,
) -> str | None:
    normalized = _normalized_event_time(event_time)
    if normalized is None:
        return None
    if normalized >= recent_start:
        return "recent"
    if normalized >= previous_start:
        return "previous"
    return None


def summarize_memory_baselines(
    session: Session,
    *,
    now: str | datetime | None = None,
    window_hours: int = 24,
) -> dict[str, Any]:
    resolved_now = _as_datetime(now)
    normalized_window_hours = (
        window_hours if isinstance(window_hours, int) and window_hours > 0 else 24
    )
    recent_start, previous_start = _window_bounds(resolved_now, normalized_window_hours)

    windows = {
        "writeback": {"recent": [], "previous": []},
        "curation": {"recent": [], "previous": []},
        "jobs": {"recent": [], "previous": []},
    }

    writeback_events = session.scalars(
        select(AuditEvent).where(AuditEvent.aggregate_type == "memory_writeback")
    ).all()
    for event in writeback_events:
        bucket = _event_window(
            event.occurred_at,
            recent_start=recent_start,
            previous_start=previous_start,
        )
        if bucket is None:
            continue
        status = str(_payload(event.payload_json).get("status") or "").strip().lower() or "unknown"
        windows["writeback"][bucket].append(status)

    curation_events = session.scalars(
        select(AuditEvent).where(AuditEvent.aggregate_type == "memory_curation")
    ).all()
    for event in curation_events:
        bucket = _event_window(
            event.occurred_at,
            recent_start=recent_start,
            previous_start=previous_start,
        )
        if bucket is None:
            continue
        status = (
            str(event.event_type or "")
            .strip()
            .lower()
            .removeprefix("memory.curation.")
            or "unknown"
        )
        windows["curation"][bucket].append(status)

    jobs = session.scalars(select(Job).where(Job.kind == "memory_curation")).all()
    for job in jobs:
        bucket = _event_window(
            job.created_at,
            recent_start=recent_start,
            previous_start=previous_start,
        )
        if bucket is None:
            continue
        status = str(job.status or "").strip().lower() or "unknown"
        windows["jobs"][bucket].append(status)

    def summarize_status_window(statuses: list[str]) -> dict[str, Any]:
        return {
            "totals": {"count": len(statuses)},
            "status_rates": _status_rate_summary(statuses),
        }

    writeback_recent = summarize_status_window(windows["writeback"]["recent"])
    writeback_previous = summarize_status_window(windows["writeback"]["previous"])
    curation_recent = summarize_status_window(windows["curation"]["recent"])
    curation_previous = summarize_status_window(windows["curation"]["previous"])
    jobs_recent = summarize_status_window(windows["jobs"]["recent"])
    jobs_previous = summarize_status_window(windows["jobs"]["previous"])

    return {
        "ok": True,
        "window_hours": normalized_window_hours,
        "generated_at": resolved_now.isoformat().replace("+00:00", "Z"),
        "writeback": {
            "recent": writeback_recent,
            "previous": writeback_previous,
            "delta": {
                "stored_rate": _delta(
                    writeback_recent["status_rates"].get("stored", 0.0),
                    writeback_previous["status_rates"].get("stored", 0.0),
                ),
                "failed_rate": _delta(
                    writeback_recent["status_rates"].get("failed", 0.0),
                    writeback_previous["status_rates"].get("failed", 0.0),
                ),
            },
        },
        "curation": {
            "recent": curation_recent,
            "previous": curation_previous,
            "delta": {
                "archived_rate": _delta(
                    curation_recent["status_rates"].get("archived", 0.0),
                    curation_previous["status_rates"].get("archived", 0.0),
                ),
                "pruned_rate": _delta(
                    curation_recent["status_rates"].get("pruned", 0.0),
                    curation_previous["status_rates"].get("pruned", 0.0),
                ),
                "failed_rate": _delta(
                    curation_recent["status_rates"].get("failed", 0.0),
                    curation_previous["status_rates"].get("failed", 0.0),
                ),
            },
        },
        "jobs": {
            "recent": jobs_recent,
            "previous": jobs_previous,
            "delta": {
                "completed_rate": _delta(
                    jobs_recent["status_rates"].get("completed", 0.0),
                    jobs_previous["status_rates"].get("completed", 0.0),
                ),
                "failed_rate": _delta(
                    jobs_recent["status_rates"].get("failed", 0.0),
                    jobs_previous["status_rates"].get("failed", 0.0),
                ),
            },
        },
    }


__all__ = ["summarize_memory_baselines"]
