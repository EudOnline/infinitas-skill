# Private-First Full Cutover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the legacy submission workflow with a fully private-first registry that uses drafts, releases, exposures, review cases, grants, credentials, and discovery as the only product lifecycle.

**Architecture:** Start from current `main`, selectively port the mature private-first domain/API modules from `codex/private-first-registry`, then cut over `server/app.py`, auth, worker, CLI, and UI so only the private-first lifecycle remains. Keep `/registry/*` as canonical install/discovery endpoints, but remove the old submission/review/job product flow.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, Jinja2, httpx, SQLite for local/dev, filesystem-backed immutable artifacts, `uv run`, hosted worker jobs.

---

### Task 1: Expand the schema to the canonical private-first model and drop legacy workflow tables

**Files:**
- Modify: `server/models.py`
- Modify: `server/modules/access/models.py`
- Modify: `server/modules/authoring/models.py`
- Modify: `server/modules/release/models.py`
- Modify: `server/modules/exposure/models.py`
- Modify: `server/modules/review/models.py`
- Create: `server/modules/audit/__init__.py`
- Create: `server/modules/audit/models.py`
- Create: `alembic/versions/20260329_0004_private_first_cutover.py`
- Create: `scripts/test-private-first-cutover-schema.py`

**Step 1: Write the failing schema cutover test**

Create `scripts/test-private-first-cutover-schema.py` that:

- runs `uv run alembic upgrade head` on a temp database
- verifies canonical tables exist: `principals`, `teams`, `team_memberships`, `service_principals`, `skills`, `skill_drafts`, `skill_versions`, `releases`, `artifacts`, `exposures`, `review_policies`, `review_cases`, `review_decisions`, `access_grants`, `credentials`, `audit_events`, `jobs`
- verifies legacy `submissions` and `reviews` are absent
- verifies `jobs` includes `release_id` and does not include `submission_id`

**Step 2: Run the test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-first-cutover-schema.py
```

Expected: FAIL because the canonical schema and legacy-table drop are not complete.

**Step 3: Implement the canonical schema**

- Port the richer model definitions from `codex/private-first-registry`
- Add audit models
- Create `20260329_0004_private_first_cutover.py` that:
  - extends the current partial schema to the canonical model
  - rebuilds `jobs` around `release_id`
  - drops `submissions` and `reviews`

**Step 4: Re-run the focused schema test**

Run:

```bash
uv run python3 scripts/test-private-first-cutover-schema.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add server/models.py server/modules/access/models.py server/modules/authoring/models.py server/modules/release/models.py server/modules/exposure/models.py server/modules/review/models.py server/modules/audit/__init__.py server/modules/audit/models.py alembic/versions/20260329_0004_private_first_cutover.py scripts/test-private-first-cutover-schema.py
git commit -m "feat: cut over schema to private-first model"
```

### Task 2: Cut over authentication and authorization to AccessContext-first behavior

**Files:**
- Modify: `server/auth.py`
- Modify: `server/api/auth.py`
- Modify: `server/settings.py`
- Modify: `server/modules/access/authn.py`
- Modify: `server/modules/access/authz.py`
- Modify: `server/modules/access/service.py`
- Create: `server/modules/access/schemas.py`
- Create: `server/modules/access/router.py`
- Create: `scripts/test-private-first-access-api.py`

**Step 1: Write the failing access cutover test**

Create `scripts/test-private-first-access-api.py` that verifies:

- bearer token auth resolves through `AccessContext`
- user-token bridge still allows operator login
- grant token access is scoped to allowed releases only
- global registry-reader token path is no longer required for discovery/install

**Step 2: Run the test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-first-access-api.py
```

Expected: FAIL because auth still depends on legacy/global reader behavior.

**Step 3: Implement the cutover**

- Port `AccessContext`-first auth behavior from `codex/private-first-registry`
- Make `require_registry_reader` and registry access checks resolve through private-first credentials
- Keep browser auth modal and `/api/v1/me` behavior compatible with current UI wording, but backed by the new access model

**Step 4: Re-run the focused access test**

Run:

```bash
uv run python3 scripts/test-private-first-access-api.py
uv run python3 scripts/test-hosted-registry-auth.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add server/auth.py server/api/auth.py server/settings.py server/modules/access/authn.py server/modules/access/authz.py server/modules/access/service.py server/modules/access/schemas.py server/modules/access/router.py scripts/test-private-first-access-api.py scripts/test-hosted-registry-auth.py
git commit -m "feat: cut over auth to private-first access context"
```

### Task 3: Port the private-first authoring, release, exposure, review, and discovery modules

