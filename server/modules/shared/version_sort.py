"""Shared version sorting and deduplication utilities.

Provides common functions for sorting semantic versions and deduplicating
discovery projections by release ID.  Used by both the discovery and registry
modules which previously maintained independent (and subtly divergent) copies.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

_VERSION_PARTS_RE = re.compile(r"(\d+|[A-Za-z]+)")


def version_sort_key(version: str) -> tuple:
    """Return a sort key for a version string.

    Splits the version into numeric and alphabetic parts so that
    ``"1.2.3"`` sorts before ``"1.10.0"`` and ``"1.0.0-beta"`` before
    ``"1.0.0-rc"``.
    """
    parts = []
    for item in _VERSION_PARTS_RE.findall(str(version or "")):
        if item.isdigit():
            parts.append((0, int(item)))
        else:
            parts.append((1, item.lower()))
    return tuple(parts)


def audience_rank(audience_type: str) -> int:
    """Return a numeric rank for an audience type (higher = more restricted).

    Used for sorting and deduplication: ``"private"`` (4) > ``"grant"`` (3) >
    ``"authenticated"`` (2) > ``"public"`` (1).
    """
    return {
        "private": 4,
        "grant": 3,
        "authenticated": 2,
        "public": 1,
    }.get(str(audience_type or ""), 0)


def ready_sort_key(value: datetime | None) -> tuple[int, str]:
    """Sort key that puts entries with a ``ready_at`` timestamp first."""
    if value is None:
        return (0, "")
    return (1, value.isoformat())


def dedupe_entries(
    entries: list,
    *,
    keep: Literal["highest", "lowest"] = "highest",
) -> list:
    """Deduplicate entries by ``release_id``, keeping one per release.

    Args:
        entries: List of entries with ``release_id`` and ``audience_type`` attrs.
        keep: ``"highest"`` keeps the entry with the most restricted audience
            (registry default); ``"lowest"`` keeps the most permissive
            (discovery default).

    Returns:
        Deduplicated list sorted by qualified name, version, audience rank,
        and ready_at timestamp.
    """
    by_release: dict[int, Any] = {}
    for entry in entries:
        current = by_release.get(entry.release_id)
        if current is None:
            by_release[entry.release_id] = entry
            continue
        current_rank = audience_rank(current.audience_type)
        entry_rank = audience_rank(entry.audience_type)
        if keep == "highest" and entry_rank > current_rank:
            by_release[entry.release_id] = entry
        elif keep == "lowest" and entry_rank < current_rank:
            by_release[entry.release_id] = entry
    return sorted(
        by_release.values(),
        key=lambda entry: (
            entry.qualified_name,
            version_sort_key(entry.version),
            audience_rank(entry.audience_type),
            ready_sort_key(getattr(entry, "ready_at", None)),
        ),
        reverse=False,
    )
