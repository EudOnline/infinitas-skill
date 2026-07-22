from __future__ import annotations


def test_hero_section_renders_copy_cta(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/?lang=en", wait_until="domcontentloaded")

    hero_title = authenticated_page.query_selector(".hero-title")
    assert hero_title is not None

    cta = authenticated_page.query_selector(".hero-cta")
    assert cta is not None

    quick_start = authenticated_page.query_selector(".quick-start")
    assert quick_start is not None


def test_console_grid_has_six_cards(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/?lang=en", wait_until="domcontentloaded")

    cards = authenticated_page.query_selector_all(".console-card")
    assert len(cards) >= 6

    labels = [c.inner_text() for c in cards]
    assert any("Library" in text for text in labels)
    assert any("Releases" in text for text in labels)
    assert any("Share Links" in text for text in labels)
    assert any("Access" in text for text in labels)
    assert any("Activity" in text for text in labels)
    assert any("Settings" in text for text in labels)


def test_mobile_nav_scrolls_horizontally(authenticated_page, live_server):
    authenticated_page.set_viewport_size({"width": 390, "height": 844})
    authenticated_page.goto(f"{live_server}/manage?lang=en", wait_until="domcontentloaded")

    nav = authenticated_page.query_selector(".nav")
    assert nav is not None

    style = authenticated_page.evaluate("(el) => window.getComputedStyle(el).overflowX", nav)
    assert style in ("auto", "scroll", "hidden")

    active = authenticated_page.query_selector('.nav a[aria-current="page"]')
    assert active is not None


def test_focus_mode_button_toggles_class(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/?lang=en", wait_until="domcontentloaded")

    btn = authenticated_page.query_selector("#focus-mode-toggle")
    assert btn is not None

    btn.click()
    authenticated_page.wait_for_timeout(200)

    html = authenticated_page.query_selector("html")
    classes = html.get_attribute("class") or ""
    assert "focus-mode" in classes

    btn.click()
    authenticated_page.wait_for_timeout(200)

    classes = html.get_attribute("class") or ""
    assert "focus-mode" not in classes
