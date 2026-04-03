from __future__ import annotations

from infinitas_skill.memory.contracts import MemoryRecord
from infinitas_skill.memory.curation import curate_memory_records


def test_curate_memory_records_keeps_strongest_duplicate() -> None:
    curated = curate_memory_records(
        [
            MemoryRecord(
                memory="Neptune release handoffs usually succeed after review approval.",
                memory_type="experience",
                score=0.91,
                metadata={"confidence": 0.9, "ttl_seconds": 60 * 60 * 24 * 90},
            ),
            MemoryRecord(
                memory="neptune release handoffs usually succeed after review approval",
                memory_type="experience",
                score=0.41,
                metadata={"confidence": 0.2, "ttl_seconds": 60 * 60 * 24 * 7},
            ),
        ],
        max_items=3,
        max_chars=180,
    )

    assert len(curated.records) == 1
    assert curated.summary["input_count"] == 2
    assert curated.summary["suppressed_duplicates"] == 1
    assert curated.records[0].score == 0.91


def test_curate_memory_records_suppresses_low_signal_short_lived_items() -> None:
    curated = curate_memory_records(
        [
            MemoryRecord(
                memory="Temporary note for neptune rollout.",
                memory_type="task_context",
                score=0.18,
                metadata={"confidence": 0.15, "ttl_seconds": 60 * 60 * 12},
            ),
            MemoryRecord(
                memory="Neptune rollouts remain safer after release readiness checks pass.",
                memory_type="experience",
                score=0.77,
                metadata={"confidence": 0.88, "ttl_seconds": 60 * 60 * 24 * 60},
            ),
        ],
        max_items=3,
        max_chars=180,
    )

    assert [record.memory_type for record in curated.records] == ["experience"]
    assert curated.summary["suppressed_low_signal"] == 1
    assert curated.summary["kept_count"] == 1
