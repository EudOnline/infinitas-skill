from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

DEFAULT_MEMORY_BACKEND = "disabled"
DEFAULT_MEMORY_NAMESPACE = "infinitas"
DEFAULT_MEMORY_TOP_K = 5
DEFAULT_MEM0_API_KEY_ENV = "MEM0_API_KEY"


def normalize_memory_backend(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return DEFAULT_MEMORY_BACKEND
    return normalized


def _env_flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_int_or_default(value: str | None, default: int) -> int:
    try:
        parsed = int(str(value or "").strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


@dataclass(frozen=True)
class MemoryConfig:
    backend: str
    context_enabled: bool
    write_enabled: bool
    namespace: str
    top_k: int
    mem0_base_url: str | None
    mem0_api_key_env: str


def load_memory_config(env: Mapping[str, str] | None = None) -> MemoryConfig:
    source = env if env is not None else os.environ
    namespace = str(source.get("INFINITAS_MEMORY_NAMESPACE") or "").strip()
    return MemoryConfig(
        backend=normalize_memory_backend(source.get("INFINITAS_MEMORY_BACKEND")),
        context_enabled=_env_flag(source.get("INFINITAS_MEMORY_CONTEXT_ENABLED")),
        write_enabled=_env_flag(source.get("INFINITAS_MEMORY_WRITE_ENABLED")),
        namespace=namespace or DEFAULT_MEMORY_NAMESPACE,
        top_k=_positive_int_or_default(source.get("INFINITAS_MEMORY_TOP_K"), DEFAULT_MEMORY_TOP_K),
        mem0_base_url=str(source.get("INFINITAS_MEMORY_MEM0_BASE_URL") or "").strip() or None,
        mem0_api_key_env=(
            str(source.get("INFINITAS_MEMORY_MEM0_API_KEY_ENV") or "").strip()
            or DEFAULT_MEM0_API_KEY_ENV
        ),
    )
