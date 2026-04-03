from __future__ import annotations

import json
from types import SimpleNamespace

from infinitas_skill.server.memory_health import summarize_memory_writeback


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


def _event(*, event_id: int, status: str, lifecycle_event: str, backend: str, occurred_at: str):
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
            }
        ),
        occurred_at=occurred_at,
    )


def test_summarize_memory_writeback_groups_recent_statuses_and_failures() -> None:
    session = _FakeSession(
        [
            _event(
                event_id=3,
                status="failed",
                lifecycle_event="task.review.approve",
                backend="memo0",
                occurred_at="2026-04-03T10:00:00Z",
            ),
            _event(
                event_id=2,
                status="stored",
                lifecycle_event="task.release.ready",
                backend="memo0",
                occurred_at="2026-04-03T09:00:00Z",
            ),
            _event(
                event_id=1,
                status="disabled",
                lifecycle_event="task.authoring.create_draft",
                backend="noop",
                occurred_at="2026-04-03T08:00:00Z",
            ),
        ]
    )

    payload = summarize_memory_writeback(session, limit=10)

    assert payload["writeback_status_counts"] == {
        "failed": 1,
        "stored": 1,
        "disabled": 1,
    }
    assert payload["backend_names"] == ["memo0", "noop"]
    assert payload["top_failed_lifecycle_events"] == [
        {"count": 1, "lifecycle_event": "task.review.approve"}
    ]
    assert payload["recent_failures"][0]["lifecycle_event"] == "task.review.approve"
