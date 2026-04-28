from __future__ import annotations


def test_activity_page_loads_human_audit_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/activity?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    assert authenticated_page.query_selector("text=Activity") is not None
    assert authenticated_page.query_selector("[data-activity-filter]") is not None
    assert authenticated_page.query_selector("text=Review Case") is None