**Files:**
- Create: `server/modules/authoring/schemas.py`
- Create: `server/modules/authoring/service.py`
- Create: `server/modules/authoring/router.py`
- Create: `server/modules/authoring/repository.py`
- Create: `server/modules/release/schemas.py`
- Create: `server/modules/release/service.py`
- Create: `server/modules/release/router.py`
- Create: `server/modules/release/materializer.py`
- Create: `server/modules/release/storage.py`
- Create: `server/modules/exposure/schemas.py`
- Create: `server/modules/exposure/service.py`
- Create: `server/modules/exposure/router.py`
- Create: `server/modules/review/schemas.py`
- Create: `server/modules/review/service.py`
- Create: `server/modules/review/router.py`
- Create: `server/modules/review/policy.py`
- Create: `server/modules/review/default_policy.py`
- Create: `server/modules/discovery/__init__.py`
- Create: `server/modules/discovery/schemas.py`
- Create: `server/modules/discovery/service.py`
- Create: `server/modules/discovery/router.py`
- Create: `server/modules/discovery/projections.py`
- Create: `server/modules/discovery/search.py`
- Create: `scripts/test-private-first-authoring-api.py`
- Create: `scripts/test-private-first-release-api.py`
- Create: `scripts/test-private-first-exposure-review.py`
- Create: `scripts/test-private-first-discovery.py`
- Create: `scripts/test-private-first-install-resolution.py`

**Step 1: Write the failing API tests**

Create focused tests that verify:

- skills and drafts can be created and sealed into versions
- releases can be created from versions and expose artifacts
- exposures can be created, activated, and reviewed
- discovery and install resolution return only audience-allowed releases

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run python3 scripts/test-private-first-authoring-api.py
uv run python3 scripts/test-private-first-release-api.py
uv run python3 scripts/test-private-first-exposure-review.py
uv run python3 scripts/test-private-first-discovery.py
uv run python3 scripts/test-private-first-install-resolution.py
```

Expected: FAIL because these services and routers are not mounted in `main`.

**Step 3: Port and adapt the private-first modules**

- Port the committed private-first service/router/schemas modules from `codex/private-first-registry`
- Adapt model imports and current schema names to the new cutover schema
- Ensure discovery powers both `/api/v1/...` and `/registry/...`

**Step 4: Re-run the focused API tests**

Run the same commands again.

Expected: PASS.

**Step 5: Commit**

```bash
git add server/modules/authoring server/modules/release server/modules/exposure server/modules/review server/modules/discovery scripts/test-private-first-authoring-api.py scripts/test-private-first-release-api.py scripts/test-private-first-exposure-review.py scripts/test-private-first-discovery.py scripts/test-private-first-install-resolution.py
git commit -m "feat: add private-first lifecycle and discovery modules"
```

### Task 4: Replace app composition, navigation, and hosted pages with the private-first workflow

**Files:**
- Modify: `server/app.py`
- Modify: `server/static/js/app.js`
- Modify: `server/templates/layout-kawaii.html`
- Modify: `server/templates/index-kawaii.html`
- Modify: `server/templates/login-kawaii.html`
- Create: `server/templates/skills.html`
- Create: `server/templates/skill-detail.html`
- Create: `server/templates/draft-detail.html`
- Create: `server/templates/release-detail.html`
- Create: `server/templates/share-detail.html`
- Create: `server/templates/access-tokens.html`
- Create: `server/templates/review-cases.html`
- Delete: `server/templates/submissions.html`
- Delete: `server/templates/reviews.html`
- Delete: `server/templates/jobs.html`
- Create: `scripts/test-private-first-ui.py`

**Step 1: Write the failing UI cutover test**

Create `scripts/test-private-first-ui.py` that verifies:

- homepage maintainer links point to `skills`, `access`, and `review`
- `/skills`, `/access/tokens`, and `/review-cases` render in the kawaii shell
- `/submissions`, `/reviews`, and `/jobs` no longer render as primary operator pages

**Step 2: Run the UI test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-first-ui.py
```

Expected: FAIL because the old console is still mounted.

**Step 3: Implement the cutover**

- Rebuild `server/app.py` routing around auth, background, access, authoring, release, exposure, review, and discovery
- Preserve current language/theme/auth-modal improvements from `main`
- Port the private-first page set from the experimental worktree and adapt it to current UI copy/context
- Remove the old operator pages and nav entries

**Step 4: Re-run the UI test and homepage/runtime checks**

Run:

