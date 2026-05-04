from __future__ import annotations


def test_home_nav_has_anchor_links(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    for label in ("Home base", "Handoff", "Console"):
        link = authenticated_page.query_selector(f".nav a:has-text('{label}')")
        assert link is not None, f"Home nav link '{label}' not found"
        href = link.get_attribute("href")
        assert href is not None


def test_admin_nav_has_page_links(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/library?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    for label in ("Home", "Library", "Access", "Shares", "Activity", "Settings"):
        link = authenticated_page.query_selector(f".nav a:has-text('{label}')")
        assert link is not None, f"Admin nav link '{label}' not found"
        href = link.get_attribute("href")
        assert href is not None


def test_global_search_input_exists(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    search_input = authenticated_page.query_selector("#global-search")
    assert search_input is not None
    placeholder = search_input.get_attribute("placeholder")
    assert placeholder is not None


def test_language_toggle_changes_url(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    assert "lang=en" in authenticated_page.url or authenticated_page.url.endswith("/")

    zh_toggle = authenticated_page.query_selector("[data-lang-choice='zh']")
    if zh_toggle:
        zh_toggle.click()
        authenticated_page.wait_for_load_state("networkidle")
        assert "lang=zh" in authenticated_page.url


def test_user_panel_opens_and_shows_username(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    trigger = authenticated_page.query_selector("#user-trigger")
    assert trigger is not None

    panel = authenticated_page.query_selector("#user-panel")
    assert panel is not None
    assert panel.is_hidden()

    trigger.click()
    authenticated_page.wait_for_timeout(300)

    assert not panel.is_hidden()

    username = authenticated_page.query_selector("#user-panel-username")
    assert username is not None
    assert username.inner_text() == "e2e-maintainer"

    trigger.click()
    authenticated_page.wait_for_timeout(300)
