from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from infinitas_skill.memory.experience import build_experience_memory
from infinitas_skill.memory.provider import build_memory_provider
from server.models import AuditEvent
from server.modules.audit.service import append_audit_event
from server.settings import get_settings

_SENSITIVE_KEY_PARTS = {
    "token",
    "secret",
    "credential",
    "grant",
    "password",
    "api_key",
    "apikey",
}
_PATH_KEY_PARTS = {"path", "dir", "directory"}
_SLASH_ALLOWED_KEYS = {"qualified_name", "skill_ref"}


@dataclass(frozen=True)
class MemoryWritebackOutcome:
    status: str
    backend: str
    dedupe_key: str
    audit_event_ref: str | None = None
    memory_id: str | None = None
    error: str | None = None


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _is_path_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _PATH_KEY_PARTS)


def _looks_like_absolute_path(value: str) -> bool:
    trimmed = value.strip()
    if not trimmed:
        return False
    if trimmed.startswith("/"):
        return True
    if len(trimmed) >= 3 and trimmed[1] == ":" and trimmed[2] in {"\\", "/"}:
        return True
    return False


def _looks_like_relative_path(value: str) -> bool:
    trimmed = value.strip()
    if not trimmed:
        return False
    if trimmed.startswith(("./", "../", "~/")):
        return True
    if "\\" in trimmed:
        return True
    if "/" not in trimmed:
        return False
    if ":" in trimmed.split("/", 1)[0]:
        return False
    return True


def _is_safe_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _sanitize_mapping(payload: Mapping[str, Any] | None) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key in sorted((payload or {}).keys()):
        if not isinstance(key, str) or not key.strip():
            continue
        if _is_sensitive_key(key) or _is_path_key(key):
            continue
        value = (payload or {}).get(key)
        if not _is_safe_scalar(value):
            continue
        normalized = str(value).strip()
        if not normalized or _looks_like_absolute_path(normalized):
            continue
        if key not in _SLASH_ALLOWED_KEYS and _looks_like_relative_path(normalized):
            continue
        sanitized[key] = normalized
    return sanitized


def _sanitize_error(exc: Exception) -> str:
    return f"{exc.__class__.__name__}:provider_write_failed"


def _sanitize_error_text(raw: Any) -> str | None:
    normalized = str(raw or "").strip()
    if not normalized:
        return None
    return "provider_write_failed"


def _dedupe_key(*, lifecycle_event: str, aggregate_type: str, aggregate_id: str) -> str:
    raw = f"{lifecycle_event}|{aggregate_type}|{aggregate_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
    return f"mw:{digest}"


def _normalize_lifecycle_event(value: str) -> str:
    return str(value or "").strip() or "task.unknown"


def _resolve_memory_write_enabled(memory_write_enabled: bool | None) -> bool:
    if memory_write_enabled is not None:
        return bool(memory_write_enabled)
    try:
        return bool(get_settings().memory_write_enabled)
    except Exception:
        return False


def _event_ref(event: AuditEvent | None) -> str | None:
    if event is None:
        return None
    return f"audit_event:{event.id}"


def _find_existing_writeback_event(db: Session, dedupe_key: str) -> AuditEvent | None:
    return db.scalar(
        select(AuditEvent)
        .where(AuditEvent.aggregate_type == "memory_writeback")
        .where(AuditEvent.aggregate_id == dedupe_key)
        .order_by(AuditEvent.id.desc())
    )


def _existing_event_status(event: AuditEvent | None) -> str | None:
    if event is None:
        return None
    try:
        payload = json.loads(event.payload_json or "{}")
    except Exception:
        return None
    status = payload.get("status")
    if not isinstance(status, str):
        return None
    normalized = status.strip().lower()
    return normalized or None


def _append_memory_audit_event(
    db: Session,
    *,
    dedupe_key: str,
    lifecycle_event: str,
    aggregate_ref: str,
    actor_ref: str,
    status: str,
    backend: str,
    payload: Mapping[str, Any] | None = None,
    memory_id: str | None = None,
    error: str | None = None,
) -> AuditEvent:
    event_type = f"memory.writeback.{status}".lower()
    event_payload: dict[str, Any] = {
        "status": status,
        "backend": backend,
        "lifecycle_event": lifecycle_event,
        "aggregate_ref": aggregate_ref,
        "dedupe_key": dedupe_key,
        "payload": _sanitize_mapping(payload),
    }
    if memory_id:
        event_payload["memory_id"] = str(memory_id)
    if error:
        event_payload["error"] = str(error)
    return append_audit_event(
        db,
        aggregate_type="memory_writeback",
        aggregate_id=dedupe_key,
        event_type=event_type,
        actor_ref=actor_ref,
        payload=event_payload,
    )


