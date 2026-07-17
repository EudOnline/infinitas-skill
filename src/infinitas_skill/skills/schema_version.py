"""Schema version helpers for canonical skill payloads."""

from __future__ import annotations

SUPPORTED_SCHEMA_VERSION = 1


def validate_schema_version(
    payload: object, *, field: str = "schema_version"
) -> tuple[int | None, list[str]]:
    if not isinstance(payload, dict):
        return None, [f"{field} validation requires an object payload"]
    if field not in payload:
        return None, [f"missing required {field}"]
    value = payload.get(field)
    if not isinstance(value, int):
        return None, [f"{field} must be an integer"]
    if value != SUPPORTED_SCHEMA_VERSION:
        return value, [
            f"unsupported {field} {value!r}; supported version is {SUPPORTED_SCHEMA_VERSION}"
        ]
    return value, []


__all__ = ["SUPPORTED_SCHEMA_VERSION", "validate_schema_version"]
