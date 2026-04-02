"""Schema version helpers for canonical skill payloads."""

from __future__ import annotations

SUPPORTED_SCHEMA_VERSION = 1


def validate_schema_version(
    payload, *, field: str = "schema_version", default_version: int = SUPPORTED_SCHEMA_VERSION
):
    if not isinstance(payload, dict):
        return default_version, [f"{field} validation requires an object payload"]
    if field not in payload:
        return default_version, []
    value = payload.get(field)
    if not isinstance(value, int):
        return default_version, [f"{field} must be an integer"]
    if value != SUPPORTED_SCHEMA_VERSION:
        return value, [
            f"unsupported {field} {value!r}; "
            f"supported version is {SUPPORTED_SCHEMA_VERSION}"
        ]
    return value, []


__all__ = ["SUPPORTED_SCHEMA_VERSION", "validate_schema_version"]
