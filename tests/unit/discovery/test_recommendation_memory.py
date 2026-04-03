from __future__ import annotations

from infinitas_skill.discovery.recommendation_memory import (
    load_recommendation_memory_context,
)
from infinitas_skill.discovery.recommendation_ranking import calculate_memory_signals
from infinitas_skill.memory.contracts import MemoryRecord


class FailingMemoryProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
        raise RuntimeError("provider offline")


def test_load_recommendation_memory_context_reports_error_without_records():
    payload = load_recommendation_memory_context(
        task="Need codex helper for workflows",
        target_agent="codex",
        memory_provider=FailingMemoryProvider(),
        memory_scope={"user_ref": "maintainer"},
        memory_context_enabled=True,
        memory_top_k=3,
    )

    assert payload["records"] == []
    assert payload["backend"] == "fake"
    assert payload["status"] == "error"
    assert "provider offline" in payload["error"]


def test_calculate_memory_signals_uses_effective_memory_quality_for_boost_order():
    item = {
        "name": "beta-preferred",
        "qualified_name": "team/beta-preferred",
        "summary": "Specialized helper for neptune-harbor operations",
        "tags": ["helper", "ops"],
        "use_when": ["Need neptune-harbor operations"],
        "capabilities": ["repo-operations"],
    }
    factors = {"compatibility": True}
    records = [
        MemoryRecord(
            memory="Saturn-forge handoffs are favored for operator routing.",
            memory_type="user_preference",
            score=0.94,
            metadata={"confidence": 0.3, "ttl_seconds": 60 * 60 * 24 * 7},
        ),
        MemoryRecord(
            memory="Neptune-harbor operations are favored for operator routing.",
            memory_type="user_preference",
            score=0.74,
            metadata={"confidence": 0.95, "ttl_seconds": 60 * 60 * 24 * 90},
        ),
    ]

    payload = calculate_memory_signals(
        item,
        factors=factors,
        records=records,
    )

    assert payload["matched_memory_count"] == 1
    assert payload["applied_boost"] > 0
    assert payload["memory_types"] == ["user_preference"]
