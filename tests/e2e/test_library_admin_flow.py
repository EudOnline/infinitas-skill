from __future__ import annotations


def test_library_page_replaces_old_console_actions(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/library?lang=en")
    authenticated_page.wait_for_load_state("networkidle")
    chrome_text = "\n".join(
        authenticated_page.locator("nav, header, h1, h2, button, label").all_inner_texts()
    )

    assert authenticated_page.query_selector("text=Library")
    assert authenticated_page.query_selector("[data-library-filter]") is not None
    assert authenticated_page.query_selector("[data-library-search]") is not None
    assert authenticated_page.query_selector("#create-skill-form") is None
    for legacy_phrase in ("Create Skill", "Create Draft", "Seal Draft", "lifecycle console"):
        assert legacy_phrase not in chrome_text
