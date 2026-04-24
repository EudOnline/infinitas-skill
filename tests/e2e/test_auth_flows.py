from __future__ import annotations


def test_home_page_loads(page):
    assert page.title()
    heading = page.query_selector("h1, h2, .page-title")
    assert heading is not None


def test_login_page_exists(page, live_server):
    page.goto(f"{live_server}/login?lang=en")
    token_input = page.query_selector("#login-token-input")
    assert token_input is not None


def test_login_with_valid_token(live_server, browser):
    context = browser.new_context()
    pg = context.new_page()
    pg.goto(f"{live_server}/login?lang=en")
    pg.wait_for_selector("#login-token-input")
    pg.fill("#login-token-input", "e2e-maintainer-token")
    pg.click("#login-login-btn")
    pg.wait_for_load_state("networkidle")
    assert "/login" not in pg.url or pg.url.endswith("/")
    context.close()


def test_login_with_invalid_token(live_server, browser):
    context = browser.new_context()
    pg = context.new_page()
    pg.goto(f"{live_server}/login?lang=en")
    pg.wait_for_selector("#login-token-input")
    pg.fill("#login-token-input", "wrong-token-x")
    pg.click("#login-login-btn")
    pg.wait_for_timeout(1000)
    error = pg.query_selector("#login-auth-error:not([hidden])")
    context.close()
