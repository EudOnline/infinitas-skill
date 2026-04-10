from __future__ import annotations

from typing import Any

from infinitas_skill.memory import build_inspect_memory_query, curate_memory_records
from infinitas_skill.memory.contracts import MemoryRecord, MemorySearchResult

INSPECT_MEMORY_TYPES = {"experience", "task_context"}


def coerce_memory_search_result(
    payload: Any,
    *,
    fallback_backend: str,
) -> MemorySearchResult:
    if isinstance(payload, MemorySearchResult):
        return payload
    if not isinstance(payload, dict):
        return MemorySearchResult(records=[], backend=fallback_backend)

    backend = fallback_backend
    backend_value = payload.get("backend")
    if isinstance(backend_value, str) and backend_value.strip():
        backend = backend_value.strip()

    records = []
    raw_records = payload.get("records")
    if isinstance(raw_records, list):
        for item in raw_records:
            if isinstance(item, MemoryRecord):
                records.append(item)
                continue
            if not isinstance(item, dict):
                continue
            memory = item.get("memory")
            if not isinstance(memory, str) or not memory.strip():
                continue
            records.append(
                MemoryRecord(
                    memory=memory.strip(),
                    memory_type=(
                        item.get("memory_type")
                        if isinstance(item.get("memory_type"), str)
                        and item.get("memory_type", "").strip()
                        else "generic"
                    ),
                    score=(
                        float(item.get("score"))
                        if isinstance(item.get("score"), (int, float))
                        else None
                    ),
                    source=(
                        item.get("source")
                        if isinstance(item.get("source"), str) and item.get("source", "").strip()
                        else None
                    ),
                    metadata=(
                        item.get("metadata")
                        if isinstance(item.get("metadata"), dict)
                        else {}
                    ),
                )
            )
    return MemorySearchResult(records=records, backend=backend)


def memory_hint_item(record: MemoryRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "memory_type": record.memory_type,
        "memory": record.memory,
    }
    if isinstance(record.score, (int, float)):
        payload["score"] = float(record.score)
    return payload


def load_inspect_memory_hints(
    *,
    skill_ref: str,
    target_agent: str | None,
    memory_provider: Any | None,
    memory_scope: dict | None,
    memory_context_enabled: bool,
    memory_top_k: int,
) -> dict[str, Any]:
    backend = getattr(memory_provider, "backend_name", "disabled")
    base = {
        "used": False,
        "backend": backend if memory_provider is not None else "disabled",
        "matched_count": 0,
        "items": [],
        "advisory_only": True,
        "curation_summary": {
            "input_count": 0,
            "kept_count": 0,
            "suppressed_duplicates": 0,
            "suppressed_low_signal": 0,
        },
    }
    if memory_provider is None or not memory_context_enabled:
        base["status"] = "disabled"
        return base

    capabilities = getattr(memory_provider, "capabilities", {})
    if not isinstance(capabilities, dict) or not capabilities.get("read"):
        base["status"] = "unavailable"
        return base

    memory_scope = memory_scope if isinstance(memory_scope, dict) else {}
    query = build_inspect_memory_query(
        skill_ref=skill_ref,
        target_agent=target_agent,
        user_ref=memory_scope.get("user_ref"),
        principal_ref=memory_scope.get("principal_ref"),
        task=memory_scope.get("task_ref") or "inspect",
        runtime_platform=memory_scope.get("runtime_platform"),
        workspace_root=memory_scope.get("workspace_root"),
        session_ref=memory_scope.get("session_ref"),
        task_capabilities=memory_scope.get("task_capabilities"),
        runtime_capabilities=memory_scope.get("runtime_capabilities"),
    )
    provider_scope = dict(query.provider_scope)
    for key in ["user_id", "agent_id", "run_id", "namespace"]:
        value = memory_scope.get(key)
        if isinstance(value, str) and value.strip():
            provider_scope[key] = value.strip()
    limit = (
        memory_top_k
        if isinstance(memory_top_k, int) and memory_top_k > 0
        else query.max_results
    )
    try:
        payload = memory_provider.search(
            query=query.query,
            limit=limit,
            scope=provider_scope,
            memory_types=query.memory_types,
        )
    except Exception as exc:
        base["status"] = "error"
        base["error"] = f"memory retrieval failed: {exc}"
        return base

    normalized = coerce_memory_search_result(payload, fallback_backend=backend)
    filtered = [
        record
        for record in normalized.records
        if isinstance(record.memory_type, str) and record.memory_type in INSPECT_MEMORY_TYPES
    ]
    curated = curate_memory_records(filtered, max_items=limit, max_chars=180)
    base["backend"] = normalized.backend
    base["matched_count"] = len(filtered)
    base["items"] = [memory_hint_item(record) for record in curated.records]
    base["curation_summary"] = curated.summary
    base["used"] = bool(base["items"])
    base["status"] = "matched" if filtered else "no-match"
    return base


__all__ = [
    "INSPECT_MEMORY_TYPES",
    "coerce_memory_search_result",
    "load_inspect_memory_hints",
    "memory_hint_item",
]
