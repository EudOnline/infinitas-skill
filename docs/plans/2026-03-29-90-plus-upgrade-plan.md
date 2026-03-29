# 90+ Project Quality Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raise `infinitas-skill` from roughly 85/100 to 90+ by hardening auth and configuration, removing legacy token risk, reducing maintenance hotspots, and turning the new guardrails into enforced regression checks.

**Architecture:** Keep the existing FastAPI + Jinja + Alembic structure, but improve it through small, low-risk slices. Do the work in this order: browser-session hardening, configuration hard fails, token model cleanup, template/controller decomposition, then CI and docs updates so the new behavior stays enforced.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Jinja2, uvicorn, Playwright-backed runtime scripts, GitHub Actions.

---

### Task 1: Harden Browser Auth Sessions

**Files:**
- Modify: `scripts/test-home-auth-session-runtime.py`
- Modify: `server/api/auth.py`
- Modify: `server/templates/index-kawaii.html`
- Modify: `server/templates/layout-kawaii.html`
- Modify: `server/templates/login-kawaii.html`
- Test: `scripts/test-home-auth-session-runtime.py`
- Test: `scripts/test-private-registry-ui.py`

**Step 1: Write the failing test**

Extend `scripts/test-home-auth-session-runtime.py` so the authenticated browser path asserts all of the following:
- login succeeds and `/api/auth/me` reports the user as authenticated
- `document.cookie` does not expose `infinitas_auth_token`
- the home and layout flows no longer require client-side cookie parsing to hydrate the user panel
- logout still returns the page to an anonymous state

**Step 2: Run test to verify it fails**

Run:

```bash
uv run python3 scripts/test-home-auth-session-runtime.py
```

Expected: `FAIL` because the current runtime explicitly checks `document.cookie` for `infinitas_auth_token`.

**Step 3: Write minimal implementation**

Make the browser session cookie server-only:
- set `httponly=True` in `server/api/auth.py`
- set `secure` from environment or request policy rather than hard-coding it off forever
- stop reading auth state from `document.cookie` in the Jinja templates
- use `/api/auth/me` plus in-memory UI state to drive authenticated/anonymous rendering
- make logout rely on `/api/auth/logout` and explicit UI reset, not cookie string mutation in the browser

**Step 4: Run tests to verify it passes**

Run:

```bash
uv run python3 scripts/test-home-auth-session-runtime.py
uv run python3 scripts/test-private-registry-ui.py
```

Expected: both scripts print `OK`.

**Step 5: Commit**

```bash
git add scripts/test-home-auth-session-runtime.py server/api/auth.py server/templates/index-kawaii.html server/templates/layout-kawaii.html server/templates/login-kawaii.html
git commit -m "feat: harden browser auth session handling"
```

### Task 2: Require Explicit Production Secrets and Bootstrap Configuration

**Files:**
- Create: `scripts/test-settings-hardening.py`
- Modify: `server/settings.py`
- Modify: `.env.compose.example`
- Modify: `README.md`
- Modify: `docs/ops/server-deployment.md`
- Test: `scripts/test-settings-hardening.py`

**Step 1: Write the failing test**

Create `scripts/test-settings-hardening.py` with scenarios that assert:
- production-like startup fails when `INFINITAS_SERVER_SECRET_KEY` is missing or equals `change-me`
- production-like startup fails when bootstrap users are omitted
- local/test mode can still opt into fixture defaults explicitly

**Step 2: Run test to verify it fails**

Run:

```bash
uv run python3 scripts/test-settings-hardening.py
```

Expected: `FAIL` because `server/settings.py` currently allows the default secret and implicit bootstrap users.

**Step 3: Write minimal implementation**

Update `server/settings.py` to introduce an explicit environment mode, for example `INFINITAS_SERVER_ENV=development|test|production`, then:
- reject `change-me` in production
- require explicit bootstrap users in production
- keep the current defaults only for development/test or an explicit insecure-local flag
- document the required variables in `.env.compose.example`, `README.md`, and `docs/ops/server-deployment.md`

