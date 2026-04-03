from __future__ import annotations

from collections.abc import Iterable


def _normalize(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def scope_ref(prefix: str, value: str | None) -> str | None:
    normalized_prefix = _normalize(prefix)
    normalized_value = _normalize(value)
    if normalized_prefix is None or normalized_value is None:
        return None
    return f"{normalized_prefix.lower()}:{normalized_value}"


def task_scope_ref(task: str | None) -> str | None:
    normalized = _normalize(task)
    if normalized is None:
        return None
    first_token = normalized.split()[0].lower()
    return scope_ref("task", first_token)


def dedupe_scope_refs(values: Iterable[str | None]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        normalized = _normalize(value)
        if normalized is None or normalized in deduped:
            continue
        deduped.append(normalized)
    return deduped


__all__ = ["dedupe_scope_refs", "scope_ref", "task_scope_ref"]

