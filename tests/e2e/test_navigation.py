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
    authenticated_page.goto(f"{live_server}/manage?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    for label in ("Home", "Profile", "Management"):
        link = authenticated_page.query_selector(f".nav a:has-text('{label}')")
        assert link is not None, f"Admin nav link '{label}' not found"
        href = link.get_attribute("href")
        assert href is not None


def test_navigation_and_toggle_targets_are_at_least_44px(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/manage?lang=en")
    authenticated_page.wait_for_load_state("networkidle")

    targets = authenticated_page.query_selector_all(".nav a, .toggle-chip")
    visible_boxes = [target.bounding_box() for target in targets if target.is_visible()]
    assert visible_boxes
    assert all(box is not None and box["height"] >= 44 for box in visible_boxes)


def test_theme_tokens_meet_wcag_text_contrast(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/?lang=en")

    ratios = authenticated_page.evaluate(
        r"""
        () => {
          const channel = (value) => {
            value /= 255;
            return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
          };
          const channels = (color) => {
            const value = color.trim();
            if (value.startsWith('#')) {
              const hex = value.slice(1);
              return [0, 2, 4].map((offset) => parseInt(hex.slice(offset, offset + 2), 16));
            }
            return value.match(/[\d.]+/g).slice(0, 3).map(Number);
          };
          const luminance = (color) => {
            const rgb = channels(color).map(channel);
            return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
          };
          const contrast = (foreground, background) => {
            const first = luminance(foreground);
            const second = luminance(background);
            return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
          };
          const root = document.documentElement;
          return ['light', 'dark'].flatMap((scheme) => {
            root.dataset.colorScheme = scheme;
            const style = getComputedStyle(root);
            const samples = [
              ['kawaii-button kawai-button--primary', 'button'],
              ['kawaii-button kawai-button--secondary', 'button'],
              ['hero-kicker', 'span'],
              ['search-result__readiness search-result__readiness--stale', 'span'],
            ];
            const host = document.createElement('div');
            host.style.backgroundColor = 'var(--kawaii-surface)';
            document.body.appendChild(host);
            const measured = samples.map(([className, tag]) => {
              const element = document.createElement(tag);
              element.className = className;
              element.textContent = 'Contrast sample';
              host.appendChild(element);
              const computed = getComputedStyle(element);
              const background = computed.backgroundColor === 'rgba(0, 0, 0, 0)'
                ? getComputedStyle(host).backgroundColor
                : computed.backgroundColor;
              const ratio = contrast(computed.color, background);
              element.remove();
              return ratio;
            });
            host.remove();
            return [
              ...measured,
              contrast(
                style.getPropertyValue('--kawaii-ink-muted'),
                style.getPropertyValue('--kawaii-paper')
              ),
            ];
          });
        }
        """
    )
    assert all(ratio >= 4.5 for ratio in ratios), ratios


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


def test_console_pages_have_one_h1_and_compact_mobile_chrome(authenticated_page, live_server):
    authenticated_page.set_viewport_size({"width": 320, "height": 720})
    for path in ("/manage", "/settings", "/profile"):
        authenticated_page.goto(f"{live_server}{path}?lang=en")
        authenticated_page.wait_for_load_state("networkidle")
        assert authenticated_page.locator("main h1").count() == 1
        assert authenticated_page.locator("nav.fixed.bottom-0").count() == 0

    topbar = authenticated_page.locator(".topbar")
    box = topbar.bounding_box()
    assert box is not None and box["height"] < 220
    settings = authenticated_page.locator("#topbar-settings")
    assert settings.evaluate("element => getComputedStyle(element).display") == "none"
    authenticated_page.locator("#mobile-settings-toggle").click()
    assert settings.evaluate("element => getComputedStyle(element).display") == "flex"
