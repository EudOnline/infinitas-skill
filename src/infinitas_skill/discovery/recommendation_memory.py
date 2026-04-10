from __future__ import annotations

from typing import Any

from infinitas_skill.memory import build_recommendation_memory_query, curate_memory_records
from infinitas_skill.memory.contracts import MemoryRecord, MemorySearchResult


def coerce_memory_search_result(
    payload: Any,
    *,
    fallback_backend: str,
) -> MemorySearchResult:
    if isinstance(payload, MemorySearchResult):
        return payload

    records = []
    backend = fallback_backend

    if isinstance(payload, dict):
        if isinstance(payload.get("backend"), str) and payload.get("backend", "").strip():
            backend = payload.get("backend", "").strip()
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
                            if isinstance(item.get("source"), str)
                            and item.get("source", "").strip()
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


def load_recommendation_memory_context(
    *,
    task: str,
    target_agent: str | None,
    memory_provider: Any | None,
    memory_scope: dict | None,
    memory_context_enabled: bool,
    memory_top_k: int,
) -> dict[str, Any]:
    backend = getattr(memory_provider, "backend_name", "disabled")
    memory_scope = memory_scope if isinstance(memory_scope, dict) else {}
    if not memory_context_enabled or memory_provider is None:
        return {
            "records": [],
            "backend": backend if memory_provider else "disabled",
            "status": "disabled",
            "error": None,
            "curation_summary": {
                "input_count": 0,
                "kept_count": 0,
                "suppressed_duplicates": 0,
                "suppressed_low_signal": 0,
            },
        }

    capabilities = getattr(memory_provider, "capabilities", {})
    if not isinstance(capabilities, dict) or not capabilities.get("read"):
        return {
            "records": [],
            "backend": backend,
            "status": "unavailable",
            "error": "memory provider does not support read",
            "curation_summary": {
                "input_count": 0,
                "kept_count": 0,
                "suppressed_duplicates": 0,
                "suppressed_low_signal": 0,
            },
        }

    context_query = build_recommendation_memory_query(
        task=task,
        target_agent=target_agent,
        user_ref=memory_scope.get("user_ref"),
        principal_ref=memory_scope.get("principal_ref"),
        skill_ref=memory_scope.get("skill_ref"),
        runtime_platform=memory_scope.get("runtime_platform"),
        workspace_root=memory_scope.get("workspace_root"),
        session_ref=memory_scope.get("session_ref"),
        task_capabilities=memory_scope.get("task_capabilities"),
        runtime_capabilities=memory_scope.get("runtime_capabilities"),
    )
    provider_scope = dict(context_query.provider_scope)
    for key in ["user_id", "agent_id", "run_id", "namespace"]:
        value = memory_scope.get(key)
        if isinstance(value, str) and value.strip():
            provider_scope[key] = value.strip()
    limit = memory_top_k if isinstance(memory_top_k, int) and memory_top_k > 0 else 3
    try:
        payload = memory_provider.search(
            query=context_query.query,
            limit=limit,
            scope=provider_scope,
            memory_types=context_query.memory_types,
        )
    except Exception as exc:
        return {
            "records": [],
            "backend": backend,
            "status": "error",
            "error": f"memory retrieval failed: {exc}",
            "curation_summary": {
                "input_count": 0,
                "kept_count": 0,
                "suppressed_duplicates": 0,
                "suppressed_low_signal": 0,
            },
        }

    normalized = coerce_memory_search_result(payload, fallback_backend=backend)
    curated = curate_memory_records(normalized.records, max_items=limit, max_chars=220)
    return {
        "records": curated.records,
        "backend": normalized.backend,
        "status": "matched" if curated.records else "no-match",
        "error": None,
        "curation_summary": curated.summary,
    }


__all__ = [
    "coerce_memory_search_result",
    "load_recommendation_memory_context",
]
