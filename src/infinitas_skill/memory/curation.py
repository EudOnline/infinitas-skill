from __future__ import annotations

import re
from dataclasses import dataclass

from .context import effective_memory_score
from .contracts import MemoryRecord
from .policy import DAY_SECONDS

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
LOW_SIGNAL_SCORE_THRESHOLD = 0.45
LOW_SIGNAL_TTL_SECONDS = DAY_SECONDS * 3


@dataclass(frozen=True)
class CuratedMemoryRecords:
    records: list[MemoryRecord]
    summary: dict[str, int]


def memory_record_fingerprint(record: MemoryRecord) -> str:
    normalized = _NORMALIZE_RE.sub(" ", str(record.memory or "").lower()).strip()
    normalized = " ".join(part for part in normalized.split() if part)
    return f"{record.memory_type}:{normalized}"


def _trim_text(value: str, *, max_chars: int) -> str:
    if max_chars <= 3:
        return "..."
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def _ttl_seconds(record: MemoryRecord) -> int | None:
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    ttl = metadata.get("ttl_seconds")
    return ttl if isinstance(ttl, int) and ttl > 0 else None


def _is_low_signal_record(record: MemoryRecord) -> bool:
    ttl_seconds = _ttl_seconds(record)
    if ttl_seconds is None or ttl_seconds > LOW_SIGNAL_TTL_SECONDS:
        return False
    return effective_memory_score(record) < LOW_SIGNAL_SCORE_THRESHOLD


def curate_memory_records(
    records: list[MemoryRecord],
    *,
    max_items: int = 3,
    max_chars: int = 180,
) -> CuratedMemoryRecords:
    strongest_by_fingerprint: dict[str, MemoryRecord] = {}
    suppressed_duplicates = 0

    for record in records:
        fingerprint = memory_record_fingerprint(record)
        current = strongest_by_fingerprint.get(fingerprint)
        if current is None:
            strongest_by_fingerprint[fingerprint] = record
            continue
        if effective_memory_score(record) > effective_memory_score(current):
            strongest_by_fingerprint[fingerprint] = record
        suppressed_duplicates += 1

    unique = []
    suppressed_low_signal = 0
    for record in strongest_by_fingerprint.values():
        if _is_low_signal_record(record):
            suppressed_low_signal += 1
            continue
        unique.append(record)
    unique.sort(
        key=lambda item: (
            -effective_memory_score(item),
            item.memory_type,
            item.memory,
        )
    )
    limited = unique[: max_items if max_items > 0 else 0]
    trimmed = [
        MemoryRecord(
            memory=_trim_text(item.memory, max_chars=max_chars),
            memory_type=item.memory_type,
            score=item.score,
            source=item.source,
            metadata=dict(item.metadata),
        )
        for item in limited
    ]
    return CuratedMemoryRecords(
        records=trimmed,
        summary={
            "input_count": len(records),
            "kept_count": len(trimmed),
            "suppressed_duplicates": suppressed_duplicates,
            "suppressed_low_signal": suppressed_low_signal,
        },
    )


__all__ = [
    "CuratedMemoryRecords",
    "LOW_SIGNAL_SCORE_THRESHOLD",
    "LOW_SIGNAL_TTL_SECONDS",
    "curate_memory_records",
    "memory_record_fingerprint",
]
