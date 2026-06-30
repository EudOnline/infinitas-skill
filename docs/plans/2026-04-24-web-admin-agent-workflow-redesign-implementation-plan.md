# Web Admin And Agent Workflow Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current maintainer-console product flow with a human-admin web distribution console plus clean agent publish/read workflows for `skill`, `agent_preset`, and `agent_code`.

**Architecture:** Treat web admin and agent usage as separate products sharing the same release core. Keep internal lifecycle state (`draft`, `sealed version`, `release`, `artifact`, `exposure`, `review`) behind service boundaries, but expose only object, release, visibility, token, share link, and activity concepts in the web UI and public API. Frontend implementation should be generated and iterated with `kimi cli`, then integrated into the existing FastAPI + Jinja + static JS stack.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja templates, vanilla JS modules under `server/static/js/modules`, Playwright E2E tests, pytest integration tests, `kimi cli` for frontend generation.

---

## Implementation Rules

- This is a hard product cutover. Do not preserve the old `/skills` maintainer-console information architecture unless it is needed as a temporary redirect.
- The web product is for human admins only. Remove or demote skill authoring actions (`create skill`, `create draft`, `seal draft`, `create release`) from the primary web UI.
- Agent creation and release flows remain API/CLI-driven.
- `skill` remains the default featured object in the web UI, but the design and APIs must support `agent_preset` and `agent_code` as first-class objects.
- All net-new frontend layout and interaction work must be produced with `kimi cli`; hand edits should be limited to integration glue, route wiring, and bug fixes.

## Route Map To Build

- Web:
  - `/library`
  - `/library/{object_id}`
  - `/library/{object_id}/releases/{release_id}`
  - `/access`
  - `/shares`
  - `/activity`
  - `/settings`
- Agent-facing API:
  - `GET /api/library`
  - `GET /api/library/{object_id}`
  - `GET /api/library/{object_id}/releases`
  - `GET /api/releases/{release_id}`
  - `PATCH /api/releases/{release_id}/visibility`
  - `POST /api/v1/object-tokens/objects/{object_id}/tokens`
  - `GET /api/v1/object-tokens/objects/{object_id}/tokens`
  - `POST /api/releases/{release_id}/share-links`
  - `GET /api/releases/{release_id}/share-links`
  - `GET /api/activity`
  - `PUT /api/publish/objects/{slug}`
  - `POST /api/publish/objects/{object_id}/releases`
  - `GET /api/publish/releases/{release_id}/status`

## Product Vocabulary To Use

- Object
- Release
- Visibility
- Token
- Share Link
- Activity

## Product Vocabulary To Hide From The Web UI

- Draft
- Seal
- Exposure
- Grant
- Credential
- Review Case

### Task 1: Freeze The New Product Contract In Docs

**Files:**
- Create: `docs/specs/web-admin-agent-product-contract.md`
- Modify: `docs/guide/quickstart.md`
- Modify: `docs/reference/registry-cli.md`
- Modify: `docs/reference/error-catalog.md`
- Test: `tests/integration/test_reference_docs.py`

**Step 1: Write the failing docs contract test**

Add a focused doc test that asserts the new route names and vocabulary appear in the new spec and that the old maintainer-console wording is no longer the primary documented product surface.

```python
def test_web_admin_contract_uses_distribution_language():
    text = Path("docs/specs/web-admin-agent-product-contract.md").read_text(encoding="utf-8")
    assert "/library" in text
    assert "Share Link" in text
    assert "Token" in text
    assert "Maintainer-only console" not in text
```

**Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_reference_docs.py -q`

Expected: FAIL because the spec file does not exist yet.

**Step 3: Write the product contract**

Document:

- user personas
- route map
- object model
- token model
- share-link model
- hard requirement that frontend implementation uses `kimi cli`

**Step 4: Update CLI and quickstart docs**

Rewrite quickstart so:

- human admin actions reference `/library`, `/access`, `/shares`, `/activity`
- agent publish flow references `publish` endpoints instead of draft/seal as the primary story

**Step 5: Run the docs test again**

Run: `uv run pytest tests/integration/test_reference_docs.py -q`

Expected: PASS

**Step 6: Commit**

```bash
git add docs/specs/web-admin-agent-product-contract.md docs/guide/quickstart.md docs/reference/registry-cli.md docs/reference/error-catalog.md tests/integration/test_reference_docs.py
git commit -m "docs: define web admin and agent product contract"
```

### Task 2: Add A Unified Library Read Surface

**Files:**
- Create: `server/api/library.py`
- Create: `server/ui/library.py`
- Modify: `server/app.py`
- Modify: `server/ui/routes.py`
- Modify: `server/ui/navigation.py`
- Modify: `server/ui/formatting.py`
- Test: `tests/integration/test_library_api.py`
- Test: `tests/integration/test_library_pages.py`

**Step 1: Write the failing API tests**

Cover:

- object list includes `skill`, `agent_preset`, and `agent_code`
- list response uses unified object fields
- object detail returns type-specific data in a separate payload block

```python
def test_library_list_returns_multi_object_cards(client):
    response = client.get("/api/library")
    assert response.status_code == 200
    payload = response.json()
    assert {item["kind"] for item in payload["items"]} >= {"skill", "agent_preset", "agent_code"}
