from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from infinitas_skill.server.repo_checks import require_sqlite_db
from server.models import AuditEvent


def _server_engine_kwargs(database_url: str) -> dict[str, Any]:
    if database_url.startswith("sqlite:///"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def _aggregate_id(entry: dict[str, Any]) -> str:
    operation = str(entry.get("operation") or "unknown")
    if operation == "recommend":
        raw = "|".join(
            [
                operation,
                str(entry.get("task") or ""),
                str(entry.get("target_agent") or ""),
                str((entry.get("results") or {}).get("top_qualified_name") or ""),
            ]
        )
    else:
        raw = "|".join(
            [
                operation,
                str(entry.get("skill_ref") or ""),
                str(entry.get("version") or ""),
                str(entry.get("target_agent") or ""),
            ]
        )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
    return f"mr:{digest}"


def record_memory_retrieval_audit(
    db: Session,
    *,
    actor_ref: str,
    entry: dict[str, Any],
):
    operation = str(entry.get("operation") or "unknown").strip().lower() or "unknown"
    event = AuditEvent(
        aggregate_type="memory_retrieval",
        aggregate_id=_aggregate_id(entry),
        event_type=f"memory.retrieval.{operation}",
        actor_ref=str(actor_ref or "").strip(),
        payload_json=json.dumps(entry, ensure_ascii=False, sort_keys=True),
    )
    db.add(event)
    db.flush()
    return event


def build_memory_retrieval_audit_recorder(
    *,
    database_url: str,
    actor_ref: str,
) -> Callable[[dict[str, Any]], None]:
    require_sqlite_db(database_url)
    engine = create_engine(database_url, future=True, **_server_engine_kwargs(database_url))

    def recorder(entry: dict[str, Any]) -> None:
        with Session(engine) as session:
            record_memory_retrieval_audit(session, actor_ref=actor_ref, entry=entry)
            session.commit()

    return recorder


__all__ = [
    "build_memory_retrieval_audit_recorder",
    "record_memory_retrieval_audit",
]
