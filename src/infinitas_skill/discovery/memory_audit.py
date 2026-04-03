from __future__ import annotations

from typing import Any, Callable

MemoryAuditRecorder = Callable[[dict[str, Any]], None]


def _memory_summary(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {
            "used": False,
            "backend": "",
            "matched_count": 0,
            "retrieved_count": 0,
            "status": "unknown",
        }
    curation = summary.get("curation_summary")
    payload: dict[str, Any] = {
        "used": bool(summary.get("used")),
        "backend": str(summary.get("backend") or ""),
        "matched_count": int(summary.get("matched_count") or 0),
        "retrieved_count": int(summary.get("retrieved_count") or 0),
        "status": str(summary.get("status") or "unknown"),
    }
    if isinstance(curation, dict):
        payload["curation_summary"] = {
            "input_count": int(curation.get("input_count") or 0),
            "kept_count": int(curation.get("kept_count") or 0),
            "suppressed_duplicates": int(curation.get("suppressed_duplicates") or 0),
            "suppressed_low_signal": int(curation.get("suppressed_low_signal") or 0),
        }
    return payload


def _effect_from_status(status: str) -> str | None:
    normalized = str(status or "").strip().lower()
    if normalized in {"disabled", "error", "unavailable", "unknown"}:
        return normalized
    return None


def _recommendation_effect(memory: dict[str, Any], results: dict[str, Any]) -> str:
    status = str(memory.get("status") or "")
    direct = _effect_from_status(status)
    if direct is not None:
        return direct
    if bool(memory.get("used")) and int(results.get("top_memory_boost") or 0) > 0:
        return "helpful"
    if int(memory.get("matched_count") or 0) > 0:
        return "restrained"
    return "no_signal"


def _inspect_effect(memory: dict[str, Any], results: dict[str, Any]) -> str:
    status = str(memory.get("status") or "")
    direct = _effect_from_status(status)
    if direct is not None:
        return direct
    if bool(memory.get("used")) and int(results.get("count") or 0) > 0:
        return "helpful"
    if int(memory.get("matched_count") or 0) > 0:
        return "restrained"
    return "no_signal"


def emit_recommendation_memory_audit(
    *,
    audit_recorder: MemoryAuditRecorder | None,
    task: str,
    target_agent: str | None,
    payload: dict[str, Any],
) -> None:
    if audit_recorder is None:
        return
    results = payload.get("results") or []
    top = results[0] if isinstance(results, list) and results else {}
    entry = {
        "operation": "recommend",
        "task": str(task or ""),
        "target_agent": str(target_agent or ""),
        "memory": _memory_summary((payload.get("explanation") or {}).get("memory_summary")),
        "results": {
            "count": len(results) if isinstance(results, list) else 0,
            "top_qualified_name": str((top or {}).get("qualified_name") or ""),
            "top_memory_boost": int(
                ((top or {}).get("memory_signals") or {}).get("applied_boost") or 0
            ),
            "top_matched_memory_count": int(
                ((top or {}).get("memory_signals") or {}).get("matched_memory_count") or 0
            ),
        },
    }
    entry["effect"] = _recommendation_effect(entry["memory"], entry["results"])
    try:
        audit_recorder(entry)
    except Exception:
        return


def emit_inspect_memory_audit(
    *,
    audit_recorder: MemoryAuditRecorder | None,
    skill_ref: str,
    version: str | None,
    target_agent: str | None,
    payload: dict[str, Any],
) -> None:
    if audit_recorder is None:
        return
    memory_hints = payload.get("memory_hints") or {}
    entry = {
        "operation": "inspect",
        "skill_ref": str(skill_ref or ""),
        "version": str(version or payload.get("version") or ""),
        "target_agent": str(target_agent or ""),
        "memory": _memory_summary(memory_hints),
        "results": {
            "count": len(memory_hints.get("items") or []) if isinstance(memory_hints, dict) else 0,
            "trust_state": str(payload.get("trust_state") or ""),
        },
    }
    entry["effect"] = _inspect_effect(entry["memory"], entry["results"])
    try:
        audit_recorder(entry)
    except Exception:
        return


__all__ = [
    "MemoryAuditRecorder",
    "emit_inspect_memory_audit",
    "emit_recommendation_memory_audit",
]
