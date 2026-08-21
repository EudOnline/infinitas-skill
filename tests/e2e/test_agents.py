from __future__ import annotations


def test_agent_invitation_form_displays_one_time_prompt(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/agents", wait_until="domcontentloaded")
    assert authenticated_page.locator('meta[name="csrf-token"]').get_attribute("content")
    authenticated_page.locator('input[name="slug"]').fill("browser-agent")
    authenticated_page.locator('input[name="display_name"]').fill("Browser Agent")
    authenticated_page.get_by_role("button", name="创建邀请").click()

    authenticated_page.wait_for_timeout(1000)
    body_text = authenticated_page.locator("body").inner_text()
    assert "复制提示词" in body_text, body_text
    prompt = authenticated_page.locator("#agent-prompt")
    assert "infinitas agent join" in prompt.input_value()
    assert "enroll_" in prompt.input_value()
    assert authenticated_page.locator("script:not([src])").count() == 0

    authenticated_page.locator("#copy-agent-prompt").click()
    authenticated_page.wait_for_timeout(200)
    assert authenticated_page.locator("#copy-agent-prompt-status").inner_text()


def test_agents_page_is_usable_at_320px(authenticated_page, live_server):
    authenticated_page.set_viewport_size({"width": 320, "height": 720})
    authenticated_page.goto(f"{live_server}/agents", wait_until="domcontentloaded")

    dimensions = authenticated_page.evaluate(
        "({scrollWidth: document.documentElement.scrollWidth, "
        "clientWidth: document.documentElement.clientWidth})"
    )
    offenders = authenticated_page.locator("body *").evaluate_all(
        "elements => elements.filter(element => element.getBoundingClientRect().right > "
        "document.documentElement.clientWidth + 1).map(element => ({tag: element.tagName, "
        "className: element.className, text: element.textContent?.trim().slice(0, 80), "
        "right: element.getBoundingClientRect().right}))"
    )
    assert dimensions["scrollWidth"] <= dimensions["clientWidth"], offenders
    sizes = authenticated_page.locator("main button, main .agent-auto-public").evaluate_all(
        "elements => elements.map(element => { const rect = element.getBoundingClientRect(); "
        "return {width: rect.width, height: rect.height}; })"
    )
    assert sizes
    assert all(item["height"] >= 44 for item in sizes)
