from __future__ import annotations

import json
from types import SimpleNamespace

from infinitas_skill.server.memory_curation import summarize_memory_curation_plan


class _FakeScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)


class _FakeSession:
    def __init__(self, events):
        self._events = list(events)

    def scalars(self, _query):
        return _FakeScalarResult(self._events)


def _event(
    *,
    event_id: int,
    status: str,
    lifecycle_event: str,
    backend: str,
    occurred_at: str,
    payload: dict,
):
    return SimpleNamespace(
        id=event_id,
        aggregate_type="memory_writeback",
        aggregate_id=f"mw:{event_id}",
        event_type=f"memory.writeback.{status}",
        payload_json=json.dumps(
            {
                "status": status,
                "backend": backend,
                "lifecycle_event": lifecycle_event,
                "payload": payload,
            }
        ),
        occurred_at=occurred_at,
    )


def test_summarize_memory_curation_plan_groups_duplicates_and_expired_candidates() -> None:
    session = _FakeSession(
        [
            _event(
                event_id=3,
                status="stored",
                lifecycle_event="task.authoring.create_draft",
                backend="memo0",
                occurred_at="2026-03-01T10:00:00Z",
                payload={"qualified_name": "team/demo", "state": "draft"},
            ),
            _event(
                event_id=2,
                status="stored",
                lifecycle_event="task.review.approve",
                backend="memo0",
                occurred_at="2026-04-03T09:00:00Z",
                payload={"qualified_name": "team/demo", "decision": "approve"},
            ),
            _event(
                event_id=1,
                status="stored",
                lifecycle_event="task.review.approve",
                backend="memo0",
                occurred_at="2026-04-03T08:00:00Z",
                payload={"qualified_name": "team/demo", "decision": "approve"},
            ),
        ]
    )

    payload = summarize_memory_curation_plan(
        session,
        limit=20,
        now="2026-04-03T12:00:00Z",
    )

    assert payload["candidate_counts"]["duplicate_groups"] == 1
    assert payload["candidate_counts"]["expired_by_policy"] == 1
    assert payload["top_duplicate_groups"][0]["count"] == 2
    assert (
        payload["top_expired_lifecycle_events"][0]["lifecycle_event"]
        == "task.authoring.create_draft"
    )
