"""Pure normalization primitives for installed-integrity state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def default_integrity_record() -> dict[str, Any]:
    return {
        "state": "unknown",
        "last_verified_at": None,
        "checked_file_count": 0,
        "release_file_manifest_count": 0,
        "modified_count": 0,
        "missing_count": 0,
        "unexpected_count": 0,
        "modified_files": [],
        "missing_files": [],
        "unexpected_files": [],
    }


def default_integrity_capability_fields() -> dict[str, str | None]:
    return {"integrity_capability": "unknown", "integrity_reason": None}


def default_integrity_events() -> list[dict[str, str]]:
    return []


def default_integrity_freshness() -> dict[str, Any]:
    return {
        "freshness_state": "never-verified",
        "checked_age_seconds": None,
        "last_checked_at": None,
    }


def normalize_integrity_record(record: object) -> dict[str, Any]:
    normalized = default_integrity_record()
    if not isinstance(record, dict):
        return normalized
    state = record.get("state")
    if state in {"unknown", "verified", "drifted"}:
        normalized["state"] = state
    last_verified_at = record.get("last_verified_at")
    if isinstance(last_verified_at, str) and last_verified_at:
        normalized["last_verified_at"] = last_verified_at
    for key in (
        "checked_file_count",
        "release_file_manifest_count",
        "modified_count",
        "missing_count",
        "unexpected_count",
    ):
        value = record.get(key)
        if isinstance(value, int) and value >= 0:
            normalized[key] = value
    for key in ("modified_files", "missing_files", "unexpected_files"):
        value = record.get(key)
        if isinstance(value, list):
            normalized[key] = [item for item in value if isinstance(item, str) and item]
    return normalized


def normalize_integrity_capability_fields(
    capability: object = None, reason: object = None
) -> dict[str, str | None]:
    normalized = default_integrity_capability_fields()
    if capability == "supported":
        normalized["integrity_capability"] = "supported"
        return normalized
    if isinstance(reason, str) and reason:
        normalized["integrity_reason"] = reason
    return normalized


def normalize_integrity_event(event: object) -> dict[str, str] | None:
    if not isinstance(event, dict):
        return None
    normalized: dict[str, str] = {}
    for key in ("at", "event", "source"):
        value = event.get(key)
        if not isinstance(value, str) or not value:
            return None
        normalized[key] = value
    reason = event.get("reason")
    if isinstance(reason, str) and reason:
        normalized["reason"] = reason
    return normalized


def normalize_integrity_events(events: object) -> list[dict[str, str]]:
    if not isinstance(events, list):
        return default_integrity_events()
    return [event for item in events if (event := normalize_integrity_event(item)) is not None]


def normalize_timestamp_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def parse_timestamp(value: object) -> datetime | None:
    normalized = normalize_timestamp_string(value)
    if normalized is None:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
