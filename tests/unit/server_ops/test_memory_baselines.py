from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from infinitas_skill.server.memory_baselines import summarize_memory_baselines
from server.models import AuditEvent, Base, Job


def test_summarize_memory_baselines_compares_recent_window_to_previous_window() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    now = datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:1",
                        event_type="memory.writeback.stored",
                        actor_ref="principal:1",
                        occurred_at=now - timedelta(hours=1),
                        payload_json=json.dumps(
                            {
                                "status": "stored",
                                "backend": "memo0",
                                "lifecycle_event": "task.release.ready",
                            }
                        ),
                    ),
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:2",
                        event_type="memory.writeback.failed",
                        actor_ref="principal:1",
                        occurred_at=now - timedelta(hours=2),
                        payload_json=json.dumps(
                            {
                                "status": "failed",
                                "backend": "memo0",
                                "lifecycle_event": "task.review.approve",
                            }
                        ),
                    ),
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:3",
                        event_type="memory.writeback.stored",
                        actor_ref="principal:1",
                        occurred_at=now - timedelta(hours=30),
                        payload_json=json.dumps(
                            {
                                "status": "stored",
                                "backend": "memo0",
                                "lifecycle_event": "task.release.ready",
                            }
                        ),
                    ),
                    AuditEvent(
                        aggregate_type="memory_curation",
                        aggregate_id="memory_writeback:1",
                        event_type="memory.curation.archived",
                        actor_ref="system:memory-curation",
                        occurred_at=now - timedelta(hours=3),
                        payload_json=json.dumps({"action": "archive", "status": "archived"}),
                    ),
                    AuditEvent(
                        aggregate_type="memory_curation",
                        aggregate_id="memory_writeback:3",
                        event_type="memory.curation.failed",
                        actor_ref="system:memory-curation",
                        occurred_at=now - timedelta(hours=28),
                        payload_json=json.dumps({"action": "prune", "status": "failed"}),
                    ),
                    Job(
                        kind="memory_curation",
                        status="completed",
                        created_at=now - timedelta(hours=4),
                        payload_json=json.dumps({"action": "archive"}),
                        note="completed archive",
                    ),
                    Job(
                        kind="memory_curation",
                        status="failed",
                        created_at=now - timedelta(hours=26),
                        payload_json=json.dumps({"action": "prune"}),
                        note="failed prune",
                    ),
                ]
            )
            session.commit()

            payload = summarize_memory_baselines(
                session,
                now=now,
                window_hours=24,
            )

        assert payload["ok"] is True
        assert payload["writeback"]["recent"]["totals"]["count"] == 2
        assert payload["writeback"]["recent"]["status_rates"]["stored"] == 0.5
        assert payload["writeback"]["previous"]["totals"]["count"] == 1
        assert payload["curation"]["recent"]["status_rates"]["archived"] == 1.0
        assert payload["jobs"]["recent"]["status_rates"]["completed"] == 1.0
        assert payload["jobs"]["delta"]["failed_rate"] == -1.0
    finally:
        engine.dispose()
