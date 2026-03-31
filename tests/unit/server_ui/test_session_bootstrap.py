from __future__ import annotations

from types import SimpleNamespace

from server.ui.navigation import build_site_nav
from server.ui.session_bootstrap import build_session_bootstrap


def test_build_session_bootstrap_preserves_cookie_hint_and_hydrates_current_user() -> None:
    payload = build_session_bootstrap(
        {"has_auth_cookie_hint": True},
        SimpleNamespace(username="fixture-maintainer", role="maintainer"),
    )

    assert payload == {
        "has_auth_cookie_hint": True,
        "current_user": {
            "username": "fixture-maintainer",
            "role": "maintainer",
        },
    }


def test_build_site_nav_assembles_language_aware_home_and_console_links() -> None:
    assert build_site_nav(home=True, lang="en") == [
        {"href": "#start", "label": "Home base"},
        {"href": "#handoff", "label": "Handoff"},
        {"href": "#console", "label": "Console"},
    ]
    assert build_site_nav(home=False, lang="en") == [
        {"href": "/?lang=en", "label": "Home"},
        {"href": "/skills?lang=en", "label": "Skills"},
        {"href": "/skills?lang=en#drafts", "label": "Drafts"},
        {"href": "/skills?lang=en#releases", "label": "Releases"},
        {"href": "/skills?lang=en#share", "label": "Share"},
        {"href": "/access/tokens?lang=en", "label": "Access"},
        {"href": "/review-cases?lang=en", "label": "Review"},
    ]
