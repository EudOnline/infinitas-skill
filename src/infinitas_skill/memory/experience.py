from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import MemoryRecord
from .policy import resolve_memory_policy

SENSITIVE_KEY_PARTS = {"token", "secret", "credential", "grant", "password", "api_key", "apikey"}
PATH_KEY_PARTS = {"path", "dir", "directory"}
SLASH_ALLOWED_KEYS = {"qualified_name", "skill_ref"}


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _is_path_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in PATH_KEY_PARTS)


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
    if trimmed.startswith(("./", "../", "~/" )):
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


def _sanitize_mapping(payload: dict[str, Any] | None) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key in sorted((payload or {}).keys()):
        value = (payload or {}).get(key)
        if not isinstance(key, str) or not key.strip():
            continue
        if _is_sensitive_key(key) or _is_path_key(key):
            continue
        if not _is_safe_scalar(value):
            continue
        normalized = str(value).strip()
        if not normalized or _looks_like_absolute_path(normalized):
            continue
        if key not in SLASH_ALLOWED_KEYS and _looks_like_relative_path(normalized):
            continue
        sanitized[key] = normalized
    return sanitized


def _render_content(event_type: str, payload: dict[str, Any] | None, *, max_chars: int) -> str:
    normalized_event = str(event_type or "").strip()
    rendered_parts = [normalized_event] if normalized_event else []
    sanitized_payload = _sanitize_mapping(payload)
    for key in sorted(sanitized_payload):
        rendered_parts.append(f"{key}={sanitized_payload[key]}")
    joined = "; ".join(rendered_parts) if rendered_parts else "event=unknown"
    if len(joined) <= max_chars:
        return joined
    if max_chars <= 3:
        return "..."
    return joined[: max_chars - 3].rstrip() + "..."


@dataclass(frozen=True)
class ExperienceMemoryRecord:
    memory_type: str
    content: str
    source_refs: list[str] = field(default_factory=list)
    confidence: float = 0.7
    ttl_seconds: int = 60 * 60 * 24 * 30
    provider_metadata: dict[str, str] = field(default_factory=dict)

    def to_memory_record(self) -> MemoryRecord:
        return MemoryRecord(
            memory=self.content,
            memory_type=self.memory_type,
            metadata={
                "source_refs": list(self.source_refs),
                "confidence": self.confidence,
                "ttl_seconds": self.ttl_seconds,
                "provider_metadata": dict(self.provider_metadata),
            },
        )


def build_experience_memory(
    *,
    event_type: str,
    aggregate_ref: str,
    payload: dict[str, Any] | None = None,
    confidence: float | None = None,
    ttl_seconds: int | None = None,
    provider_metadata: dict[str, Any] | None = None,
    max_content_chars: int = 220,
) -> ExperienceMemoryRecord:
    source_ref = str(aggregate_ref or "").strip()
    policy = resolve_memory_policy(event_type)
    normalized_ttl = (
        ttl_seconds
        if isinstance(ttl_seconds, int) and ttl_seconds > 0
        else policy.ttl_seconds
    )
    return ExperienceMemoryRecord(
        memory_type=policy.memory_type,
        content=_render_content(
            event_type,
            payload,
            max_chars=max_content_chars if max_content_chars > 0 else 220,
        ),
        source_refs=[source_ref] if source_ref else [],
        confidence=confidence if isinstance(confidence, (int, float)) else policy.confidence,
        ttl_seconds=normalized_ttl,
        provider_metadata=_sanitize_mapping(provider_metadata),
    )


__all__ = ["ExperienceMemoryRecord", "build_experience_memory"]
