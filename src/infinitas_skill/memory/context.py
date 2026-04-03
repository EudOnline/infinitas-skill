from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import MemoryRecord
from .policy import DAY_SECONDS
from .scopes import dedupe_scope_refs, scope_ref, task_scope_ref

DEFAULT_RECOMMENDATION_MEMORY_TYPES = ["user_preference", "task_context", "experience"]
DEFAULT_INSPECT_MEMORY_TYPES = ["task_context", "experience"]
DEFAULT_MEMORY_CONFIDENCE = 0.6
MAX_MEMORY_TTL_SECONDS = DAY_SECONDS * 90
MEMORY_TYPE_QUALITY_WEIGHTS = {
    "user_preference": 0.08,
    "experience": 0.07,
    "task_context": 0.03,
}


@dataclass(frozen=True)
class MemoryContextQuery:
    query: str
    scope_refs: list[str] = field(default_factory=list)
    provider_scope: dict[str, str] = field(default_factory=dict)
    memory_types: list[str] = field(default_factory=list)
    max_results: int = 5


def _clamp_float(value: object, *, default: float) -> float:
    if isinstance(value, (int, float)):
        numeric = float(value)
    else:
        return default
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return numeric


def _ttl_factor(value: object) -> float:
    if not isinstance(value, int) or value <= 0:
        return 0.0
    return min(value, MAX_MEMORY_TTL_SECONDS) / MAX_MEMORY_TTL_SECONDS


def effective_memory_score(record: MemoryRecord) -> float:
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    provider_score = _clamp_float(record.score, default=0.5)
    confidence = _clamp_float(
        metadata.get("confidence"),
        default=DEFAULT_MEMORY_CONFIDENCE,
    )
    ttl_factor = _ttl_factor(metadata.get("ttl_seconds"))
    type_weight = MEMORY_TYPE_QUALITY_WEIGHTS.get(record.memory_type, 0.02)
    return (provider_score * 0.65) + (confidence * 0.25) + (ttl_factor * 0.10) + type_weight


def _normalize_memory_types(
    explicit_memory_types: list[str] | None,
    *,
    defaults: list[str],
) -> list[str]:
    if not explicit_memory_types:
        return list(defaults)
    normalized = []
    for item in explicit_memory_types:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized or list(defaults)


def _build_scope_refs(
    *,
    task: str | None,
    user_ref: str | None,
    principal_ref: str | None,
    target_agent: str | None,
    skill_ref: str | None,
    extra_scope_refs: list[str] | None,
) -> list[str]:
    return dedupe_scope_refs(
        [
            scope_ref("user", user_ref),
            scope_ref("principal", principal_ref),
            scope_ref("agent", target_agent),
            scope_ref("skill", skill_ref),
            task_scope_ref(task),
            *(extra_scope_refs or []),
        ]
    )


def _build_provider_scope(
    *,
    task: str | None,
    user_ref: str | None,
    principal_ref: str | None,
    target_agent: str | None,
    skill_ref: str | None,
) -> dict[str, str]:
    provider_scope: dict[str, str] = {}
    if isinstance(user_ref, str) and user_ref.strip():
        provider_scope["user_ref"] = user_ref.strip()
    if isinstance(principal_ref, str) and principal_ref.strip():
        provider_scope["principal_ref"] = principal_ref.strip()
    if isinstance(target_agent, str) and target_agent.strip():
        provider_scope["agent_id"] = target_agent.strip()
    if isinstance(skill_ref, str) and skill_ref.strip():
        provider_scope["skill_ref"] = skill_ref.strip()
    task_ref = task_scope_ref(task)
    if task_ref is not None:
        provider_scope["task_ref"] = task_ref.split(":", 1)[1]
    return provider_scope


def build_recommendation_memory_query(
    *,
    task: str,
    target_agent: str | None = None,
    user_ref: str | None = None,
    principal_ref: str | None = None,
    skill_ref: str | None = None,
    extra_scope_refs: list[str] | None = None,
    memory_types: list[str] | None = None,
    max_results: int = 5,
) -> MemoryContextQuery:
    return MemoryContextQuery(
        query=str(task or "").strip(),
        scope_refs=_build_scope_refs(
            task=task,
            user_ref=user_ref,
            principal_ref=principal_ref,
            target_agent=target_agent,
            skill_ref=skill_ref,
            extra_scope_refs=extra_scope_refs,
        ),
        provider_scope=_build_provider_scope(
            task=task,
            user_ref=user_ref,
            principal_ref=principal_ref,
            target_agent=target_agent,
            skill_ref=skill_ref,
        ),
        memory_types=_normalize_memory_types(
            memory_types,
            defaults=DEFAULT_RECOMMENDATION_MEMORY_TYPES,
        ),
        max_results=max_results if isinstance(max_results, int) and max_results > 0 else 5,
    )


def build_inspect_memory_query(
    *,
    skill_ref: str,
    target_agent: str | None = None,
    user_ref: str | None = None,
    principal_ref: str | None = None,
    task: str = "inspect",
    extra_scope_refs: list[str] | None = None,
    memory_types: list[str] | None = None,
    max_results: int = 5,
) -> MemoryContextQuery:
    return MemoryContextQuery(
        query=str(skill_ref or "").strip(),
        scope_refs=_build_scope_refs(
            task=task,
            user_ref=user_ref,
            principal_ref=principal_ref,
            target_agent=target_agent,
            skill_ref=skill_ref,
            extra_scope_refs=extra_scope_refs,
        ),
        provider_scope=_build_provider_scope(
            task=task,
            user_ref=user_ref,
            principal_ref=principal_ref,
            target_agent=target_agent,
            skill_ref=skill_ref,
        ),
        memory_types=_normalize_memory_types(memory_types, defaults=DEFAULT_INSPECT_MEMORY_TYPES),
        max_results=max_results if isinstance(max_results, int) and max_results > 0 else 5,
    )


def _trim_text(value: str, *, max_chars: int) -> str:
    if max_chars <= 3:
        return "..."
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def trim_memory_records(
    records: list[MemoryRecord],
    *,
    max_items: int = 3,
    max_chars: int = 180,
) -> list[MemoryRecord]:
    seen: set[tuple[str, str]] = set()
    unique: list[MemoryRecord] = []
    for record in records:
        key = (record.memory_type, record.memory)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    unique.sort(
        key=lambda item: (
            -effective_memory_score(item),
            item.memory_type,
            item.memory,
        )
    )
    limited = unique[: max_items if max_items > 0 else 0]
    return [
        MemoryRecord(
            memory=_trim_text(item.memory, max_chars=max_chars),
            memory_type=item.memory_type,
            score=item.score,
            source=item.source,
            metadata=dict(item.metadata),
        )
        for item in limited
    ]


def render_memory_snippets(
    records: list[MemoryRecord],
    *,
    max_items: int = 3,
    max_chars: int = 180,
) -> list[str]:
    snippets = []
    for record in trim_memory_records(records, max_items=max_items, max_chars=max_chars):
        snippets.append(f"{record.memory_type}: {record.memory}")
    return snippets


__all__ = [
    "DEFAULT_INSPECT_MEMORY_TYPES",
    "DEFAULT_MEMORY_CONFIDENCE",
    "DEFAULT_RECOMMENDATION_MEMORY_TYPES",
    "MAX_MEMORY_TTL_SECONDS",
    "MEMORY_TYPE_QUALITY_WEIGHTS",
    "MemoryContextQuery",
    "build_inspect_memory_query",
    "build_recommendation_memory_query",
    "effective_memory_score",
    "render_memory_snippets",
    "trim_memory_records",
]
