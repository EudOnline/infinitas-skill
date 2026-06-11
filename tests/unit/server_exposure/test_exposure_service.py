"""Unit tests for server.modules.exposure.service."""
from __future__ import annotations

import pytest


def _get_exposure_service():
    """Lazy import to avoid circular dependency."""
    from server.modules.exposure.service import (
        ConflictError,
        ExposureError,
        ForbiddenError,
        NotFoundError,
    )
    return {
        "ConflictError": ConflictError,
        "ExposureError": ExposureError,
        "ForbiddenError": ForbiddenError,
        "NotFoundError": NotFoundError,
    }


# ── Exception hierarchy ──────────────────────────────────────────────────────


class TestExposureExceptions:
    def test_exposure_error_is_exception(self):
        svc = _get_exposure_service()
        assert issubclass(svc["ExposureError"], Exception)

    def test_not_found_inherits_exposure_error(self):
        svc = _get_exposure_service()
        assert issubclass(svc["NotFoundError"], svc["ExposureError"])

    def test_conflict_inherits_exposure_error(self):
        svc = _get_exposure_service()
        assert issubclass(svc["ConflictError"], svc["ExposureError"])

    def test_forbidden_inherits_exposure_error(self):
        svc = _get_exposure_service()
        assert issubclass(svc["ForbiddenError"], svc["ExposureError"])

    def test_not_found_inherits_base_not_found(self):
        svc = _get_exposure_service()
        from server.exceptions_base import NotFoundError as BaseNotFoundError
        assert issubclass(svc["NotFoundError"], BaseNotFoundError)

    def test_conflict_inherits_base_conflict(self):
        svc = _get_exposure_service()
        from server.exceptions_base import ConflictError as BaseConflictError
        assert issubclass(svc["ConflictError"], BaseConflictError)

    def test_forbidden_inherits_base_forbidden(self):
        svc = _get_exposure_service()
        from server.exceptions_base import ForbiddenError as BaseForbiddenError
        assert issubclass(svc["ForbiddenError"], BaseForbiddenError)