```

**Step 2: Write the failing page test**

Add a page contract test for `/library`.

Run: `uv run pytest tests/integration/test_library_api.py tests/integration/test_library_pages.py -q`

Expected: FAIL because the routes do not exist.

**Step 3: Implement a unified read service**

In `server/ui/library.py` and `server/api/library.py`, add helpers that normalize:

- base object fields
- default release info
- current visibility
- token/share counts
- type-specific fields

**Step 4: Wire the routes**

Register:

- `GET /library`
- `GET /library/{object_id}`
- `GET /library/{object_id}/releases/{release_id}`
- `GET /api/library`
- `GET /api/library/{object_id}`
- `GET /api/library/{object_id}/releases`

**Step 5: Run the focused tests**

Run: `uv run pytest tests/integration/test_library_api.py tests/integration/test_library_pages.py -q`

Expected: PASS

**Step 6: Commit**

```bash
git add server/api/library.py server/ui/library.py server/app.py server/ui/routes.py server/ui/navigation.py server/ui/formatting.py tests/integration/test_library_api.py tests/integration/test_library_pages.py
git commit -m "feat: add unified library read surfaces"
```

### Task 3: Build The New Web Navigation And Core Pages With Kimi CLI

**Files:**
- Create: `docs/specs/kimi-library-ui-spec.md`
- Create: `server/templates/library.html`
- Create: `server/templates/object-detail.html`
- Create: `server/templates/release-detail-v2.html`
- Create: `server/templates/access-center.html`
- Create: `server/templates/shares.html`
- Create: `server/templates/activity.html`
- Create: `server/templates/settings.html`
- Create: `server/static/js/modules/library.js`
- Create: `server/static/js/modules/access-center.js`
- Create: `server/static/js/modules/shares.js`
- Create: `server/static/js/modules/activity.js`
- Modify: `server/templates/layout-kawaii.html`
- Modify: `server/static/js/app.js`
- Modify: `server/static/css/input.css`
- Modify: `server/static/css/output.css`
- Test: `tests/e2e/test_library_admin_flow.py`
- Test: `tests/integration/test_private_registry_ui.py`

**Step 1: Write the failing E2E test**

Cover:

- `/library` loads
- list filters render
- object detail tabs render
- authoring actions are not visible in the primary UI

```python
def test_library_page_replaces_old_console_actions(authenticated_page, live_server):
    authenticated_page.goto(f"{live_server}/library?lang=en")
    assert authenticated_page.query_selector("text=Library")
    assert authenticated_page.query_selector("text=Create Skill") is None
