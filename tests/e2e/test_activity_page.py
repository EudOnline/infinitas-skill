from __future__ import annotations


def test_activity_page_loads_human_audit_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/manage?lang=en#activity", wait_until="domcontentloaded")
    chrome_text = "\n".join(
        authenticated_page.locator("nav, header, h1, h2, button, label").all_inner_texts()
    )

    assert authenticated_page.query_selector("text=Activity") is not None
    assert authenticated_page.query_selector("#manage-panel-activity") is not None
    selected = authenticated_page.locator('[data-view="activity"]').get_attribute("aria-selected")
    assert selected == "true"
    for legacy_phrase in (
        "Create Skill",
        "Create Draft",
        "Seal Draft",
        "Review Case",
        "lifecycle console",
    ):
        assert legacy_phrase not in chrome_text
