from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from server.ui.auth_state import (
    hydrate_auth_state,
    is_owner,
    principal_label,
    require_draft_bundle_or_404,
    require_release_bundle_or_404,
    require_skill_or_404,
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


class TestRequireSkillOr404:
    def test_found_skill(self):
        mock_skill = MagicMock()
        db = MagicMock()
        db.get.return_value = mock_skill
        assert require_skill_or_404(db, 1) == mock_skill
        db.get.assert_called_once()

    def test_not_found_raises(self):
        db = MagicMock()
        db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            require_skill_or_404(db, 1)
        assert exc.value.status_code == 404


class TestRequireDraftBundleOr404:
    def test_found(self):
        mock_draft = MagicMock()
        mock_draft.skill_id = 2
        mock_skill = MagicMock()
        db = MagicMock()
        db.get.side_effect = [mock_draft, mock_skill]
        assert require_draft_bundle_or_404(db, 1) == (mock_draft, mock_skill)

    def test_draft_not_found(self):
        db = MagicMock()
        db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            require_draft_bundle_or_404(db, 1)
        assert exc.value.status_code == 404
        assert "draft" in exc.value.detail

    def test_skill_not_found(self):
        mock_draft = MagicMock()
        mock_draft.skill_id = 2
        db = MagicMock()
        db.get.side_effect = [mock_draft, None]
        with pytest.raises(HTTPException) as exc:
            require_draft_bundle_or_404(db, 1)
        assert exc.value.status_code == 404
        assert "skill" in exc.value.detail


class TestRequireReleaseBundleOr404:
    def test_found(self):
        mock_release = MagicMock()
        mock_release.skill_version_id = 2
        mock_version = MagicMock()
        mock_version.skill_id = 3
        mock_skill = MagicMock()
        db = MagicMock()
        db.get.side_effect = [mock_release, mock_version, mock_skill]
        assert require_release_bundle_or_404(db, 1) == (mock_release, mock_version, mock_skill)

    def test_release_not_found(self):
        db = MagicMock()
        db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            require_release_bundle_or_404(db, 1)
        assert exc.value.status_code == 404
        assert "release" in exc.value.detail

    def test_version_not_found(self):
        mock_release = MagicMock()
        mock_release.skill_version_id = 2
        db = MagicMock()
        db.get.side_effect = [mock_release, None]
        with pytest.raises(HTTPException) as exc:
            require_release_bundle_or_404(db, 1)
        assert exc.value.status_code == 404
        assert "version" in exc.value.detail

    def test_skill_not_found(self):
        mock_release = MagicMock()
        mock_release.skill_version_id = 2
        mock_version = MagicMock()
        mock_version.skill_id = 3
        db = MagicMock()
        db.get.side_effect = [mock_release, mock_version, None]
        with pytest.raises(HTTPException) as exc:
            require_release_bundle_or_404(db, 1)
        assert exc.value.status_code == 404
        assert "skill" in exc.value.detail
