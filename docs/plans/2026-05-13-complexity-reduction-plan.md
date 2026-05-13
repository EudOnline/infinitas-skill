# Complexity Reduction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the old lifecycle model as a maintained product surface and reduce control-plane complexity by converging on one publish model, one share model, one activity truth source, and smaller projection modules.

**Architecture:** Execute the simplification in two layers. First remove external dual-track behavior so contributors and users only see the private-first object/release/exposure/distribution model. Then replace the deepest internal legacy lifecycle dependency by collapsing draft-and-seal internals into direct version creation. Do not start with the deepest refactor first.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja templates, ES modules, pytest, Playwright, maintained `infinitas` CLI

---

## Target End State

The repository should converge on this model:

- one public product story: `object -> release -> exposure -> distribution`
- one browser product story: Library distribution console
- one share implementation: `AccessGrant + Credential`
- one activity truth source: backend audit events
- one publish implementation path: direct version/release creation without maintained draft/seal semantics

The repository should no longer require contributors to understand the old lifecycle console model in order to ship routine work.

### Task 1: Freeze the canonical model and add guardrails

**Files:**
- Modify: `docs/guide/control-plane-business-flows.md`
- Modify: `docs/guide/frontend-control-plane-alignment.md`
- Modify: `docs/guide/frontend-control-plane-checklist.md`
- Modify: `docs/reference/api-reference.md`
- Modify: `tests/e2e/test_library_admin_flow.py`
- Modify: `tests/integration/test_private_registry_ui.py`

**Step 1: Write the failing assertions**

Add or tighten assertions that the maintained browser product must not expose:

- create skill
- create draft
- seal draft
- lifecycle-console wording

Also add doc assertions in `tests/integration/test_private_registry_ui.py` that reject references to the old lifecycle as a maintained primary flow.

**Step 2: Run the focused tests**

Run:

```bash
uv run pytest tests/e2e/test_library_admin_flow.py tests/integration/test_private_registry_ui.py -q
```

Expected:

- existing assertions pass or reveal the next legacy references to remove

**Step 3: Tighten docs**

Update docs so they explicitly state:

- old lifecycle model is not maintained
- old routes may exist only as temporary redirects or migration shims
- new work must use the object/release/exposure/distribution story

**Step 4: Re-run the tests**

Run:

```bash
uv run pytest tests/integration/test_private_registry_ui.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add docs/guide/control-plane-business-flows.md docs/guide/frontend-control-plane-alignment.md docs/guide/frontend-control-plane-checklist.md docs/reference/api-reference.md tests/e2e/test_library_admin_flow.py tests/integration/test_private_registry_ui.py
git commit -m "docs: freeze canonical control-plane model"
```

### Task 2: Remove legacy frontend lifecycle initialization

**Files:**
- Modify: `server/static/js/app.js`
- Modify: `server/static/js/modules/lifecycle.js`
- Modify: `server/templates/layout-kawaii.html`
- Modify: `tests/integration/test_private_registry_ui.py`
- Modify: `tests/e2e/test_access_settings.py`
- Modify: `tests/e2e/test_share_link_flow.py`

**Step 1: Write the failing tests**

Add assertions that:

- the global app bootstrap no longer initializes `initCreateSkill`, `initCreateDraft`, or legacy release-detail lifecycle entrypoints for the maintained browser product
- no frontend contract test expects the old forms or lifecycle button plumbing

**Step 2: Run the focused tests**

Run:

```bash
uv run pytest tests/integration/test_private_registry_ui.py tests/e2e/test_access_settings.py tests/e2e/test_share_link_flow.py -q
```

Expected:

- FAIL on current legacy bootstrap references

**Step 3: Write the minimal implementation**

Change the app bootstrap so the maintained browser shell initializes only:

- search
- theme
- table helpers
- library page helpers
- release admin helpers
- access/shares/activity helpers

Do not delete `lifecycle.js` until no maintained template imports or depends on it.

**Step 4: Re-run the tests**

Run:

```bash
uv run pytest tests/integration/test_private_registry_ui.py tests/e2e/test_library_admin_flow.py tests/e2e/test_access_settings.py tests/e2e/test_share_link_flow.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add server/static/js/app.js server/static/js/modules/lifecycle.js server/templates/layout-kawaii.html tests/integration/test_private_registry_ui.py tests/e2e/test_access_settings.py tests/e2e/test_share_link_flow.py
git commit -m "refactor: remove legacy lifecycle bootstrap from frontend"
```

