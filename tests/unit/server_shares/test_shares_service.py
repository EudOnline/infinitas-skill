"""Unit tests for server.modules.shares.service."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest


# Import after other modules to avoid circular import
def _get_shares_service():
    from server.modules.shares.service import (
        ShareLinkConflictError,
        ShareLinkError,
        ShareLinkForbiddenError,
        ShareLinkNotFoundError,
        _json_object,
        _share_state,
    )
    return {
        "ShareLinkConflictError": ShareLinkConflictError,
        "ShareLinkError": ShareLinkError,
        "ShareLinkForbiddenError": ShareLinkForbiddenError,
        "ShareLinkNotFoundError": ShareLinkNotFoundError,
        "_json_object": _json_object,
        "_share_state": _share_state,
    }


# ── Exception hierarchy ──────────────────────────────────────────────────────


class TestShareLinkExceptions:
    def test_share_link_error_is_exception(self):
        svc = _get_shares_service()
        assert issubclass(svc["ShareLinkError"], Exception)

    def test_not_found_inherits_share_link_error(self):
        svc = _get_shares_service()
        assert issubclass(svc["ShareLinkNotFoundError"], svc["ShareLinkError"])

    def test_forbidden_inherits_share_link_error(self):
        svc = _get_shares_service()
        assert issubclass(svc["ShareLinkForbiddenError"], svc["ShareLinkError"])

    def test_conflict_inherits_share_link_error(self):
        svc = _get_shares_service()
        assert issubclass(svc["ShareLinkConflictError"], svc["ShareLinkError"])


# ── _json_object helper ──────────────────────────────────────────────────────


class TestJsonObject:
    def test_valid_json(self):
        svc = _get_shares_service()
        assert svc["_json_object"]('{"key": "value"}') == {"key": "value"}

    def test_empty_string(self):
        svc = _get_shares_service()
        assert svc["_json_object"]("") == {}

    def test_none(self):
        svc = _get_shares_service()
        assert svc["_json_object"](None) == {}

    def test_invalid_json(self):
        svc = _get_shares_service()
        assert svc["_json_object"]("not json") == {}

    def test_non_dict_json(self):
        svc = _get_shares_service()
        assert svc["_json_object"]("[1, 2, 3]") == {}

    def test_nested_dict(self):
        svc = _get_shares_service()
        result = svc["_json_object"]('{"a": {"b": 1}}')
        assert result == {"a": {"b": 1}}


# ── _share_state helper ──────────────────────────────────────────────────────


class TestShareState:
    def _make_grant(self, state="active"):
        """Create a mock grant-like object."""

        class MockGrant:
            def __init__(self, state):
                self.state = state

        return MockGrant(state)

    def test_revoked_grant(self):
        svc = _get_shares_service()
        grant = self._make_grant(state="revoked")
        assert svc["_share_state"](grant, {}) == "revoked"

    def test_active_grant_no_expiry(self):
        svc = _get_shares_service()
        grant = self._make_grant(state="active")
        assert svc["_share_state"](grant, {}) == "active"

    def test_expired_grant(self):
        svc = _get_shares_service()
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        grant = self._make_grant(state="active")
        assert svc["_share_state"](grant, {"expires_at": past}) == "expired"

    def test_exhausted_grant(self):
        svc = _get_shares_service()
        grant = self._make_grant(state="active")
        constraints = {"max_uses": 5, "used_count": 5}
        assert svc["_share_state"](grant, constraints) == "exhausted"

    def test_active_grant_with_uses_remaining(self):
        svc = _get_shares_service()
        grant = self._make_grant(state="active")
        constraints = {"max_uses": 5, "used_count": 3}
        assert svc["_share_state"](grant, constraints) == "active"

    def test_active_grant_with_usage_limit(self):
        svc = _get_shares_service()
        grant = self._make_grant(state="active")
        constraints = {"usage_limit": 10, "usage_count": 7}
        assert svc["_share_state"](grant, constraints) == "active"
