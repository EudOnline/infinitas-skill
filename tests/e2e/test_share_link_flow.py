from __future__ import annotations


def test_shares_page_loads_admin_share_link_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/shares?lang=en")
    authenticated_page.wait_for_load_state("networkidle")
    visible_text = authenticated_page.locator("body").inner_text()

    assert authenticated_page.query_selector("text=Links") is not None
    assert authenticated_page.query_selector('[data-action="revoke-share-link"]') is None
    for legacy_phrase in ("Create Skill", "Create Draft", "Seal Draft", "lifecycle console"):
        assert legacy_phrase not in visible_text
