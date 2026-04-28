from __future__ import annotations


def test_library_page_replaces_old_console_actions(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/library?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    assert authenticated_page.query_selector("text=Library")
    assert authenticated_page.query_selector("[data-library-filter]") is not None
    assert authenticated_page.query_selector("[data-library-search]") is not None
    assert authenticated_page.query_selector("text=Create Skill") is None
    assert authenticated_page.query_selector("#create-skill-form") is None
