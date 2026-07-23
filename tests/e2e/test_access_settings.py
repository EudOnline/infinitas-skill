from __future__ import annotations


def test_access_page_loads_token_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/manage?lang=en#tokens", wait_until="domcontentloaded")
    visible_text = authenticated_page.locator("body").inner_text()

    assert authenticated_page.query_selector("text=Access") is not None
    assert authenticated_page.query_selector("text=Tokens") is not None
    for legacy_phrase in ("Create Skill", "Create Draft", "Seal Draft", "lifecycle console"):
        assert legacy_phrase not in visible_text


def test_settings_page_loads_registry_surface(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/settings?lang=en", wait_until="domcontentloaded")
    visible_text = authenticated_page.locator("body").inner_text()

    assert authenticated_page.query_selector("text=Settings") is not None
    assert authenticated_page.query_selector("text=Admin token") is not None
    assert authenticated_page.query_selector("text=Reference") is not None
    assert authenticated_page.query_selector("text=Scope") is not None
    assert authenticated_page.query_selector("#namespace-token-form") is not None
    for legacy_phrase in ("Create Skill", "Create Draft", "Seal Draft", "lifecycle console"):
        assert legacy_phrase not in visible_text


def test_settings_issues_and_revokes_namespace_agent_token(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/settings?lang=en", wait_until="domcontentloaded")
    form = authenticated_page.locator("#namespace-token-form")
    form.locator('[name="name"]').fill("e2e namespace publisher")
    form.locator('[name="expires_in_days"]').fill("30")
    form.locator('[name="max_daily_publishes"]').fill("25")
    form.locator('button[type="submit"]').click()

    result = authenticated_page.locator("#namespace-token-result")
    result.wait_for(state="visible")
    assert result.locator("code").inner_text().startswith("tok_")
    row = authenticated_page.locator("#namespace-token-list tbody tr").filter(
        has_text="e2e namespace publisher"
    )
    row.wait_for(state="visible")
    assert "publisher" in row.inner_text()
    row.get_by_role("button", name="Revoke").click()
    authenticated_page.wait_for_function(
        """() => [...document.querySelectorAll('#namespace-token-list tbody tr')]
          .some((row) => row.textContent.includes('e2e namespace publisher')
            && row.textContent.includes('revoked'))"""
    )