**Step 4: Run tests to verify it passes**

Run:

```bash
uv run python3 scripts/test-settings-hardening.py
uv run python3 scripts/test-private-registry-ui.py
```

Expected: hardening test prints `OK`; UI script still prints `OK`.

**Step 5: Commit**

```bash
git add scripts/test-settings-hardening.py server/settings.py .env.compose.example README.md docs/ops/server-deployment.md
git commit -m "feat: require explicit production auth configuration"
```

### Task 3: Remove Plaintext Personal Token Dependency

**Files:**
- Create: `alembic/versions/20260329_0005_personal_token_hash_cutover.py`
- Modify: `server/models.py`
- Modify: `server/db.py`
- Modify: `server/modules/access/service.py`
- Modify: `scripts/test-private-registry-access-api.py`
- Modify: `scripts/test-home-auth-session-runtime.py`
- Test: `scripts/test-private-registry-access-api.py`

**Step 1: Write the failing test**

Expand `scripts/test-private-registry-access-api.py` to verify:
- personal auth resolves through hashed credential records, not a plaintext `users.token` lookup
- migrated fixture users continue to authenticate
- legacy plaintext-only records are upgraded or rejected according to the migration policy you choose

**Step 2: Run test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-access-api.py
```

Expected: `FAIL` because personal token bridging still depends on plaintext `User.token`.

**Step 3: Write minimal implementation**

Cut personal auth over to credential-backed hashes:
- add a migration that creates the new storage shape you need and backfills existing data
- stop using `User.token` as the source of truth for runtime auth
- keep `Credential.hashed_secret` as the canonical secret store for personal tokens
- if a transition path is required, make it one-way: migrate old plaintext data, then authenticate against hashes only

**Step 4: Run tests to verify it passes**

Run:

```bash
uv run python3 scripts/test-private-registry-access-api.py
uv run python3 scripts/test-home-auth-session-runtime.py
uv run python3 scripts/test-private-first-cutover-schema.py
```

Expected: all scripts print `OK`.

**Step 5: Commit**

```bash
git add alembic/versions/20260329_0005_personal_token_hash_cutover.py server/models.py server/db.py server/modules/access/service.py scripts/test-private-registry-access-api.py scripts/test-home-auth-session-runtime.py
git commit -m "feat: cut personal auth over to hashed credentials"
```

### Task 4: Split Oversized UI and Controller Surfaces

**Files:**
- Create: `server/ui/__init__.py`
- Create: `server/ui/home.py`
- Create: `server/ui/console.py`
- Create: `server/templates/partials/home-auth-panel.html`
- Create: `server/templates/partials/home-hero.html`
- Create: `server/templates/partials/home-console.html`
- Create: `server/static/js/auth-session.js`
- Modify: `server/app.py`
- Modify: `server/templates/index-kawaii.html`
- Modify: `server/templates/layout-kawaii.html`
- Modify: `server/static/js/app.js`
- Test: `scripts/test-private-registry-ui.py`
- Test: `scripts/test-home-auth-session-runtime.py`

**Step 1: Write the failing test**

Before refactoring, add or tighten assertions in the existing UI tests so they lock down:
- home page auth panel behavior
- console navigation labels
- share page audience labels
- login/logout runtime behavior

**Step 2: Run test to verify the baseline**

Run:

```bash
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-home-auth-session-runtime.py
```

Expected: `OK`, establishing a safe refactor baseline.

**Step 3: Write minimal implementation**

Refactor without changing behavior:
- move home-page data shaping out of `server/app.py` into `server/ui/home.py`
- move console-specific formatting into `server/ui/console.py`
- extract the biggest `index-kawaii.html` sections into partial templates
- move auth-session JavaScript out of inline templates into `server/static/js/auth-session.js`
- leave `server/static/js/app.js` as the shared shell entrypoint, not the dumping ground

**Step 4: Run tests to verify it passes**

Run:

```bash
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-home-auth-session-runtime.py
```

Expected: both scripts still print `OK`.

**Step 5: Commit**

```bash
git add server/ui/__init__.py server/ui/home.py server/ui/console.py server/templates/partials/home-auth-panel.html server/templates/partials/home-hero.html server/templates/partials/home-console.html server/static/js/auth-session.js server/app.py server/templates/index-kawaii.html server/templates/layout-kawaii.html server/static/js/app.js
git commit -m "refactor: split homepage and console presentation logic"
```

### Task 5: Turn the New Guardrails into CI Gates

**Files:**
- Modify: `scripts/check-all.sh`
- Modify: `.github/workflows/validate.yml`
- Modify: `docs/project-closeout.md`
- Modify: `README.md`
- Test: `scripts/check-all.sh`

**Step 1: Write the failing test**

Make the verification path intentionally incomplete first by adding the new scripts from Tasks 1-3 to the expected maintained matrix in `docs/project-closeout.md`, then confirm CI locally does not yet run all of them.

**Step 2: Run verification to show the gap**

Run:

```bash
rg "test-home-auth-session-runtime|test-settings-hardening|test-private-registry-access-api" scripts/check-all.sh .github/workflows/validate.yml docs/project-closeout.md
```

Expected: at least one of the new checks is missing from `scripts/check-all.sh` or the documented closeout matrix.

**Step 3: Write minimal implementation**

Update the project verification contract:
- add the new hardening scripts to `scripts/check-all.sh`
- ensure `.github/workflows/validate.yml` still runs the authoritative path that includes them
- update `docs/project-closeout.md` and `README.md` so local verification instructions match CI truth

**Step 4: Run tests to verify it passes**

Run:

```bash
uv run python3 scripts/test-home-auth-session-runtime.py
uv run python3 scripts/test-settings-hardening.py
uv run python3 scripts/test-private-registry-access-api.py
scripts/check-all.sh
```

Expected: the targeted scripts print `OK`, and `scripts/check-all.sh` completes successfully.

**Step 5: Commit**

```bash
git add scripts/check-all.sh .github/workflows/validate.yml docs/project-closeout.md README.md
git commit -m "chore: enforce security hardening checks in ci"
```

### Task 6: Final 90+ Verification Pass

**Files:**
- Modify: `docs/project-closeout.md`
- Modify: `README.md`
- Test: `scripts/test-project-complete-state.py`
- Test: `scripts/test-private-registry-ui.py`
- Test: `scripts/test-private-first-cutover-schema.py`
- Test: `scripts/test-private-registry-access-api.py`
- Test: `scripts/test-home-auth-session-runtime.py`
- Test: `scripts/test-settings-hardening.py`
- Test: `scripts/check-all.sh`

**Step 1: Run the focused regression matrix**

Run:

```bash
uv run python3 scripts/test-project-complete-state.py
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-private-first-cutover-schema.py
uv run python3 scripts/test-private-registry-access-api.py
uv run python3 scripts/test-home-auth-session-runtime.py
uv run python3 scripts/test-settings-hardening.py
```

Expected: every script prints `OK`.

**Step 2: Run the full project gate**

Run:

```bash
scripts/check-all.sh
```

Expected: `OK: full registry check passed`.

**Step 3: Refresh project truth**

Update `docs/project-closeout.md` and `README.md` so they describe:
- hardened browser sessions
- explicit production auth configuration
- hashed personal token storage
- the maintained regression matrix that now enforces all of the above

**Step 4: Re-run the final smoke checks**

Run:

```bash
uv run python3 scripts/test-project-complete-state.py
scripts/check-all.sh
```

Expected: both commands succeed without new diffs or skipped required checks.

**Step 5: Commit**

```bash
git add docs/project-closeout.md README.md
git commit -m "docs: refresh closeout after 90 plus hardening pass"
```
