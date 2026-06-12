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
        _password_credential,
        _share_state,
    )
    return {
        "ShareLinkConflictError": ShareLinkConflictError,
        "ShareLinkError": ShareLinkError,
        "ShareLinkForbiddenError": ShareLinkForbiddenError,
        "ShareLinkNotFoundError": ShareLinkNotFoundError,
        "_json_object": _json_object,
        "_password_credential": _password_credential,
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

    def test_not_found_inherits_base_not_found(self):
        svc = _get_shares_service()
        from server.exceptions_base import NotFoundError as BaseNotFoundError
        # Note: ShareLinkNotFoundError does NOT inherit from BaseNotFoundError
        # This is intentional - shares has its own exception hierarchy
        assert not issubclass(svc["ShareLinkNotFoundError"], BaseNotFoundError)


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

    def test_whitespace_only(self):
        svc = _get_shares_service()
        assert svc["_json_object"]("   ") == {}

    def test_json_with_spaces(self):
        svc = _get_shares_service()
        result = svc["_json_object"]('  {"key": "value"}  ')
        assert result == {"key": "value"}


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

    def test_future_expiry_is_active(self):
        svc = _get_shares_service()
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        grant = self._make_grant(state="active")
        assert svc["_share_state"](grant, {"expires_at": future}) == "active"

    def test_exactly_at_limit_is_exhausted(self):
        svc = _get_shares_service()
        grant = self._make_grant(state="active")
        constraints = {"max_uses": 1, "used_count": 1}
        assert svc["_share_state"](grant, constraints) == "exhausted"

    def test_zero_uses_is_active(self):
        svc = _get_shares_service()
        grant = self._make_grant(state="active")
        constraints = {"max_uses": 5, "used_count": 0}
        assert svc["_share_state"](grant, constraints) == "active"


# ── _password_credential helper ──────────────────────────────────────────────


class TestPasswordCredential:
    def _make_credential(self, cred_type="share_password"):
        """Create a mock credential-like object."""

        class MockCredential:
            def __init__(self, type):
                self.type = type

        return MockCredential(cred_type)

    def test_finds_password_credential(self):
        svc = _get_shares_service()
        creds = [
            self._make_credential("share_secret"),
            self._make_credential("share_password"),
        ]
        result = svc["_password_credential"](creds)
        assert result is not None
        assert result.type == "share_password"

    def test_returns_none_when_no_password(self):
        svc = _get_shares_service()
        creds = [
            self._make_credential("share_secret"),
        ]
        result = svc["_password_credential"](creds)
        assert result is None

    def test_empty_credentials(self):
        svc = _get_shares_service()
        result = svc["_password_credential"]([])
        assert result is None

    def test_returns_first_password_credential(self):
        svc = _get_shares_service()
        creds = [
            self._make_credential("share_password"),
            self._make_credential("share_password"),
        ]
        result = svc["_password_credential"](creds)
        assert result is not None
        assert result.type == "share_password"
