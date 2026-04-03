from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class MemoryRecord:
    memory: str
    memory_type: str = "generic"
    score: float | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySearchResult:
    records: list[MemoryRecord] = field(default_factory=list)
    backend: str = "noop"


@dataclass(frozen=True)
class MemoryWriteResult:
    status: str
    backend: str
    memory_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class MemoryDeleteResult:
    status: str
    backend: str
    memory_id: str | None = None
    error: str | None = None


class MemoryProvider(Protocol):
    backend_name: str
    capabilities: Mapping[str, bool]

    def search(
        self,
        *,
        query: str,
        limit: int,
        scope: Mapping[str, Any] | None = None,
        memory_types: list[str] | None = None,
    ) -> MemorySearchResult: ...

    def add(
        self,
        *,
        record: MemoryRecord,
        scope: Mapping[str, Any] | None = None,
    ) -> MemoryWriteResult: ...

    def delete(
        self,
        *,
        memory_id: str,
    ) -> MemoryDeleteResult: ...
