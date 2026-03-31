from __future__ import annotations

from types import SimpleNamespace

from server.ui.auth_state import hydrate_auth_state


def test_hydrate_auth_state_adds_current_user_without_clobbering_existing_flags() -> None:
    payload = hydrate_auth_state(
        {"has_auth_cookie_hint": True},
        SimpleNamespace(username="fixture-maintainer", role="maintainer"),
    )

    assert payload["has_auth_cookie_hint"] is True
    assert payload["current_user"] == {
        "username": "fixture-maintainer",
        "role": "maintainer",
    }
