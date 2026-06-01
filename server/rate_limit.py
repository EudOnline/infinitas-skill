"""Rate limiting backends for login and sensitive endpoints.

Supports in-memory (default) and database-backed rate limiting.
The database backend uses a lightweight table so it works across
multiple worker processes without adding Redis as a dependency.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from server.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RateLimitEntry(Base):
    """Shared rate-limit bucket storage for multi-process deployments."""

    __tablename__ = "rate_limit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
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

    def __init__(self) -> None:
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, *, max_attempts: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        attempts = [t for t in self._attempts.get(key, []) if t > cutoff]
        return len(attempts) < max_attempts

    def record(self, key: str) -> None:
        now = time.monotonic()
        self._attempts[key].append(now)

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)

    def reset_all(self) -> None:
        self._attempts.clear()


class DBRateLimiter(RateLimiter):
    """Database-backed rate limiter for multi-process deployments.

    .. note::
       ``record`` and ``reset`` call ``db.commit()`` internally because
       rate-limit state must be visible to other processes immediately.
       Callers should treat rate-limit bookkeeping as an independent
       side-effect transaction.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def check(self, key: str, *, max_attempts: int, window_seconds: int) -> bool:
        from datetime import timedelta

        cutoff = _utcnow() - timedelta(seconds=window_seconds)

        # Prune old entries.
        self._db.execute(
            delete(RateLimitEntry).where(RateLimitEntry.window_start < cutoff)
        )

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
        window_start = _utcnow().replace(second=0, microsecond=0)

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
        self._db.commit()

    def reset(self, key: str) -> None:
        self._db.execute(delete(RateLimitEntry).where(RateLimitEntry.key == key))
        self._db.commit()

    def reset_all(self) -> None:
        self._db.execute(delete(RateLimitEntry))
        self._db.commit()


# Global singleton for memory-backed rate limiting.
_memory_limiter = MemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Return the default memory rate limiter.

    Callers that need distributed rate limiting should instantiate
    :class:`DBRateLimiter` directly with a SQLAlchemy session.
    """
    return _memory_limiter
