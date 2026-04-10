"""Plugin capability helpers for OpenClaw runtime metadata."""

from __future__ import annotations

SUPPORTED_PLUGIN_CAPABILITY_KEYS = ("channels", "tools", "web_search")


def _normalize_string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        token = item.strip()
        if not token:
            continue
        normalized.append(token)
    return normalized if normalized else None


def normalize_plugin_capabilities(payload: dict | None) -> dict[str, list[str]]:
    """Normalize plugin capability payloads to supported list-based fields."""

    if not isinstance(payload, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for key in SUPPORTED_PLUGIN_CAPABILITY_KEYS:
        values = _normalize_string_list(payload.get(key))
        if values is not None:
            normalized[key] = values
    return normalized


__all__ = ["SUPPORTED_PLUGIN_CAPABILITY_KEYS", "normalize_plugin_capabilities"]
