"""Rate limiting backends for login and sensitive endpoints.

Supports in-memory (default) and database-backed rate limiting.
The database backend uses a lightweight table so it works across
multiple worker processes without adding Redis as a dependency.
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime

from fastapi import Request
from sqlalchemy import DateTime, Integer, String, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from server.model_base import Base, utcnow


def resolve_client_ip(request: Request) -> str:
    """Extract the real client IP from a request, respecting trusted reverse proxies.

    Only reads ``X-Forwarded-For`` and ``X-Real-IP`` headers when the
    direct connection comes from an IP listed in ``trusted_proxies``.
    Otherwise falls back to the direct ``request.client.host`` to prevent
    header spoofing.

    The trusted proxy list is loaded from the
    ``INFINITAS_SERVER_TRUSTED_PROXIES`` environment variable (JSON array).
    When empty (the default), only direct connection IPs are used.
    """
    from server.settings import get_settings

    client_host = request.client.host if request.client else "unknown"
    trusted_proxies = get_settings().trusted_proxies
    if trusted_proxies and client_host in trusted_proxies:
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
        real_ip = (request.headers.get("x-real-ip") or "").strip()
        if real_ip:
            return real_ip
    return client_host


def resolve_rate_limit_key(request: Request, user_id: int | None = None) -> str:
    """Generate a rate limit key that combines multiple identifiers.

    For authenticated users, uses the user_id to prevent IP spoofing.
    For unauthenticated requests, uses the trusted client IP. User-Agent is
    deliberately excluded because it is attacker-controlled and would let a
    caller rotate buckets without changing network identity.

    Args:
        request: The FastAPI request object
        user_id: Optional authenticated user ID

    Returns:
        A string key suitable for rate limiting
    """
    if user_id is not None:
        # For authenticated users, use user_id as the primary key
        return f"user:{user_id}"

    # Hash the trusted client IP so raw addresses are not stored or logged.
    client_ip = resolve_client_ip(request)
    return f"anon:{hashlib.sha256(client_ip.encode()).hexdigest()[:32]}"


class RateLimitEntry(Base):
    """Shared rate-limit bucket storage for multi-process deployments."""

    __tablename__ = "rate_limit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class RateLimiter(ABC):
    """Abstract rate limiter interface."""

    @abstractmethod
    def check(self, key: str, *, max_attempts: int, window_seconds: int) -> bool:
        """Return ``True`` if the key is within the rate limit."""

    @abstractmethod
    def record(self, key: str) -> None:
        """Record an attempt for the given key."""

    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset attempts for the given key."""

    @abstractmethod
    def reset_all(self) -> None:
        """Reset attempts for every key."""


class MemoryRateLimiter(RateLimiter):
    """In-memory rate limiter using sliding window (default)."""

    # Prune stale keys once this many total entries accumulate across all keys.
    _PRUNE_THRESHOLD = 10_000

    def __init__(self) -> None:
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._total_entries = 0

    def _prune_all_stale(self) -> None:
        """Remove expired entries across all keys to bound memory usage."""
        now = time.monotonic()
        surviving: dict[str, list[float]] = defaultdict(list)
        count = 0
        for key, timestamps in self._attempts.items():
            fresh = [t for t in timestamps if t > now - 3600]  # 1h hard floor
            if fresh:
                surviving[key] = fresh
                count += len(fresh)
        self._attempts = surviving
        self._total_entries = count

    def _maybe_prune(self) -> None:
        if self._total_entries > self._PRUNE_THRESHOLD:
            self._prune_all_stale()

    def check(self, key: str, *, max_attempts: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        attempts = [t for t in self._attempts.get(key, []) if t > cutoff]
        return len(attempts) < max_attempts

    def record(self, key: str) -> None:
        now = time.monotonic()
        self._attempts[key].append(now)
        self._total_entries += 1
        self._maybe_prune()

    def reset(self, key: str) -> None:
        removed = self._attempts.pop(key, None)
        if removed:
            self._total_entries -= len(removed)

    def reset_all(self) -> None:
        self._attempts.clear()
        self._total_entries = 0


class DBRateLimiter(RateLimiter):
    """Database-backed rate limiter participating in its caller's transaction."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def check(self, key: str, *, max_attempts: int, window_seconds: int) -> bool:
        from datetime import timedelta

        cutoff = utcnow() - timedelta(seconds=window_seconds)

        # Prune old entries.
        self._db.execute(delete(RateLimitEntry).where(RateLimitEntry.window_start < cutoff))

        # Count attempts in current window.
        total = (
            self._db.scalar(
                select(func.sum(RateLimitEntry.attempt_count))
                .where(RateLimitEntry.key == key)
                .where(RateLimitEntry.window_start >= cutoff)
            )
            or 0
        )
        return int(total) < max_attempts

    def record(self, key: str) -> None:
        window_start = utcnow().replace(second=0, microsecond=0)

        entry = self._db.scalar(
            select(RateLimitEntry)
            .where(RateLimitEntry.key == key)
            .where(RateLimitEntry.window_start == window_start)
        )
        if entry is not None:
            entry.attempt_count += 1
        else:
            entry = RateLimitEntry(
                key=key,
                window_start=window_start,
                attempt_count=1,
            )
            self._db.add(entry)
        self._db.flush()

    def reset(self, key: str) -> None:
        self._db.execute(delete(RateLimitEntry).where(RateLimitEntry.key == key))
        self._db.flush()

    def reset_all(self) -> None:
        self._db.execute(delete(RateLimitEntry))
        self._db.flush()


# Global singleton for memory-backed rate limiting.
_memory_limiter = MemoryRateLimiter()


def get_rate_limiter(db: Session | None = None) -> RateLimiter:
    """Return a shared database limiter when a request session is available.

    The memory limiter remains for isolated utilities without a database
    session. HTTP routes pass their request session so limits are shared across
    worker processes.
    """
    if db is not None:
        return DBRateLimiter(db)
    return _memory_limiter