```bash
uv run python3 scripts/test-private-first-ui.py
uv run python3 scripts/test-home-auth-session-runtime.py
uv run python3 scripts/test-home-kawaii-theme.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add server/app.py server/static/js/app.js server/templates/layout-kawaii.html server/templates/index-kawaii.html server/templates/login-kawaii.html server/templates/skills.html server/templates/skill-detail.html server/templates/draft-detail.html server/templates/release-detail.html server/templates/share-detail.html server/templates/access-tokens.html server/templates/review-cases.html scripts/test-private-first-ui.py
git commit -m "feat: replace hosted console with private-first workflow"
```

### Task 5: Replace the worker, CLI, and registry scripts with release-centric behavior

**Files:**
- Modify: `server/jobs.py`
- Modify: `server/worker.py`
- Modify: `scripts/registryctl.py`
- Modify: `scripts/http_registry_lib.py`
- Modify: `scripts/install-by-name.sh`
- Modify: `scripts/pull-skill.sh`
- Modify: `scripts/resolve-install-plan.py`
- Modify: `scripts/check-skill-update.sh`
- Delete: `scripts/approve-skill.sh`
- Delete: `scripts/promote-skill.sh`
- Delete: `scripts/publish-skill.sh`
- Delete: `scripts/request-review.sh`
- Create: `scripts/test-private-first-release-worker.py`
- Create: `scripts/test-private-first-cli.py`

**Step 1: Write the failing worker and CLI tests**

Create tests that verify:

- `materialize_release` is the only supported lifecycle job kind
- `registryctl` lists/releases/shares/access entities instead of submissions
- install scripts resolve the private-first discovery/install metadata

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run python3 scripts/test-private-first-release-worker.py
uv run python3 scripts/test-private-first-cli.py
```

Expected: FAIL because the worker and CLI still expose legacy workflow semantics.

**Step 3: Implement the cutover**

- Update worker and job helpers to process only release-centric jobs
- Port `registryctl` private-first commands from the experimental branch
- remove obsolete submission/review shell scripts

**Step 4: Re-run the focused worker and CLI tests**

Run the same commands again.

Expected: PASS.

**Step 5: Commit**

```bash
git add server/jobs.py server/worker.py scripts/registryctl.py scripts/http_registry_lib.py scripts/install-by-name.sh scripts/pull-skill.sh scripts/resolve-install-plan.py scripts/check-skill-update.sh scripts/test-private-first-release-worker.py scripts/test-private-first-cli.py
git rm scripts/approve-skill.sh scripts/promote-skill.sh scripts/publish-skill.sh scripts/request-review.sh
git commit -m "feat: cut over worker and cli to release lifecycle"
```

### Task 6: Remove legacy product surfaces, rewrite docs, and run the full cutover matrix

**Files:**
- Delete: `server/api/submissions.py`
- Delete: `server/api/reviews.py`
- Delete: `server/api/skills.py`
- Delete: `server/api/jobs.py`
- Delete: `server/api/search.py`
- Delete: `server/schemas.py`
- Modify: `README.md`
- Modify: `docs/ai/server-api.md`
- Modify: `docs/ai/publish.md`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/ai/pull.md`
- Create: `docs/private-first-cutover.md`

**Step 1: Remove the old mounted product surfaces**

Delete the old routers and schemas once `server/app.py` no longer imports them.

**Step 2: Rewrite docs**

Document:

- private-first lifecycle
- private operator UI
- release materialization
- exposure/review/access semantics
- discovery/install flow

**Step 3: Run the final verification matrix**

Run:

```bash
uv run python3 scripts/test-private-first-cutover-schema.py
uv run python3 scripts/test-private-first-access-api.py
uv run python3 scripts/test-private-first-authoring-api.py
uv run python3 scripts/test-private-first-release-api.py
uv run python3 scripts/test-private-first-exposure-review.py
uv run python3 scripts/test-private-first-discovery.py
uv run python3 scripts/test-private-first-install-resolution.py
uv run python3 scripts/test-private-first-ui.py
uv run python3 scripts/test-private-first-release-worker.py
uv run python3 scripts/test-private-first-cli.py
uv run python3 scripts/test-home-auth-session-runtime.py
uv run python3 scripts/test-home-kawaii-theme.py
```

Expected: PASS.

**Step 4: Commit**

```bash
git add README.md docs/ai/server-api.md docs/ai/publish.md docs/ai/discovery.md docs/ai/pull.md docs/private-first-cutover.md
git rm server/api/submissions.py server/api/reviews.py server/api/skills.py server/api/jobs.py server/api/search.py server/schemas.py
git commit -m "feat: finalize private-first full cutover"
```
