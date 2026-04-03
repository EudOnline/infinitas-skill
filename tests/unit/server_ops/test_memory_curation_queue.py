from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from server.models import AuditEvent, Base, Job
from server.worker import process_job


def _configure_server_env(monkeypatch, tmp_path):
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
    monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "disabled")
    monkeypatch.setenv("INFINITAS_MEMORY_CONTEXT_ENABLED", "0")
    monkeypatch.setenv("INFINITAS_MEMORY_WRITE_ENABLED", "0")


def test_process_job_executes_memory_curation_archive_job(monkeypatch, tmp_path) -> None:
    _configure_server_env(monkeypatch, tmp_path)

    from infinitas_skill.server.memory_curation_queue import enqueue_memory_curation_job
    from server.db import get_engine, get_session_factory

    Base.metadata.create_all(get_engine())
    session_factory = get_session_factory()

    with session_factory() as session:
        session.add(
            AuditEvent(
                aggregate_type="memory_writeback",
                aggregate_id="mw:1",
                event_type="memory.writeback.stored",
                actor_ref="principal:1",
                occurred_at=datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
                payload_json=json.dumps(
                    {
                        "status": "stored",
                        "backend": "memo0",
                        "memory_id": "memory-1",
                        "lifecycle_event": "task.authoring.create_draft",
                        "payload": {"qualified_name": "team/demo", "state": "draft"},
                    }
                ),
            )
        )
        job = enqueue_memory_curation_job(
            session,
            action="archive",
            apply=True,
            limit=50,
            max_actions=5,
            actor_ref="system:test",
        )
        session.commit()
        job_id = int(job.id)

    process_job(job_id)

    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.kind == "memory_curation"
        assert job.status == "completed"
        assert "archived=1" in (job.log or "")
        event = session.scalar(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "memory_curation")
            .where(AuditEvent.event_type == "memory.curation.archived")
        )
        assert event is not None


def test_resolve_memory_curation_job_options_uses_server_policy(monkeypatch) -> None:
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "test")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", "[]")
    monkeypatch.setenv("INFINITAS_SERVER_MEMORY_CURATION_ACTION", "prune")
    monkeypatch.setenv("INFINITAS_SERVER_MEMORY_CURATION_APPLY", "1")
    monkeypatch.setenv("INFINITAS_SERVER_MEMORY_CURATION_LIMIT", "33")
    monkeypatch.setenv("INFINITAS_SERVER_MEMORY_CURATION_MAX_ACTIONS", "7")
    monkeypatch.setenv("INFINITAS_SERVER_MEMORY_CURATION_ACTOR_REF", "system:scheduled-curation")

    from infinitas_skill.server.memory_curation_queue import resolve_memory_curation_job_options

    options = resolve_memory_curation_job_options(use_server_policy=True)

    assert options["action"] == "prune"
    assert options["apply"] is True
    assert options["limit"] == 33
    assert options["max_actions"] == 7
    assert options["actor_ref"] == "system:scheduled-curation"