### Task 3: Consolidate share links onto the grant model

**Files:**
- Modify: `server/api/library.py`
- Modify: `server/ui/library.py`
- Modify: `server/static/js/modules/release-admin.js`
- Modify: `server/static/js/modules/shares.js`
- Modify: `server/api/activity.py`
- Delete or retire: `server/modules/shares/router.py`
- Delete or retire: `server/modules/shares/service.py`
- Delete or retire: `server/modules/shares/models.py`
- Modify: `server/app.py`
- Modify: `tests/integration/test_share_links_api.py`
- Modify: `tests/integration/test_library_api.py`
- Modify: `tests/integration/test_activity_api.py`

**Step 1: Write the failing tests**

Rewrite share-link integration tests so the maintained share flow uses one model:

- create share from the release admin path
- list shares from the same underlying data
- resolve and revoke through one share identity model
- record activity under one aggregate shape

**Step 2: Run the focused tests**

Run:

```bash
uv run pytest tests/integration/test_share_links_api.py tests/integration/test_library_api.py tests/integration/test_activity_api.py -q
```

Expected:

- FAIL because the code still uses dual implementations

**Step 3: Write the minimal implementation**

Choose `AccessGrant + Credential` as the only maintained share model.

Implementation rules:

- keep one share identifier shape
- keep one revoke path
- keep one resolve path
- keep one UI listing path
- migrate any remaining standalone `ShareLink` behavior into grant-backed logic

If backward-compatible routes must remain temporarily, they should be thin adapters over the grant model rather than separate persistence.

**Step 4: Re-run the tests**

Run:

```bash
uv run pytest tests/integration/test_share_links_api.py tests/integration/test_library_api.py tests/integration/test_activity_api.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add server/api/library.py server/ui/library.py server/static/js/modules/release-admin.js server/static/js/modules/shares.js server/api/activity.py server/app.py tests/integration/test_share_links_api.py tests/integration/test_library_api.py tests/integration/test_activity_api.py
git commit -m "refactor: unify share links on access grants"
```

### Task 4: Make backend audit the only activity truth source

**Files:**
- Modify: `server/api/activity.py`
- Modify: `server/ui/routes.py`
- Modify: `server/ui/library.py`
- Create: `server/ui/activity.py`
- Modify: `server/templates/activity.html`
- Modify: `server/static/js/modules/activity.js`
- Modify: `tests/integration/test_activity_api.py`
- Modify: `tests/unit/server_ui/test_navigation.py`

**Step 1: Write the failing tests**

Add assertions that the activity page renders from normalized audit-event rows, not synthetic share/token projection rows assembled separately from current state.

**Step 2: Run the focused tests**

Run:

```bash
uv run pytest tests/integration/test_activity_api.py tests/unit/server_ui/test_navigation.py -q
```

Expected:

- FAIL on current projection-driven behavior

**Step 3: Write the minimal implementation**

Refactor activity rendering so:

- API remains the normalized audit source
- UI page uses an adapter over audit events
- display formatting stays UI-owned
- event truth stays backend-audit-owned

Keep filtering in `activity.js`, but stop inventing the event list in `server/ui/library.py`.

**Step 4: Re-run the tests**

Run:

```bash
uv run pytest tests/integration/test_activity_api.py tests/unit/server_ui/test_navigation.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add server/api/activity.py server/ui/routes.py server/ui/library.py server/ui/activity.py server/templates/activity.html server/static/js/modules/activity.js tests/integration/test_activity_api.py tests/unit/server_ui/test_navigation.py
git commit -m "refactor: make audit events the single activity truth"
```

### Task 5: Split `server/ui/library.py` into stable projection modules

**Files:**
- Modify: `server/ui/library.py`
- Create: `server/ui/library_scope.py`
- Create: `server/ui/library_objects.py`
- Create: `server/ui/library_releases.py`
- Create: `server/ui/library_access.py`
- Create: `server/ui/library_shares.py`
- Modify: `server/ui/routes.py`
- Modify: `tests/integration/test_library_pages.py`
- Modify: `tests/integration/test_library_api.py`

**Step 1: Write the failing tests**

