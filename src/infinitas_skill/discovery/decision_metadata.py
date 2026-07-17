from __future__ import annotations

from typing import Any

DECISION_METADATA_LIST_FIELDS = (
    "use_when",
    "avoid_when",
    "capabilities",
    "runtime_assumptions",
)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def canonical_decision_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    metadata: dict[str, Any] = {
        field: _string_list(payload.get(field)) for field in DECISION_METADATA_LIST_FIELDS
    }

    maturity = payload.get("maturity")
    metadata["maturity"] = (
        maturity.strip() if isinstance(maturity, str) and maturity.strip() else "unknown"
    )

    quality_score = payload.get("quality_score")
    metadata["quality_score"] = quality_score if isinstance(quality_score, int) else 0

    return metadata
