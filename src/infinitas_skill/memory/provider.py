from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .config import MemoryConfig, load_memory_config, normalize_memory_backend
from .contracts import (
    MemoryDeleteResult,
    MemoryProvider,
    MemoryRecord,
    MemorySearchResult,
    MemoryWriteResult,
)


class NoopMemoryProvider:
    backend_name = "noop"
    capabilities = {"read": False, "write": False, "delete": False}

    def __init__(self, *, reason: str = "disabled") -> None:
        self.reason = reason

    def search(
        self,
        *,
        query: str,
        limit: int,
        scope: Mapping[str, Any] | None = None,
        memory_types: list[str] | None = None,
    ) -> MemorySearchResult:
        return MemorySearchResult(records=[], backend=self.backend_name)

    def add(
        self,
        *,
        record: MemoryRecord,
        scope: Mapping[str, Any] | None = None,
    ) -> MemoryWriteResult:
        return MemoryWriteResult(
            status="skipped",
            backend=self.backend_name,
            error=self.reason,
        )

    def delete(
        self,
        *,
        memory_id: str,  # noqa: ARG002
    ) -> MemoryDeleteResult:
        return MemoryDeleteResult(
            status="skipped",
            backend=self.backend_name,
            error=self.reason,
        )


def build_memory_provider(
    *,
    config: MemoryConfig | None = None,
    backend: str | None = None,
    importer: Callable[[], Any] | None = None,
) -> MemoryProvider:
    resolved_config = config or load_memory_config()
    backend_name = normalize_memory_backend(backend or resolved_config.backend)

    if backend_name == "disabled":
        return NoopMemoryProvider(reason="memory backend disabled")
    if backend_name != "memo0":
        return NoopMemoryProvider(reason=f"unsupported memory backend: {backend_name}")

    from .memo0_provider import Memo0MemoryProvider

    try:
        return Memo0MemoryProvider.from_config(
            config=resolved_config,
            importer=importer,
        )
    except ImportError:
        return NoopMemoryProvider(reason="memo0 sdk unavailable")
    except Exception as exc:
        return NoopMemoryProvider(reason=f"memo0 provider initialization failed: {exc}")