Add or preserve coverage for:

- library list
- object detail
- release detail
- access center
- shares page

The goal is to pin behavior before the module split.

**Step 2: Run the focused tests**

Run:

```bash
uv run pytest tests/integration/test_library_pages.py tests/integration/test_library_api.py -q
```

Expected:

- PASS before refactor, then continue as a safety net

**Step 3: Write the minimal implementation**

Split the current god-module by read model:

- scope loading
- object list payloads
- release detail payloads
- token rows
- share rows

Rules:

- one module per projection family
- no page should depend on unrelated row builders
- keep route signatures stable during the split

**Step 4: Re-run the tests**

Run:

```bash
uv run pytest tests/integration/test_library_pages.py tests/integration/test_library_api.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add server/ui/library.py server/ui/library_scope.py server/ui/library_objects.py server/ui/library_releases.py server/ui/library_access.py server/ui/library_shares.py server/ui/routes.py tests/integration/test_library_pages.py tests/integration/test_library_api.py
git commit -m "refactor: split library projections into focused modules"
```

### Task 6: Remove maintained draft/seal semantics from the publish path

**Files:**
- Modify: `server/api/publish.py`
- Modify: `server/modules/authoring/service.py`
- Modify: `server/modules/authoring/router.py`
- Modify: `server/modules/authoring/models.py`
- Modify: `server/modules/release/service.py`
- Modify: `server/modules/release/materializer.py`
- Modify: `server/models.py`
- Modify: `tests/integration/test_publish_api.py`
- Modify: `tests/integration/test_cli_mutation_workflows.py`
- Modify: `tests/integration/test_reference_docs.py`
- Modify: `docs/reference/api-reference.md`
- Modify: `docs/reference/registry-cli.md`

**Step 1: Write the failing tests**

Add assertions that the maintained publish path can create a version snapshot directly from object content without requiring draft or seal as a maintained concept.

Keep one narrow compatibility test only if a temporary migration endpoint must exist.

**Step 2: Run the focused tests**

Run:

```bash
uv run pytest tests/integration/test_publish_api.py tests/integration/test_cli_mutation_workflows.py tests/integration/test_reference_docs.py -q
```

Expected:

- FAIL because the current implementation still depends on draft/seal internals

**Step 3: Write the minimal implementation**

Refactor toward:

- object content snapshot creates immutable version directly
- release creation reads immutable version directly
- draft/seal terminology removed from maintained docs and maintained mutation workflows

Do this only after Tasks 1-5 are complete, because this is the highest-risk internal cut.

**Step 4: Re-run the tests**

Run:

```bash
uv run pytest tests/integration/test_publish_api.py tests/integration/test_cli_mutation_workflows.py tests/integration/test_reference_docs.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add server/api/publish.py server/modules/authoring/service.py server/modules/authoring/router.py server/modules/authoring/models.py server/modules/release/service.py server/modules/release/materializer.py server/models.py tests/integration/test_publish_api.py tests/integration/test_cli_mutation_workflows.py tests/integration/test_reference_docs.py docs/reference/api-reference.md docs/reference/registry-cli.md
git commit -m "refactor: remove maintained draft seal publish model"
```

## Sequencing Rules

- Complete Tasks 1-2 before touching persistence or activity semantics.
- Complete Task 3 before Task 4, because share activity depends on the canonical share identity.
- Complete Task 5 before Task 6, because smaller projection modules reduce refactor blast radius.
- Do not start Task 6 until the maintained browser and API surfaces no longer depend on the old model.

## Verification Matrix

After all tasks:

```bash
make lint-maintained
make test-fast
uv run pytest tests/integration/test_publish_api.py tests/integration/test_library_api.py tests/integration/test_share_links_api.py tests/integration/test_activity_api.py tests/integration/test_private_registry_ui.py tests/e2e/test_library_admin_flow.py -q
```

Expected:

- all maintained-surface tests pass
- no maintained docs present the old lifecycle as the primary product model
- no maintained browser flow depends on legacy lifecycle initialization

## Success Criteria

The complexity reduction is complete when all of the following are true:

- one share model exists in maintained code
- one activity truth source exists in maintained code
- one frontend product story exists in maintained code
- one maintained publish story exists in maintained docs and APIs
- contributors can modify distribution workflows without understanding the old lifecycle console
