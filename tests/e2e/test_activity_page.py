from __future__ import annotations


def test_activity_page_loads_human_audit_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/activity?lang=en")
    authenticated_page.wait_for_load_state("networkidle")
    chrome_text = "\n".join(
        authenticated_page.locator("nav, header, h1, h2, button, label").all_inner_texts()
    )

    assert authenticated_page.query_selector("text=Activity") is not None
    assert authenticated_page.query_selector("[data-activity-filter]") is not None
    for legacy_phrase in (
        "Create Skill",
        "Create Draft",
        "Seal Draft",
        "Review Case",
        "lifecycle console",
    ):
        assert legacy_phrase not in chrome_text
