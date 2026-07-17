from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone


def unique_strings(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def normalize_string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return unique_strings(item.strip() for item in values if isinstance(item, str) and item.strip())


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
