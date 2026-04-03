from __future__ import annotations

from infinitas_skill.discovery.inspect_memory import load_inspect_memory_hints
from infinitas_skill.memory.contracts import MemoryRecord, MemorySearchResult


class FailingMemoryProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        raise RuntimeError("provider offline")


class FakeMemoryProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def __init__(self, records: list[MemoryRecord]):
        self._records = records

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        return MemorySearchResult(backend=self.backend_name, records=self._records)


def test_load_inspect_memory_hints_returns_advisory_error_state():
    payload = load_inspect_memory_hints(
        skill_ref="lvxiaoer/consume-infinitas-skill",
        target_agent="openclaw",
        memory_provider=FailingMemoryProvider(),
        memory_scope={"user_ref": "maintainer"},
        memory_context_enabled=True,
        memory_top_k=3,
    )

    assert payload["used"] is False
    assert payload["backend"] == "fake"
    assert payload["status"] == "error"
    assert "provider offline" in payload["error"]


def test_load_inspect_memory_hints_orders_items_by_effective_quality():
    payload = load_inspect_memory_hints(
        skill_ref="lvxiaoer/consume-infinitas-skill",
        target_agent="openclaw",
        memory_provider=FakeMemoryProvider(
            [
                MemoryRecord(
                    memory="Short-lived install note for OpenClaw.",
                    memory_type="task_context",
                    score=0.88,
                    metadata={"confidence": 0.25, "ttl_seconds": 60 * 60 * 24 * 2},
                ),
                MemoryRecord(
                    memory=(
                        "OpenClaw installs usually succeed when the release "
                        "is already materialized."
                    ),
                    memory_type="experience",
                    score=0.78,
                    metadata={"confidence": 0.92, "ttl_seconds": 60 * 60 * 24 * 90},
                ),
            ]
        ),
        memory_scope={"user_ref": "maintainer"},
        memory_context_enabled=True,
        memory_top_k=3,
    )

    assert payload["status"] == "matched"
    assert payload["items"][0]["memory_type"] == "experience"
