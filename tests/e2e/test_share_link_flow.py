from __future__ import annotations


def test_shares_page_loads_admin_share_link_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/shares?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    assert authenticated_page.query_selector("text=Links") is not None
    assert authenticated_page.query_selector("text=Create Skill") is None
    assert authenticated_page.query_selector('[data-action="revoke-share-link"]') is None

