from __future__ import annotations

import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from infinitas_skill.memory.contracts import MemoryWriteResult
from infinitas_skill.memory.provider import NoopMemoryProvider
from server.models import AuditEvent, Base
from server.modules.memory.service import record_lifecycle_memory_event


class _FakeMemoryProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def __init__(self):
        self.calls = []

    def add(self, *, record, scope=None):  # noqa: ANN001
        self.calls.append({"record": record, "scope": scope})
        return MemoryWriteResult(status="stored", backend="fake", memory_id="mem-1")


class _FailingMemoryProvider:
    backend_name = "fake-failure"
    capabilities = {"read": False, "write": True}

    def add(self, *, record, scope=None):  # noqa: ANN001, ARG002
        raise RuntimeError("provider write failed for token=secret-value path=/tmp/private")


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return factory()


def test_record_lifecycle_memory_event_skips_when_provider_disabled() -> None:
    session = _session()
    try:
        outcome = record_lifecycle_memory_event(
            session,
            lifecycle_event="task.authoring.create_draft",
            aggregate_type="skill_draft",
            aggregate_id="1",
            actor_ref="principal:1",
            payload={"qualified_name": "lvxiaoer/demo", "token": "secret"},
            provider=NoopMemoryProvider(reason="memory backend disabled"),
            memory_write_enabled=True,
        )
        session.commit()

        assert outcome.status == "skipped"
        assert isinstance(outcome.audit_event_ref, str)
        assert outcome.audit_event_ref.startswith("audit_event:")

        event = session.scalar(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "memory_writeback")
            .where(AuditEvent.aggregate_id == outcome.dedupe_key)
        )
        assert event is not None
        assert event.event_type == "memory.writeback.skipped"
        payload = json.loads(event.payload_json)
        assert payload["status"] == "skipped"
        assert "token" not in json.dumps(payload, ensure_ascii=False)
    finally:
        session.close()


def test_record_lifecycle_memory_event_stores_and_dedupes() -> None:
    session = _session()
    try:
        provider = _FakeMemoryProvider()
        first = record_lifecycle_memory_event(
            session,
            lifecycle_event="review.approved",
            aggregate_type="review_case",
            aggregate_id="12",
            actor_ref="principal:1",
            payload={
                "qualified_name": "lvxiaoer/release-infinitas-skill",
                "audience_type": "public",
            },
            provider=provider,
            memory_write_enabled=True,
        )
        session.commit()

        assert first.status == "stored"
        assert first.memory_id == "mem-1"
        assert first.audit_event_ref.startswith("audit_event:")
        assert len(provider.calls) == 1

        second = record_lifecycle_memory_event(
            session,
            lifecycle_event="review.approved",
            aggregate_type="review_case",
            aggregate_id="12",
            actor_ref="principal:1",
            payload={
                "qualified_name": "lvxiaoer/release-infinitas-skill",
                "audience_type": "public",
            },
            provider=provider,
            memory_write_enabled=True,
        )
        session.commit()

        assert second.status == "deduped"
        assert second.audit_event_ref is None
        assert len(provider.calls) == 1

        events = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "memory_writeback")
            .where(AuditEvent.aggregate_id == first.dedupe_key)
        ).all()
        assert len(events) == 1
        assert events[0].event_type == "memory.writeback.stored"
    finally:
        session.close()


def test_record_lifecycle_memory_event_disabled_is_audited() -> None:
    session = _session()
    try:
        outcome = record_lifecycle_memory_event(
            session,
            lifecycle_event="task.review.approve",
            aggregate_type="review_case",
            aggregate_id="88",
            actor_ref="principal:1",
            payload={"qualified_name": "lvxiaoer/release-infinitas-skill"},
            provider=_FakeMemoryProvider(),
            memory_write_enabled=False,
        )
        session.commit()

        assert outcome.status == "disabled"
        assert outcome.audit_event_ref is not None

        event = session.scalar(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "memory_writeback")
            .where(AuditEvent.aggregate_id == outcome.dedupe_key)
        )
        assert event is not None
        assert event.event_type == "memory.writeback.disabled"
    finally:
        session.close()


def test_record_lifecycle_memory_event_failure_is_audited_without_raising() -> None:
    session = _session()
    try:
        outcome = record_lifecycle_memory_event(
            session,
            lifecycle_event="review.rejected",
            aggregate_type="review_case",
            aggregate_id="34",
            actor_ref="principal:7",
            payload={
                "qualified_name": "lvxiaoer/release-infinitas-skill",
                "grant_token": "grant-secret",
            },
            provider=_FailingMemoryProvider(),
            memory_write_enabled=True,
        )
        session.commit()

        assert outcome.status == "failed"
        assert outcome.audit_event_ref.startswith("audit_event:")

        event = session.scalar(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "memory_writeback")
            .where(AuditEvent.aggregate_id == outcome.dedupe_key)
        )
        assert event is not None
        assert event.event_type == "memory.writeback.failed"
        payload = json.loads(event.payload_json)
        assert payload["status"] == "failed"
        serialized = json.dumps(payload, ensure_ascii=False)
        assert "secret-value" not in serialized
        assert "/tmp/private" not in serialized
        assert "grant-secret" not in serialized
    finally:
        session.close()


def test_record_lifecycle_memory_event_failure_does_not_block_later_retry() -> None:
    session = _session()
    try:
        failed = record_lifecycle_memory_event(
            session,
            lifecycle_event="review.rejected",
            aggregate_type="review_case",
            aggregate_id="55",
            actor_ref="principal:7",
            payload={"qualified_name": "lvxiaoer/release-infinitas-skill"},
            provider=_FailingMemoryProvider(),
            memory_write_enabled=True,
        )
        session.commit()
        assert failed.status == "failed"

        provider = _FakeMemoryProvider()
        retried = record_lifecycle_memory_event(
            session,
            lifecycle_event="review.rejected",
            aggregate_type="review_case",
            aggregate_id="55",
            actor_ref="principal:7",
            payload={"qualified_name": "lvxiaoer/release-infinitas-skill"},
            provider=provider,
            memory_write_enabled=True,
        )
        session.commit()

        assert retried.status == "stored"
        assert len(provider.calls) == 1
    finally:
        session.close()
