"""Shared result and error types for hosted publication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class HostedPublishError(RuntimeError):
    """Raised when a hosted publication cannot be completed safely."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class PublishResult:
    payload: dict[str, Any]
