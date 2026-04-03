from __future__ import annotations

import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from infinitas_skill.server.memory_retrieval_audit import record_memory_retrieval_audit
from server.models import AuditEvent, Base


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return factory()


def test_record_memory_retrieval_audit_persists_recommendation_summary() -> None:
    session = _session()
    try:
        event = record_memory_retrieval_audit(
            session,
            actor_ref="system:discovery:test",
            entry={
                "operation": "recommend",
                "task": "Need codex helper",
                "target_agent": "codex",
                "memory": {
                    "used": True,
                    "backend": "memo0",
                    "matched_count": 2,
                    "retrieved_count": 3,
                    "status": "matched",
                },
                "results": {
                    "count": 3,
                    "top_qualified_name": "team/beta-preferred",
                    "top_memory_boost": 35,
                },
            },
        )
        session.commit()

        stored = session.scalar(
            select(AuditEvent)
            .where(AuditEvent.aggregate_type == "memory_retrieval")
            .where(AuditEvent.id == event.id)
        )
        assert stored is not None
        assert stored.event_type == "memory.retrieval.recommend"
        payload = json.loads(stored.payload_json)
        assert payload["operation"] == "recommend"
        assert payload["memory"]["backend"] == "memo0"
        assert payload["results"]["top_qualified_name"] == "team/beta-preferred"
    finally:
        session.close()
