"""Cache management for discovery projections.

Provides periodic cleanup and maintenance for the in-memory projection cache.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from server.modules.discovery.projections import cleanup_expired_cache_entries

log = logging.getLogger(__name__)


# Cache cleanup configuration
_CACHE_CLEANUP_INTERVAL_SECONDS = 600  # Run cleanup every 10 minutes
_CACHE_TTL_SECONDS = 300  # 5 minutes TTL


def get_next_cleanup_time(last_cleanup: datetime | None) -> datetime:
    """Calculate the next scheduled cleanup time.

    Args:
        last_cleanup: Last time cleanup was run (None if never run)

    Returns:
        Next cleanup datetime in UTC
    """
    if last_cleanup is None:
        return datetime.now(timezone.utc) + timedelta(seconds=_CACHE_CLEANUP_INTERVAL_SECONDS)
    return last_cleanup + timedelta(seconds=_CACHE_CLEANUP_INTERVAL_SECONDS)


def should_run_cleanup(last_cleanup: datetime | None) -> bool:
    """Check if cleanup should run based on last cleanup time.

    Args:
        last_cleanup: Last time cleanup was run

    Returns:
        True if cleanup should run now
    """
    if last_cleanup is None:
        return True
    return datetime.now(timezone.utc) >= get_next_cleanup_time(last_cleanup)


def run_cache_cleanup() -> dict[str, int]:
    """Run projection cache cleanup and return statistics.

    Returns:
        Dictionary with cleanup statistics (expired_entries_removed)
    """
    removed_count = cleanup_expired_cache_entries(ttl=_CACHE_TTL_SECONDS)

    result = {
        "expired_entries_removed": removed_count,
        "ttl_seconds": _CACHE_TTL_SECONDS,
    }

    if removed_count > 0:
        log.info(
            "cache cleanup completed: removed %d expired entries (TTL=%ds)",
            removed_count,
            _CACHE_TTL_SECONDS,
        )
    else:
        log.debug("cache cleanup completed: no expired entries to remove")

    return result


def get_cache_stats() -> dict[str, int]:
    """Get current cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    from server.modules.discovery.projections import (
        _cache_access_order,
        _projection_cache,
    )

    return {
        "total_entries": len(_projection_cache),
        "lru_order_length": len(_cache_access_order),
    }
