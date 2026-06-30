from __future__ import annotations

from types import SimpleNamespace

from server.ui.auth_state import (
    hydrate_auth_state,
    is_owner,
    principal_label,
)


class TestHydrateAuthState:
    def test_adds_current_user(self):
        payload = hydrate_auth_state(
            {},
            SimpleNamespace(username="alice", role="maintainer"),
        )
        assert payload["current_user"] == {"username": "alice", "role": "maintainer"}

    def test_preserves_existing_keys(self):
        payload = hydrate_auth_state(
            {"hint": True},
            SimpleNamespace(username="bob", role="contributor"),
        )
        assert payload["hint"] is True
        assert payload["current_user"] == {"username": "bob", "role": "contributor"}

    def test_none_user_removes_current_user(self):
        payload = hydrate_auth_state(
            {"current_user": "old"},
            None,
        )
        assert "current_user" not in payload

    def test_none_session_ui(self):
        payload = hydrate_auth_state(None, SimpleNamespace(username="x", role="y"))
        assert payload["current_user"] == {"username": "x", "role": "y"}


class TestPrincipalLabel:
    def test_none_returns_dash(self):
        assert principal_label(None) == "-"

    def test_display_name(self):
        p = SimpleNamespace(display_name="Alice", slug="alice", id=1)
        assert principal_label(p) == "Alice"

    def test_slug_fallback(self):
        p = SimpleNamespace(display_name="", slug="alice", id=1)
        assert principal_label(p) == "alice"

    def test_id_fallback(self):
        p = SimpleNamespace(display_name="", slug="", id=42)
        assert principal_label(p) == "principal-42"


class TestIsOwner:
    def test_maintainer_is_always_owner(self):
        user = SimpleNamespace(role="maintainer")
        assert is_owner(user, None, None) is True

    def test_none_principal_ids(self):
        user = SimpleNamespace(role="contributor")
        assert is_owner(user, None, 1) is False
        assert is_owner(user, 1, None) is False

    def test_matching_principal_ids(self):
        user = SimpleNamespace(role="contributor")
        assert is_owner(user, 5, 5) is True

    def test_mismatching_principal_ids(self):
        user = SimpleNamespace(role="contributor")
        assert is_owner(user, 5, 6) is False
