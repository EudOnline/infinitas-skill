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
    assert payload["curation_summary"]["input_count"] == 0


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


def test_load_recommendation_memory_context_curates_duplicates_and_low_signal_records():
    class FakeMemoryProvider:
        backend_name = "fake"
        capabilities = {"read": True, "write": True}

        def search(self, *, query, limit, scope=None, memory_types=None):  # noqa: ARG002
            return {
                "backend": self.backend_name,
                "records": [
                    {
                        "memory": "Neptune workflows succeed after review approval.",
                        "memory_type": "experience",
                        "score": 0.82,
                        "metadata": {"confidence": 0.9, "ttl_seconds": 60 * 60 * 24 * 60},
                    },
                    {
                        "memory": "neptune workflows succeed after review approval",
                        "memory_type": "experience",
                        "score": 0.31,
                        "metadata": {"confidence": 0.25, "ttl_seconds": 60 * 60 * 24 * 3},
                    },
                    {
                        "memory": "Temporary note for neptune.",
                        "memory_type": "task_context",
                        "score": 0.1,
                        "metadata": {"confidence": 0.1, "ttl_seconds": 60 * 60 * 6},
                    },
                ],
            }

    payload = load_recommendation_memory_context(
        task="Need codex helper for neptune workflows",
        target_agent="codex",
        memory_provider=FakeMemoryProvider(),
        memory_scope={"user_ref": "maintainer"},
        memory_context_enabled=True,
        memory_top_k=5,
    )

    assert payload["status"] == "matched"
    assert len(payload["records"]) == 1
    assert payload["curation_summary"]["suppressed_duplicates"] == 1
    assert payload["curation_summary"]["suppressed_low_signal"] == 1
