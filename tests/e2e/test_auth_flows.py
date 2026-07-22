from __future__ import annotations

import re


def test_home_page_loads(page):
    assert page.title()
    heading = page.query_selector("h1, h2, .page-title")
    assert heading is not None


def test_login_page_exists(page, live_server):
    page.goto(f"{live_server}/login?lang=en", wait_until="domcontentloaded")
    username_input = page.query_selector("#login-username-input")
    assert username_input is not None
    password_input = page.query_selector("#login-password-input")
    assert password_input is not None

    password_toggle = page.query_selector("#login-password-toggle")
    assert password_toggle is not None
    box = password_toggle.bounding_box()
    assert box is not None
    assert box["width"] >= 44
    assert box["height"] >= 44


def test_login_with_valid_token(live_server, browser):
    context = browser.new_context()
    pg = context.new_page()
    pg.goto(f"{live_server}/login?lang=en", wait_until="domcontentloaded")
    pg.wait_for_selector("#login-username-input")
    pg.fill("#login-username-input", "e2e-maintainer")
    pg.fill("#login-password-input", "e2e-maintainer-password")
    home_url = re.compile(rf"{re.escape(live_server)}/\?lang=en$")
    with pg.expect_navigation(url=home_url, wait_until="commit"):
        with pg.expect_response("**/api/v1/auth/login*") as response_info:
            pg.click("#login-login-btn")
    response = response_info.value
    assert response.status == 200
    pg.wait_for_selector("#global-search")
    context.close()


def test_login_with_invalid_token(live_server, browser):
    context = browser.new_context()
    pg = context.new_page()
    pg.goto(f"{live_server}/login?lang=en", wait_until="domcontentloaded")
    pg.wait_for_selector("#login-username-input")
    pg.fill("#login-username-input", "e2e-maintainer")
    pg.fill("#login-password-input", "wrong-password-x")
    pg.click("#login-login-btn")
    pg.wait_for_timeout(1000)
    error = pg.query_selector("#login-auth-error:not([hidden])")
    assert error is not None
    context.close()
