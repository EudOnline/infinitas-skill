"""Unit tests for server.modules.review.service."""

from __future__ import annotations


def _get_review_service():
    """Lazy import to avoid circular dependency."""
    from server.modules.review.service import (
        ConflictError,
        NotFoundError,
        ReviewError,
    )

    return {
        "ConflictError": ConflictError,
        "NotFoundError": NotFoundError,
        "ReviewError": ReviewError,
    }


# ── Exception hierarchy ──────────────────────────────────────────────────────


class TestReviewExceptions:
    def test_review_error_is_exception(self):
        svc = _get_review_service()
        assert issubclass(svc["ReviewError"], Exception)

    def test_not_found_inherits_review_error(self):
        svc = _get_review_service()
        assert issubclass(svc["NotFoundError"], svc["ReviewError"])

    def test_conflict_inherits_review_error(self):
        svc = _get_review_service()
        assert issubclass(svc["ConflictError"], svc["ReviewError"])

    def test_not_found_inherits_base_not_found(self):
        svc = _get_review_service()
        from server.exceptions_base import NotFoundError as BaseNotFoundError

        assert issubclass(svc["NotFoundError"], BaseNotFoundError)

    def test_conflict_inherits_base_conflict(self):
        svc = _get_review_service()
        from server.exceptions_base import ConflictError as BaseConflictError

        assert issubclass(svc["ConflictError"], BaseConflictError)