```

**Step 2: Run the E2E and UI integration tests**

Run: `uv run pytest tests/e2e/test_library_admin_flow.py tests/integration/test_private_registry_ui.py -q`

Expected: FAIL because the pages and JS modules do not exist.

**Step 3: Write the Kimi CLI spec**

In `docs/specs/kimi-library-ui-spec.md`, define:

- page hierarchy
- component inventory
- copy rules
- explicit instruction to hide draft/exposure terminology

**Step 4: Generate frontend artifacts with Kimi CLI**

Use `kimi cli` to generate:

- new page templates
- shared layout updates
- supporting JS modules
- required CSS blocks

Keep the generated output focused on the new IA:

- Library
- Overview
- Releases
- Access
- Shares
- Activity

**Step 5: Integrate generated frontend with FastAPI routes**

Attach the new templates to the route context built in Task 2 and wire JS entrypoints from `server/static/js/app.js`.

**Step 6: Run the focused UI tests again**

Run: `uv run pytest tests/e2e/test_library_admin_flow.py tests/integration/test_private_registry_ui.py -q`

Expected: PASS

**Step 7: Commit**

```bash
git add docs/specs/kimi-library-ui-spec.md server/templates/library.html server/templates/object-detail.html server/templates/release-detail-v2.html server/templates/access-center.html server/templates/shares.html server/templates/activity.html server/templates/settings.html server/static/js/modules/library.js server/static/js/modules/access-center.js server/static/js/modules/shares.js server/static/js/modules/activity.js server/templates/layout-kawaii.html server/static/js/app.js server/static/css/input.css server/static/css/output.css tests/e2e/test_library_admin_flow.py tests/integration/test_private_registry_ui.py
git commit -m "feat: add kimi-driven web admin distribution interface"
```

### Task 4: Replace Credential Inspection With Product-Level Token Issuance

**Files:**
- Create: `server/api/object_tokens.py`
- Create: `server/modules/access/token_service.py`
- Modify: `server/modules/access/models.py`
- Modify: `server/modules/access/schemas.py`
- Modify: `server/modules/access/service.py`
- Modify: `server/ui/library.py`
- Modify: `server/ui/navigation.py`
- Test: `tests/integration/test_object_tokens_api.py`
- Test: `tests/integration/test_access_grant_boundaries.py`

**Step 1: Write the failing token issuance tests**

Cover:

- admin can create `reader` and `publisher` tokens
- token can be scoped to object or release
- raw token is returned once
- later reads return metadata only

```python
def test_create_reader_token_for_release(client, headers):
    response = client.post(
        "/api/objects/1/tokens",
        headers=headers,
        json={"name": "reader-a", "type": "reader", "scope_type": "release", "scope_id": 10},
    )
    assert response.status_code == 201
    assert response.json()["raw_token"].startswith("tok_")
```

**Step 2: Run the tests to verify failure**

Run: `uv run pytest tests/integration/test_object_tokens_api.py tests/integration/test_access_grant_boundaries.py -q`

Expected: FAIL because product token issuance does not exist.

**Step 3: Add product token fields**

Extend `Credential` or add a thin wrapper service so tokens carry:

- product type: `reader` or `publisher`
- scope type: `object` or `release`
- scope id
- label
- issued-for agent name
- expires-at
- revoked state

**Step 4: Implement issuance and listing endpoints**

Add:

- `POST /api/v1/object-tokens/objects/{object_id}/tokens`
- `GET /api/v1/object-tokens/objects/{object_id}/tokens`
- `POST /api/v1/object-tokens/tokens/{token_id}/revoke`

Do not expose `grant` or raw `credential` terminology in responses.

**Step 5: Run the tests again**

Run: `uv run pytest tests/integration/test_object_tokens_api.py tests/integration/test_access_grant_boundaries.py -q`

Expected: PASS

**Step 6: Commit**

```bash
git add server/api/object_tokens.py server/modules/access/token_service.py server/modules/access/models.py server/modules/access/schemas.py server/modules/access/service.py server/ui/library.py server/ui/navigation.py tests/integration/test_object_tokens_api.py tests/integration/test_access_grant_boundaries.py
git commit -m "feat: add product token issuance and scoping"
```

### Task 5: Add Share Links With Passwords, Expiry, And Usage Limits

**Files:**
- Create: `alembic/versions/20260424_0001_share_links.py`
- Create: `server/modules/shares/models.py`
- Create: `server/modules/shares/service.py`
- Create: `server/modules/shares/router.py`
- Create: `server/modules/shares/schemas.py`
- Modify: `server/models.py`
- Modify: `server/app.py`
- Modify: `server/ui/library.py`
- Modify: `server/static/js/modules/shares.js`
- Test: `tests/integration/test_share_links_api.py`
- Test: `tests/e2e/test_share_link_flow.py`

**Step 1: Write the failing API tests**

Cover:

- create share link for a release
- optional password
- expiry
- max uses
- revoke

```python
def test_create_passworded_share_link(client, headers):
    response = client.post(
        "/api/releases/10/share-links",
        headers=headers,
        json={"name": "temp-share", "password": "123456", "max_uses": 3},
    )
    assert response.status_code == 201
    assert response.json()["has_password"] is True
