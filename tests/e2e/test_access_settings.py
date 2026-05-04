from __future__ import annotations


def test_access_page_loads_token_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/access?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    assert authenticated_page.query_selector("text=Access") is not None
    assert authenticated_page.query_selector("text=Tokens") is not None
    assert authenticated_page.query_selector("text=Create Skill") is None


def test_settings_page_loads_registry_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/settings?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    assert authenticated_page.query_selector("text=Settings") is not None
    assert authenticated_page.query_selector("text=Admin token") is not None
    assert authenticated_page.query_selector("text=Reference") is not None
    assert authenticated_page.query_selector("text=Scope") is not None
    assert authenticated_page.query_selector("text=Create Skill") is None
