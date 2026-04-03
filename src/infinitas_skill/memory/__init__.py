from __future__ import annotations

from .config import MemoryConfig, load_memory_config, normalize_memory_backend
from .context import (
    DEFAULT_INSPECT_MEMORY_TYPES,
    DEFAULT_RECOMMENDATION_MEMORY_TYPES,
    MemoryContextQuery,
    build_inspect_memory_query,
    build_recommendation_memory_query,
    render_memory_snippets,
    trim_memory_records,
)
from .contracts import MemoryProvider, MemoryRecord, MemorySearchResult, MemoryWriteResult
from .experience import ExperienceMemoryRecord, build_experience_memory
from .provider import NoopMemoryProvider, build_memory_provider
from .scopes import dedupe_scope_refs, scope_ref, task_scope_ref

__all__ = [
    "DEFAULT_INSPECT_MEMORY_TYPES",
    "DEFAULT_RECOMMENDATION_MEMORY_TYPES",
    "MemoryConfig",
    "MemoryContextQuery",
    "ExperienceMemoryRecord",
    "MemoryProvider",
    "MemoryRecord",
    "MemorySearchResult",
    "MemoryWriteResult",
    "NoopMemoryProvider",
    "build_memory_provider",
    "build_experience_memory",
    "build_inspect_memory_query",
    "build_recommendation_memory_query",
    "dedupe_scope_refs",
    "load_memory_config",
    "normalize_memory_backend",
    "render_memory_snippets",
    "scope_ref",
    "task_scope_ref",
    "trim_memory_records",
]