def record_lifecycle_memory_event(
    db: Session,
    *,
    lifecycle_event: str,
    aggregate_type: str,
    aggregate_id: str,
    actor_ref: str,
    payload: Mapping[str, Any] | None = None,
    provider: Any | None = None,
    memory_write_enabled: bool | None = None,
    scope: Mapping[str, Any] | None = None,
) -> MemoryWritebackOutcome:
    normalized_lifecycle_event = _normalize_lifecycle_event(lifecycle_event)
    normalized_aggregate_type = str(aggregate_type or "").strip() or "aggregate"
    normalized_aggregate_id = str(aggregate_id or "").strip() or "unknown"
    normalized_actor_ref = str(actor_ref or "").strip()
    dedupe_key = _dedupe_key(
        lifecycle_event=normalized_lifecycle_event,
        aggregate_type=normalized_aggregate_type,
        aggregate_id=normalized_aggregate_id,
    )
    resolved_provider = provider or build_memory_provider()
    backend_name = str(getattr(resolved_provider, "backend_name", "unknown") or "unknown")

    if not _resolve_memory_write_enabled(memory_write_enabled):
        event = _append_memory_audit_event(
            db,
            dedupe_key=dedupe_key,
            lifecycle_event=normalized_lifecycle_event,
            aggregate_ref=f"{normalized_aggregate_type}:{normalized_aggregate_id}",
            actor_ref=normalized_actor_ref,
            status="disabled",
            backend=backend_name,
            payload=payload,
        )
        return MemoryWritebackOutcome(
            status="disabled",
            backend=backend_name,
            dedupe_key=dedupe_key,
            audit_event_ref=_event_ref(event),
        )

    existing_event = _find_existing_writeback_event(db, dedupe_key)
    existing_status = _existing_event_status(existing_event)
    if existing_event is not None and existing_status not in {None, "failed"}:
        return MemoryWritebackOutcome(
            status="deduped",
            backend=backend_name,
            dedupe_key=dedupe_key,
        )

    aggregate_ref = f"{normalized_aggregate_type}:{normalized_aggregate_id}"
    sanitized_payload = _sanitize_mapping(payload)
    scope_payload = _sanitize_mapping(scope)
    if normalized_actor_ref:
        scope_payload.setdefault("actor_ref", normalized_actor_ref)

    experience = build_experience_memory(
        event_type=normalized_lifecycle_event,
        aggregate_ref=aggregate_ref,
        payload=sanitized_payload,
        provider_metadata={
            "aggregate_ref": aggregate_ref,
            "dedupe_key": dedupe_key,
            "lifecycle_event": normalized_lifecycle_event,
        },
    )
    try:
        write_result = resolved_provider.add(
            record=experience.to_memory_record(),
            scope=scope_payload,
        )
    except Exception as exc:
        sanitized_error = _sanitize_error(exc)
        event = _append_memory_audit_event(
            db,
            dedupe_key=dedupe_key,
            lifecycle_event=normalized_lifecycle_event,
            aggregate_ref=aggregate_ref,
            actor_ref=normalized_actor_ref,
            status="failed",
            backend=backend_name,
            payload=sanitized_payload,
            error=sanitized_error,
        )
        return MemoryWritebackOutcome(
            status="failed",
            backend=backend_name,
            dedupe_key=dedupe_key,
            audit_event_ref=_event_ref(event),
            error=sanitized_error,
        )

    normalized_status = (
        str(getattr(write_result, "status", "") or "unknown").strip().lower() or "unknown"
    )
    resolved_backend = (
        str(getattr(write_result, "backend", "") or backend_name).strip() or backend_name
    )
    memory_id = getattr(write_result, "memory_id", None)
    error = getattr(write_result, "error", None)
    sanitized_error = _sanitize_error_text(error)

    event = _append_memory_audit_event(
        db,
        dedupe_key=dedupe_key,
        lifecycle_event=normalized_lifecycle_event,
        aggregate_ref=aggregate_ref,
        actor_ref=normalized_actor_ref,
        status=normalized_status,
        backend=resolved_backend,
        payload=sanitized_payload,
        memory_id=str(memory_id).strip() if memory_id else None,
        error=sanitized_error,
    )
    return MemoryWritebackOutcome(
        status=normalized_status,
        backend=resolved_backend,
        dedupe_key=dedupe_key,
        audit_event_ref=_event_ref(event),
        memory_id=str(memory_id).strip() if memory_id else None,
        error=sanitized_error,
    )


def record_user_task_memory(
    db: Session,
    *,
    task_name: str,
    aggregate_type: str,
    aggregate_id: str,
    actor_ref: str,
    payload: Mapping[str, Any] | None = None,
    provider: Any | None = None,
    memory_write_enabled: bool | None = None,
    scope: Mapping[str, Any] | None = None,
) -> MemoryWritebackOutcome:
    normalized_task_name = str(task_name or "").strip().replace(" ", "_")
    lifecycle_event = normalized_task_name
    if not lifecycle_event.startswith("task."):
        lifecycle_event = f"task.{lifecycle_event or 'unknown'}"
    return record_lifecycle_memory_event(
        db,
        lifecycle_event=lifecycle_event,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        actor_ref=actor_ref,
        payload=payload,
        provider=provider,
        memory_write_enabled=memory_write_enabled,
        scope=scope,
    )


def record_experience_memory(
    db: Session,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    actor_ref: str,
    payload: Mapping[str, Any] | None = None,
    provider: Any | None = None,
    memory_write_enabled: bool | None = None,
    scope: Mapping[str, Any] | None = None,
) -> MemoryWritebackOutcome:
    normalized_event_type = str(event_type or "").strip() or "experience.unknown"
    return record_lifecycle_memory_event(
        db,
        lifecycle_event=normalized_event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        actor_ref=actor_ref,
        payload=payload,
        provider=provider,
        memory_write_enabled=memory_write_enabled,
        scope=scope,
    )


def record_lifecycle_memory_event_best_effort(
    db: Session,
    *,
    lifecycle_event: str,
    aggregate_type: str,
    aggregate_id: str,
    actor_ref: str,
    payload: Mapping[str, Any] | None = None,
    provider: Any | None = None,
    memory_write_enabled: bool | None = None,
    scope: Mapping[str, Any] | None = None,
) -> MemoryWritebackOutcome | None:
    try:
        outcome = record_lifecycle_memory_event(
            db,
            lifecycle_event=lifecycle_event,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            actor_ref=actor_ref,
            payload=payload,
            provider=provider,
            memory_write_enabled=memory_write_enabled,
            scope=scope,
        )
        db.commit()
        return outcome
    except Exception:
        db.rollback()
        return None
