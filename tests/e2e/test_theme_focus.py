from __future__ import annotations


def test_theme_toggle_persists(authenticated_page):
    html = authenticated_page.query_selector("html")
    initial_scheme = html.get_attribute("data-color-scheme") if html else None

    toggle = authenticated_page.query_selector("[data-theme-choice='dark']")
    if toggle:
        toggle.click()
        authenticated_page.wait_for_timeout(300)
        html = authenticated_page.query_selector("html")
        assert html.get_attribute("data-color-scheme") == "dark"

        toggle_light = authenticated_page.query_selector("[data-theme-choice='light']")
        if toggle_light:
            toggle_light.click()
            authenticated_page.wait_for_timeout(300)
            html = authenticated_page.query_selector("html")
            assert html.get_attribute("data-color-scheme") == "light"


def test_focus_mode_toggle(authenticated_page):
    btn = authenticated_page.query_selector("#focus-mode-toggle")
    assert btn is not None

    btn.click()
    authenticated_page.wait_for_timeout(200)

    html = authenticated_page.query_selector("html")
    class_list = html.get_attribute("class") or ""
    assert "focus-mode" in class_list

    deco = authenticated_page.query_selector(".floating-decoration")
    if deco:
        assert deco.is_hidden()

    btn.click()
    authenticated_page.wait_for_timeout(200)
    html = authenticated_page.query_selector("html")
    class_list = html.get_attribute("class") or ""
    assert "focus-mode" not in class_list
