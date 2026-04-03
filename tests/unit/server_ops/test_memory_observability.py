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
                        aggregate_id="mw:1",
                        event_type="memory.writeback.failed",
                        actor_ref="principal:1",
                        occurred_at=datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
                        payload_json=json.dumps(
                            {
                                "status": "failed",
                                "backend": "memo0",
                                "lifecycle_event": "task.review.approve",
                            }
                        ),
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
                        status="queued",
                        payload_json=json.dumps({"action": "archive", "apply": True}),
                        note="queued archive",
                    ),
                ]
            )
            session.commit()

            payload = summarize_memory_observability(session, limit=20, job_limit=10)

        assert payload["writeback"]["writeback_status_counts"]["failed"] == 1
        assert payload["curation"]["status_counts"]["archived"] == 1
        assert payload["jobs"]["status_counts"]["queued"] == 1
        assert payload["jobs"]["recent"][0]["kind"] == "memory_curation"
    finally:
        engine.dispose()

