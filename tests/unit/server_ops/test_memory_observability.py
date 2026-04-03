from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from infinitas_skill.server.memory_observability import summarize_memory_observability
from server.models import AuditEvent, Base, Job


def test_summarize_memory_observability_groups_writeback_curation_and_jobs() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:0",
                        event_type="memory.writeback.failed",
                        actor_ref="principal:0",
                        occurred_at=datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc),
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
                        aggregate_id="mw:1",
                        event_type="memory.writeback.stored",
                        actor_ref="principal:1",
                        occurred_at=datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
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
                        aggregate_id="memory_writeback:0",
                        event_type="memory.curation.failed",
                        actor_ref="system:memory-curation",
                        occurred_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive", "status": "failed"}),
                    ),
                    AuditEvent(
                        aggregate_type="memory_curation",
                        aggregate_id="memory_writeback:1",
                        event_type="memory.curation.archived",
                        actor_ref="system:memory-curation",
                        occurred_at=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive", "status": "archived"}),
                    ),
                    Job(
                        kind="memory_curation",
                        status="failed",
                        created_at=datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive"}),
                        note="failed archive",
                    ),
                    Job(
                        kind="memory_curation",
                        status="completed",
                        created_at=datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive", "apply": True}),
                        note="completed archive",
                    ),
                    AuditEvent(
                        aggregate_type="memory_curation",
                        aggregate_id="memory_writeback:2",
                        event_type="memory.curation.archived",
                        actor_ref="system:memory-curation",
                        occurred_at=datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps({"action": "archive", "status": "archived"}),
                    ),
                    AuditEvent(
                        aggregate_type="memory_writeback",
                        aggregate_id="mw:2",
                        event_type="memory.writeback.failed",
                        actor_ref="principal:2",
                        occurred_at=datetime(2026, 4, 3, 11, 30, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                            {
                                "status": "failed",
                                "backend": "memo0",
                                "lifecycle_event": "task.review.approve",
                            }
                        ),
                    ),
                ]
            )
            session.commit()

            payload = summarize_memory_observability(
                session,
                limit=20,
                job_limit=10,
                now="2026-04-03T12:00:00Z",
                window_hours=24,
            )

        assert payload["writeback"]["writeback_status_counts"]["stored"] == 1
        assert payload["writeback"]["writeback_status_counts"]["failed"] == 2
        assert payload["curation"]["status_counts"]["archived"] == 2
        assert payload["curation"]["status_counts"]["failed"] == 1
        assert payload["jobs"]["status_counts"]["completed"] == 1
        assert payload["jobs"]["status_counts"]["failed"] == 1
        assert payload["jobs"]["recent"][0]["kind"] == "memory_curation"
        assert payload["baselines"]["window_hours"] == 24
        assert payload["baselines"]["writeback"]["recent"]["totals"]["count"] == 2
        assert payload["baselines"]["writeback"]["previous"]["totals"]["count"] == 1
        assert payload["baselines"]["writeback"]["delta"]["stored_rate"] == 0.5
        assert payload["baselines"]["writeback"]["delta"]["failed_rate"] == -0.5
        assert payload["baselines"]["curation"]["delta"]["archived_rate"] == 1.0
        assert payload["baselines"]["jobs"]["delta"]["completed_rate"] == 1.0
    finally:
        engine.dispose()
