from __future__ import annotations


def test_access_page_loads_token_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/manage?lang=en#tokens", wait_until="domcontentloaded")
    visible_text = authenticated_page.locator("body").inner_text()

    assert authenticated_page.query_selector("text=Access") is not None
    assert authenticated_page.query_selector("text=Tokens") is not None
    for legacy_phrase in ("Create Skill", "Create Draft", "Seal Draft", "lifecycle console"):
        assert legacy_phrase not in visible_text


def test_settings_page_loads_registry_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/settings?lang=en", wait_until="domcontentloaded")
    visible_text = authenticated_page.locator("body").inner_text()

    assert authenticated_page.query_selector("text=Settings") is not None
    assert authenticated_page.query_selector("text=Admin token") is not None
    assert authenticated_page.query_selector("text=Reference") is not None
    assert authenticated_page.query_selector("text=Scope") is not None
    for legacy_phrase in ("Create Skill", "Create Draft", "Seal Draft", "lifecycle console"):
        assert legacy_phrase not in visible_text
