"""Shared datetime formatting helpers.

Consolidates the ``_iso()`` / ``_utc_now_iso()`` pattern duplicated
across schema and service modules.
"""
from __future__ import annotations

from datetime import datetime, timezone


def iso_format(value: datetime | None) -> str | None:
    """Format *value* as ISO-8601 with ``Z`` suffix for UTC.

    Returns ``None`` when *value* is ``None``.
    """
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with ``Z`` suffix."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
