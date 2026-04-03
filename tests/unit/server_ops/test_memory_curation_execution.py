from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from infinitas_skill.memory.contracts import MemoryDeleteResult
from infinitas_skill.server.memory_curation import execute_memory_curation
from server.models import AuditEvent, Base


class _FakeDeleteProvider:
    backend_name = "memo0"
    capabilities = {"read": True, "write": True, "delete": True}

    def __init__(self):
        self.delete_calls: list[str] = []

    def delete(self, *, memory_id: str) -> MemoryDeleteResult:
        self.delete_calls.append(memory_id)
        return MemoryDeleteResult(status="deleted", backend=self.backend_name, memory_id=memory_id)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return factory()


def _add_writeback(
    session: Session,
    *,
    event_id: str,
    occurred_at: datetime,
    lifecycle_event: str,
    payload: dict,
    memory_id: str | None,
) -> None:
    body = {
        "status": "stored",
        "backend": "memo0",
        "lifecycle_event": lifecycle_event,
        "payload": payload,
    }
    if memory_id:
        body["memory_id"] = memory_id
    session.add(
        AuditEvent(
            aggregate_type="memory_writeback",
            aggregate_id=event_id,
            event_type="memory.writeback.stored",
            actor_ref="principal:1",
            occurred_at=occurred_at,
            payload_json=json.dumps(body),
        )
    )


def test_execute_memory_curation_prune_dry_run_does_not_delete() -> None:
    session = _session()
    try:
        _add_writeback(
            session,
            event_id="mw:1",
            occurred_at=datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc),
            lifecycle_event="task.review.approve",
            payload={"qualified_name": "team/demo", "decision": "approve"},
            memory_id="memory-1",
        )
        _add_writeback(
            session,
            event_id="mw:2",
            occurred_at=datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
            lifecycle_event="task.review.approve",
            payload={"qualified_name": "team/demo", "decision": "approve"},
            memory_id="memory-2",
        )
        session.commit()

        provider = _FakeDeleteProvider()
        payload = execute_memory_curation(
            session,
            action="prune",
            apply=False,
            provider=provider,
            max_actions=10,
            now="2026-04-03T12:00:00Z",
        )

        assert payload["action"] == "prune"
        assert payload["apply"] is False
        assert payload["execution"]["selected_candidates"] == 1
        assert payload["execution"]["pruned"] == 0
        assert provider.delete_calls == []
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.aggregate_type == "memory_curation")
        ).all()
        assert events == []
    finally:
        session.close()


def test_execute_memory_curation_prune_apply_deletes_guarded_duplicate_candidate() -> None:
    session = _session()
    try:
        _add_writeback(
            session,
            event_id="mw:1",
            occurred_at=datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc),
            lifecycle_event="task.review.approve",
            payload={"qualified_name": "team/demo", "decision": "approve"},
            memory_id="memory-1",
        )
        _add_writeback(
            session,
            event_id="mw:2",
            occurred_at=datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
            lifecycle_event="task.review.approve",
            payload={"qualified_name": "team/demo", "decision": "approve"},
            memory_id="memory-2",
        )
        session.commit()

        provider = _FakeDeleteProvider()
        payload = execute_memory_curation(
            session,
            action="prune",
            apply=True,
            provider=provider,
            max_actions=10,
            now="2026-04-03T12:00:00Z",
        )
        session.commit()

        assert payload["execution"]["pruned"] == 1
        assert provider.delete_calls == ["memory-1"]
        event = session.scalar(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "memory_curation")
            .where(AuditEvent.event_type == "memory.curation.pruned")
        )
        assert event is not None
        body = json.loads(event.payload_json)
        assert body["memory_id"] == "memory-1"
        assert body["action"] == "prune"
    finally:
        session.close()


def test_execute_memory_curation_archive_apply_audits_without_deleting() -> None:
    session = _session()
    try:
        _add_writeback(
            session,
            event_id="mw:3",
            occurred_at=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc),
            lifecycle_event="task.authoring.create_draft",
            payload={"qualified_name": "team/demo", "state": "draft"},
            memory_id="memory-3",
        )
        session.commit()

        provider = _FakeDeleteProvider()
        payload = execute_memory_curation(
            session,
            action="archive",
            apply=True,
            provider=provider,
            max_actions=10,
            now="2026-04-03T12:00:00Z",
        )
        session.commit()

        assert payload["execution"]["archived"] == 1
        assert provider.delete_calls == []
        event = session.scalar(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "memory_curation")
            .where(AuditEvent.event_type == "memory.curation.archived")
        )
        assert event is not None
    finally:
        session.close()
