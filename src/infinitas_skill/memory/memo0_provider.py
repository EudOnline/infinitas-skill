from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .config import MemoryConfig
from .contracts import MemoryRecord, MemorySearchResult, MemoryWriteResult


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _iter_candidate_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return [item for item in payload["results"] if isinstance(item, dict)]
        if isinstance(payload.get("memories"), list):
            return [item for item in payload["memories"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def normalize_scope_filters(
    scope: Mapping[str, Any] | None,
    memory_types: Sequence[str] | None,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    source = dict(scope or {})

    for key in ("user_id", "agent_id", "run_id"):
        value = _string_or_none(source.get(key))
        if value is not None:
            normalized[key] = value

    metadata: dict[str, str] = {}
    for key in ("user_ref", "principal_ref", "skill_ref", "task_ref", "namespace"):
        value = _string_or_none(source.get(key))
        if value is not None:
            metadata[key] = value

    memory_type_values = [
        item.strip()
        for item in (memory_types or [])
        if isinstance(item, str) and item.strip()
    ]
    if memory_type_values:
        metadata["memory_types"] = ",".join(memory_type_values)

    if metadata:
        normalized["metadata"] = metadata

    return normalized


class Memo0MemoryProvider:
    backend_name = "memo0"
    capabilities = {"read": True, "write": True}

    def __init__(
        self,
        *,
        client: Any,
        namespace: str,
    ) -> None:
        self._client = client
        self._namespace = namespace

    @classmethod
    def from_config(
        cls,
        *,
        config: MemoryConfig,
        importer: Callable[[], Any] | None = None,
    ) -> "Memo0MemoryProvider":
        module = (importer or _default_importer)()
        client = _build_client(
            module,
            base_url=config.mem0_base_url,
            api_key_env=config.mem0_api_key_env,
        )
        return cls(client=client, namespace=config.namespace)

    def search(
        self,
        *,
        query: str,
        limit: int,
        scope: Mapping[str, Any] | None = None,
        memory_types: list[str] | None = None,
    ) -> MemorySearchResult:
        filters = normalize_scope_filters(scope, memory_types)
        payload = _search_memories(
            self._client,
            query=query,
            limit=limit,
            namespace=self._namespace,
            filters=filters,
        )

        records: list[MemoryRecord] = []
        for item in _iter_candidate_records(payload):
            memory = _string_or_none(item.get("memory")) or _string_or_none(item.get("text"))
            if memory is None:
                continue
            metadata = _as_mapping(item.get("metadata"))
            records.append(
                MemoryRecord(
                    memory=memory,
                    memory_type=(
                        _string_or_none(item.get("memory_type"))
                        or _string_or_none(item.get("type"))
                        or _string_or_none(metadata.get("memory_type"))
                        or "generic"
                    ),
                    score=(
                        float(item["score"])
                        if isinstance(item.get("score"), (int, float))
                        else None
                    ),
                    source=_string_or_none(item.get("id")),
                    metadata=metadata,
                )
            )
        return MemorySearchResult(records=records, backend=self.backend_name)

    def add(
        self,
        *,
        record: MemoryRecord,
        scope: Mapping[str, Any] | None = None,
    ) -> MemoryWriteResult:
        filters = normalize_scope_filters(scope, [record.memory_type])
        metadata = dict(record.metadata or {})
        metadata.setdefault("memory_type", record.memory_type)
        for key, value in _as_mapping(filters.get("metadata")).items():
            if isinstance(value, str) and value:
                metadata.setdefault(key, value)
        payload = {
            "memory": record.memory,
            "metadata": metadata,
            "namespace": self._namespace,
            "filters": filters or None,
        }
        result = _add_memory(self._client, payload)
        memory_id = None
        if isinstance(result, dict):
            memory_id = _string_or_none(result.get("id")) or _string_or_none(
                result.get("memory_id")
            )
        return MemoryWriteResult(
            status="stored",
            backend=self.backend_name,
            memory_id=memory_id,
        )


def _default_importer():
    import mem0  # type: ignore

    return mem0


def _build_client(module: Any, *, base_url: str | None, api_key_env: str) -> Any:
    api_key = os.environ.get(api_key_env)
    kwargs: dict[str, str] = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url

    if hasattr(module, "MemoryClient"):
        try:
            return module.MemoryClient(**kwargs)
        except TypeError:
            return module.MemoryClient()
    if hasattr(module, "Memory"):
        try:
            return module.Memory(**kwargs)
        except TypeError:
            return module.Memory()
    raise ImportError("mem0 module does not expose MemoryClient or Memory")


def _search_memories(
    client: Any,
    *,
    query: str,
    limit: int,
    namespace: str,
    filters: Mapping[str, Any],
) -> Any:
    params = {
        "query": query,
        "limit": limit,
        "filters": dict(filters or {}),
        "namespace": namespace,
    }
    if hasattr(client, "search"):
        return client.search(**params)
    if hasattr(client, "search_memories"):
        return client.search_memories(**params)
    return []


def _add_memory(client: Any, payload: Mapping[str, Any]) -> Any:
    if hasattr(client, "add"):
        return client.add(**payload)
    if hasattr(client, "add_memory"):
        return client.add_memory(**payload)
    raise RuntimeError("memo0 client does not support add operation")
