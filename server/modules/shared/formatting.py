"""Shared datetime formatting helpers.

Consolidates the ``_iso()`` / ``_utc_now_iso()`` pattern duplicated
across schema and service modules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from sqlalchemy import DateTime


def humanize_identifier(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("_", " ").replace("-", " ").strip().title()


def humanize_timestamp(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return value
    stamp = parsed.strftime("%Y-%m-%d %H:%M")
    if parsed.tzinfo is not None and parsed.utcoffset() is not None:
        stamp = f"{stamp} UTC"
    return stamp


def iso_format(value: DateTime | datetime | None) -> str | None:
    """Format *value* as ISO-8601 with ``Z`` suffix for UTC.

    Returns ``None`` when *value* is ``None``.
    """
    if value is None:
        return None
    return cast(datetime, value).isoformat().replace("+00:00", "Z")


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with ``Z`` suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