```

**Step 2: Write the failing E2E test**

Add an end-to-end test for the admin page and a password-protected link resolution.

**Step 3: Run the tests to verify failure**

Run: `uv run pytest tests/integration/test_share_links_api.py tests/e2e/test_share_link_flow.py -q`

Expected: FAIL because the share-link model and routes do not exist.

**Step 4: Add the model and migration**

Persist:

- release id
- slug or opaque token
- password hash
- expires at
- max uses
- used count
- revoked at

**Step 5: Implement admin and consume endpoints**

Add:

- `POST /api/releases/{release_id}/share-links`
- `GET /api/releases/{release_id}/share-links`
- `POST /api/share-links/{share_id}/revoke`
- `POST /api/share-links/{share_id}/resolve`

**Step 6: Run the focused tests**

Run: `uv run pytest tests/integration/test_share_links_api.py tests/e2e/test_share_link_flow.py -q`

Expected: PASS

**Step 7: Commit**

```bash
git add alembic/versions/20260424_0001_share_links.py server/modules/shares/models.py server/modules/shares/service.py server/modules/shares/router.py server/modules/shares/schemas.py server/models.py server/app.py server/ui/library.py server/static/js/modules/shares.js tests/integration/test_share_links_api.py tests/e2e/test_share_link_flow.py
git commit -m "feat: add share links with passwords and limits"
```

### Task 6: Add Human-Centric Activity And Audit Pages

**Files:**
- Create: `server/api/activity.py`
- Create: `server/ui/activity.py`
- Modify: `server/modules/audit/models.py`
- Modify: `server/modules/audit/service.py`
- Modify: `server/modules/release/service.py`
- Modify: `server/modules/access/token_service.py`
- Modify: `server/modules/shares/service.py`
- Test: `tests/integration/test_activity_api.py`
- Test: `tests/e2e/test_activity_page.py`

**Step 1: Write the failing activity tests**

Cover:

- token creation emits audit entries
- share-link access emits audit entries
- release visibility changes emit audit entries
- `/api/activity` returns normalized actor/action/result records

**Step 2: Run the tests to verify failure**

Run: `uv run pytest tests/integration/test_activity_api.py tests/e2e/test_activity_page.py -q`

Expected: FAIL because the normalized activity surface does not exist.

**Step 3: Normalize audit shape**

Add a product-facing event adapter that maps internal lifecycle events into:

- actor type
- actor label
- action
- object
- release
- outcome
- timestamp

**Step 4: Build the page and API**

Add:

- `GET /api/activity`
- `GET /api/tokens/{token_id}/activity`
- `GET /api/share-links/{share_id}/activity`

Wire the `/activity` page to these read surfaces.

**Step 5: Run the focused tests**

Run: `uv run pytest tests/integration/test_activity_api.py tests/e2e/test_activity_page.py -q`

Expected: PASS

**Step 6: Commit**

```bash
git add server/api/activity.py server/ui/activity.py server/modules/audit/models.py server/modules/audit/service.py server/modules/release/service.py server/modules/access/token_service.py server/modules/shares/service.py tests/integration/test_activity_api.py tests/e2e/test_activity_page.py
git commit -m "feat: add product activity and audit surfaces"
```

### Task 7: Add Object-Centric Publish APIs For Agents

**Files:**
- Create: `server/api/publish.py`
- Create: `server/modules/publish/service.py`
- Modify: `server/app.py`
- Modify: `server/modules/authoring/service.py`
- Modify: `server/modules/release/service.py`
- Modify: `src/infinitas_skill/registry/cli.py`
- Modify: `docs/reference/registry-cli.md`
- Test: `tests/integration/test_publish_api.py`
- Test: `tests/integration/test_multi_object_registry_surfaces.py`

**Step 1: Write the failing publish API tests**

Cover:

- `PUT /api/publish/objects/{slug}` upserts object metadata
- `POST /api/publish/objects/{object_id}/releases` creates a readying release without exposing draft/seal to the client
- publish works for `skill`, `agent_preset`, and `agent_code`

**Step 2: Run the tests to verify failure**

Run: `uv run pytest tests/integration/test_publish_api.py tests/integration/test_multi_object_registry_surfaces.py -q`

Expected: FAIL because the object-centric publish API does not exist.

**Step 3: Add a publish facade**

Implement a service that:

- resolves or creates the object record
- stages internal draft/seal work as needed
- creates the release
- returns a product-facing release status payload

**Step 4: Update CLI to use the new publish route**

Keep low-level draft/seal commands for advanced use, but switch examples and happy-path flows to the publish facade.

**Step 5: Run the focused tests**

Run: `uv run pytest tests/integration/test_publish_api.py tests/integration/test_multi_object_registry_surfaces.py -q`

Expected: PASS

**Step 6: Commit**

```bash
git add server/api/publish.py server/modules/publish/service.py server/app.py server/modules/authoring/service.py server/modules/release/service.py src/infinitas_skill/registry/cli.py docs/reference/registry-cli.md tests/integration/test_publish_api.py tests/integration/test_multi_object_registry_surfaces.py
git commit -m "feat: add object-centric publish APIs for agents"
```

### Task 8: Remove The Old Maintainer Console As The Primary Product Surface

**Files:**
- Modify: `server/ui/routes.py`
- Modify: `server/templates/index-kawaii.html`
- Modify: `server/templates/partials/home-console.html`
- Delete: `server/templates/skills.html`
- Delete: `server/templates/skill-detail.html`
- Delete: `server/templates/draft-detail.html`
- Delete: `server/templates/release-detail.html`
- Delete: `server/templates/share-detail.html`
- Delete: `server/templates/review-cases.html`
- Modify: `tests/e2e/test_auth_flows.py`
- Test: `tests/integration/test_library_pages.py`

**Step 1: Write the failing cutover assertions**

Add tests that assert:

- home links go to `/library`
- old `/skills` either redirects to `/library` or is removed
- old maintainer-console wording is no longer present on the homepage

**Step 2: Run the tests to verify failure**

Run: `uv run pytest tests/integration/test_library_pages.py tests/e2e/test_auth_flows.py -q`

Expected: FAIL because old navigation still points at `/skills`.

**Step 3: Cut over the routes and homepage**

Make `/library` the primary authenticated destination. If you keep `/skills`, make it a redirect only.

**Step 4: Remove old primary templates**

Delete or archive the old console templates once the new pages are in place and all tests target the new IA.

**Step 5: Run the focused tests**

Run: `uv run pytest tests/integration/test_library_pages.py tests/e2e/test_auth_flows.py -q`

Expected: PASS

**Step 6: Commit**

```bash
git add server/ui/routes.py server/templates/index-kawaii.html server/templates/partials/home-console.html tests/integration/test_library_pages.py tests/e2e/test_auth_flows.py
git rm server/templates/skills.html server/templates/skill-detail.html server/templates/draft-detail.html server/templates/release-detail.html server/templates/share-detail.html server/templates/review-cases.html
git commit -m "feat: cut over web product from maintainer console to library admin"
```

### Task 9: Full Verification And Closeout

**Files:**
- Modify: `README.md`
- Modify: `docs/guide/frontend-control-plane-alignment.md`
- Modify: `docs/guide/frontend-control-plane-checklist.md`
- Test: `tests/e2e/test_library_admin_flow.py`
- Test: `tests/e2e/test_share_link_flow.py`
- Test: `tests/e2e/test_activity_page.py`

**Step 1: Update repository docs**

Replace references that describe the web product as the primary maintainer lifecycle console. Document:

- web admin routes
- token model
- share-link model
- kimi cli frontend workflow

**Step 2: Run the fast maintained gate**

Run: `make ci-fast`

Expected: PASS

**Step 3: Run targeted integration coverage**

Run: `uv run pytest tests/integration/test_library_api.py tests/integration/test_object_tokens_api.py tests/integration/test_share_links_api.py tests/integration/test_activity_api.py tests/integration/test_publish_api.py tests/integration/test_multi_object_registry_surfaces.py -q`

Expected: PASS

**Step 4: Run the new E2E suite**

Run: `uv run pytest tests/e2e/test_library_admin_flow.py tests/e2e/test_share_link_flow.py tests/e2e/test_activity_page.py tests/e2e/test_auth_flows.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add README.md docs/guide/frontend-control-plane-alignment.md docs/guide/frontend-control-plane-checklist.md
git commit -m "docs: close out web admin and agent workflow redesign"
```

## Kimi CLI Execution Notes

- Generate all net-new frontend artifacts from the specs in `docs/specs/kimi-library-ui-spec.md`.
- Keep a saved prompt transcript or generated output manifest in `docs/specs/kimi-library-ui-spec.md` or an adjacent log file so later maintainers know what was asked of `kimi cli`.
- Do not let generated frontend copy reintroduce internal lifecycle terms into user-visible navigation or buttons.
- Treat `skill` as the default featured object in cards and examples, but verify that all object cards and detail tabs also render `agent_preset` and `agent_code`.

## Exit Criteria

- Web admins can manage objects from `/library` without seeing authoring-first workflow terms.
- Agents can publish through a single object-centric publish API.
- Reader and publisher tokens are first-class managed objects.
- Passworded share links exist and support expiry and usage limits.
- Activity pages expose human-readable audit data for tokens and shares.
- The new IA is covered by integration and E2E tests.
