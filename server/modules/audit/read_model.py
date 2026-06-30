from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import AuditEvent, Release, Skill
from server.modules.shared.formatting import iso_format


def json_payload(event: AuditEvent) -> dict[str, Any]:
    try:
        payload = json.loads(event.payload_json or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def activity_query():
    return select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())


def _prefetch_related(
    db: Session, events: list[AuditEvent]
) -> tuple[dict[int, Skill], dict[int, Release]]:
    """Batch-fetch Skills and Releases referenced by audit events.

    Collects all unique ``object_id`` and ``release_id`` values from event
    payloads and resolves them in two queries instead of 2*N.
    """
    object_ids: set[int] = set()
    release_ids: set[int] = set()
    for event in events:
        payload = json_payload(event)
        raw_oid = payload.get("object_id")
        if raw_oid:
            try:
                object_ids.add(int(raw_oid))
            except (TypeError, ValueError):
                pass
        raw_rid = payload.get("release_id")
        if raw_rid:
            try:
                release_ids.add(int(raw_rid))
            except (TypeError, ValueError):
                pass

    skills_by_id: dict[int, Skill] = {}
    if object_ids:
        skills_by_id = {
            s.id: s for s in db.scalars(select(Skill).where(Skill.id.in_(object_ids))).all()
        }

    releases_by_id: dict[int, Release] = {}
    if release_ids:
        releases_by_id = {
            r.id: r for r in db.scalars(select(Release).where(Release.id.in_(release_ids))).all()
        }

    return skills_by_id, releases_by_id


def _object_payload(
    payload: dict[str, Any], skills_by_id: dict[int, Skill]
) -> dict[str, Any] | None:
    object_id = payload.get("object_id")
    if not object_id:
        return None
    oid = int(object_id)
    skill = skills_by_id.get(oid)
    if skill is None:
        return {"id": oid, "name": None, "kind": None}
    return {
        "id": skill.id,
        "name": skill.display_name,
        "kind": "skill",
    }


def _release_payload(
    payload: dict[str, Any], releases_by_id: dict[int, Release]
) -> dict[str, Any] | None:
    release_id = payload.get("release_id")
    if not release_id:
        return None
    rid = int(release_id)
    release = releases_by_id.get(rid)
    if release is None:
        return {"id": rid, "state": None}
    return {"id": release.id, "state": release.state}


def normalize_event(db: Session, event: AuditEvent) -> dict[str, Any]:
    """Enrich an audit event with resolved object/release references.

    .. deprecated::
        Use :func:`normalize_events` for batch normalization instead of calling
        this in a loop — it performs 2 SQL queries per call.
    """
    payload = json_payload(event)
    return {
        "id": event.id,
        "actor": event.actor_ref or "system",
        "action": event.event_type,
        "object": _object_payload(payload, _prefetch_related(db, [event])[0]),
        "release": _release_payload(payload, _prefetch_related(db, [event])[1]),
        "outcome": payload.get("outcome") or "success",
        "timestamp": iso_format(event.occurred_at),
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "detail": payload,
    }


def normalize_events(db: Session, events: Sequence[AuditEvent]) -> list[dict[str, Any]]:
    """Batch-normalize audit events with resolved object/release references.

    Performs exactly 2 SQL queries regardless of event count (vs 2*N for the
    per-event :func:`normalize_event`).
    """
    skills_by_id, releases_by_id = _prefetch_related(db, list(events))
    results: list[dict[str, Any]] = []
    for event in events:
        payload = json_payload(event)
        results.append(
            {
                "id": event.id,
                "actor": event.actor_ref or "system",
                "action": event.event_type,
                "object": _object_payload(payload, skills_by_id),
                "release": _release_payload(payload, releases_by_id),
                "outcome": payload.get("outcome") or "success",
                "timestamp": iso_format(event.occurred_at),
                "aggregate_type": event.aggregate_type,
                "aggregate_id": event.aggregate_id,
                "detail": payload,
            }
        )
    return results
