# Hosted Auth And Operator Console Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden the hosted registry so `/registry/*` can be protected with bearer-token access, while adding the smallest usable operator console and API/CLI list surfaces for submissions, reviews, and jobs.

**Architecture:** Keep the current single-process hosted app and SQLite-first model. Replace the unauthenticated static `/registry` mount with an auth-aware read-only distribution surface that can require a registry bearer token without changing immutable artifact semantics. In the same slice, add minimal list endpoints plus simple HTML queue views so maintainers can inspect submissions, reviews, and jobs without querying SQLite directly. Extend `registryctl.py` with matching read-only list/get commands so the control plane becomes operationally useful from both browser and CLI.

**Tech Stack:** Python 3.11+, FastAPI/Starlette, existing SQLAlchemy models and auth helpers, existing hosted distribution tests, Jinja2 templates, `httpx`-based CLI, stdlib `tempfile` and script-style regression tests.

**Execution Notes:** Before implementation, create a dedicated worktree/branch such as `codex/hosted-auth-operator-console` with @superpowers:using-git-worktrees. Follow @superpowers:test-driven-development for each behavior change, and use @superpowers:verification-before-completion before any completion claim or merge.

---

### Task 1: Add failing `/registry` auth coverage

**Files:**
- Create: `scripts/test-hosted-registry-auth.py`
- Modify: `scripts/test-hosted-api.py`
- Reference: `docs/ai/hosted-registry.md`
- Reference: `server/app.py`
- Reference: `server/auth.py`

**Step 1: Write the failing tests**

Create `scripts/test-hosted-registry-auth.py` with focused scenarios that:

- create a temp artifact root and populate it via `sync_catalog_artifacts(ROOT, artifact_root)`
- set `INFINITAS_SERVER_ARTIFACT_PATH`
- set a new env var for registry auth, recommended:
  - `INFINITAS_REGISTRY_READ_TOKENS='["registry-reader-token"]'`
- build the app with `create_app()`
- assert:
  - `GET /registry/ai-index.json` without `Authorization` returns `401`
  - `GET /registry/ai-index.json` with `Authorization: Bearer wrong-token` returns `401`
  - `GET /registry/ai-index.json` with `Authorization: Bearer registry-reader-token` returns `200`
  - the same token can access a manifest path like `/registry/skills/lvxiaoer/operate-infinitas-skill/0.1.1/manifest.json`

Also extend `scripts/test-hosted-api.py` so it explicitly proves the control-plane API still behaves independently:

- `/healthz` remains public
- `/api/v1/me` still uses hosted user tokens
- `/registry/*` requires the dedicated registry reader token when configured

Use a small assertion shape like:

```python
response = client.get('/registry/ai-index.json')
if response.status_code != 401:
    fail(f'expected unauthenticated registry request to return 401, got {response.status_code}')
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
export PYTHONPATH=$PWD
python scripts/test-hosted-registry-auth.py
python scripts/test-hosted-api.py
```

Expected: FAIL because `/registry` is currently a public `StaticFiles` mount.

**Step 3: Commit**

```bash
git add scripts/test-hosted-registry-auth.py scripts/test-hosted-api.py
git commit -m "test: add hosted registry auth coverage"
```

### Task 2: Implement auth-aware hosted distribution serving

**Files:**
- Modify: `server/app.py`
- Modify: `server/auth.py`
- Modify: `server/settings.py`
- Modify: `scripts/test-hosted-registry-auth.py`
- Modify: `scripts/test-hosted-api.py`

**Step 1: Add minimal registry-read auth settings**

Extend `server/settings.py` with a normalized read-only registry auth config, for example:

- `registry_read_tokens: list[str]`

Recommended env contract:

- `INFINITAS_REGISTRY_READ_TOKENS` contains a JSON array of raw bearer tokens
- empty/missing value means `/registry/*` stays public for local/dev compatibility

Keep this intentionally small; do not add per-user registry scopes yet.

**Step 2: Add auth helpers**

Extend `server/auth.py` with a small dependency/helper such as:

```python
def require_registry_reader(authorization: str | None = Header(default=None)) -> None:
    ...
```

Behavior:

- if no registry tokens are configured, allow access
- if tokens are configured:
  - missing bearer token => `401`
  - unknown token => `401`
  - known token => allow

Do not mix registry reader tokens into the database-backed `User` model in this slice.

**Step 3: Replace the public static mount**

Refactor `server/app.py` so `/registry/*` is no longer a blind public `StaticFiles` mount.

Recommended shape:

- add explicit FastAPI routes for:
  - `/registry/ai-index.json`
  - `/registry/distributions.json`
  - `/registry/compatibility.json`
  - `/registry/skills/{publisher}/{skill}/{version}/{filename}`
  - `/registry/provenance/{filename}`
- each route:
  - depends on `require_registry_reader`
  - serves files from `settings.artifact_path`
  - rejects path traversal
  - returns `404` when the requested file is absent

Use `FileResponse` or `Response` with bytes. Keep the implementation read-only and path-safe.

**Step 4: Run focused tests to verify they pass**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
export PYTHONPATH=$PWD
python scripts/test-hosted-registry-auth.py
python scripts/test-hosted-api.py
```

Expected: PASS.

**Step 5: Re-run adjacent hosted distribution checks**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
export PYTHONPATH=$PWD
python scripts/test-hosted-artifact-layout.py
python scripts/test-hosted-registry-source.py
python scripts/test-hosted-registry-install.py
python scripts/test-hosted-registry-e2e.py
```

Expected: PASS after updating the e2e fixture to send the configured registry token when needed.

**Step 6: Commit**

```bash
git add server/app.py server/auth.py server/settings.py scripts/test-hosted-registry-auth.py scripts/test-hosted-api.py scripts/test-hosted-registry-e2e.py
git commit -m "feat: protect hosted registry artifacts"
```

### Task 3: Add failing operator list API coverage

**Files:**
- Create: `scripts/test-hosted-operator-console.py`
- Modify: `server/api/jobs.py`
- Modify: `server/api/submissions.py`
- Modify: `server/api/reviews.py`
- Modify: `scripts/registryctl.py`
- Reference: `scripts/test-submission-review-api.py`

**Step 1: Write the failing tests**

Create `scripts/test-hosted-operator-console.py` that seeds a temp DB through the existing submission/review flow, then asserts these new list routes exist:

- `GET /api/v1/submissions`
- `GET /api/v1/reviews`
- `GET /api/v1/jobs`

Expected payload shape can stay compact:

```json
{
  "items": [...],
  "total": 3
}
```

Cover at least:

- contributor can list their own submissions
- maintainer can list all submissions/reviews/jobs
- list payloads include IDs, statuses, timestamps, and enough references to navigate to details

Also extend `scripts/registryctl.py` coverage:

- `registryctl submissions list`
- `registryctl reviews list`
- `registryctl jobs list`

The CLI tests can stay at the “help and JSON contract” level first if that is enough to drive the implementation.

**Step 2: Run the tests to verify they fail**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
export PYTHONPATH=$PWD
python scripts/test-hosted-operator-console.py
```

Expected: FAIL because list endpoints and list CLI subcommands do not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-hosted-operator-console.py
git commit -m "test: add hosted operator console coverage"
```

### Task 4: Implement minimal operator list APIs and CLI

**Files:**
- Modify: `server/api/submissions.py`
- Modify: `server/api/reviews.py`
- Modify: `server/api/jobs.py`
- Modify: `server/schemas.py`
- Modify: `scripts/registryctl.py`
- Modify: `scripts/test-hosted-operator-console.py`

**Step 1: Add list endpoints**

Implement:

- `GET /api/v1/submissions`
- `GET /api/v1/reviews`
- `GET /api/v1/jobs`

Recommended minimal query support:

- `?limit=<int>` with a safe default like `20`
- optional status filter only if trivial; otherwise defer

Role behavior:

- contributor:
  - may list submissions they created
  - may see only reviews/jobs tied to their own submissions if this is easy to express
- maintainer:
  - may list everything

Keep sorting simple and explicit:

- newest first by `updated_at desc, id desc`

**Step 2: Extend schemas only as needed**

If existing `schemas.py` lacks list response wrappers, add small response models for:

- `SubmissionListResponse`
- `ReviewListResponse`
- `JobListResponse`

Do not redesign the full schema tree.

**Step 3: Extend `registryctl.py`**

Add subcommands:

- `submissions list`
- `reviews list`
- `jobs list`
- optionally `jobs get <id>` only if needed for symmetry

Keep output JSON-first and aligned with the API payloads.

**Step 4: Run focused tests to verify they pass**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
export PYTHONPATH=$PWD
python scripts/test-hosted-operator-console.py
python scripts/test-submission-review-api.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add server/api/submissions.py server/api/reviews.py server/api/jobs.py server/schemas.py scripts/registryctl.py scripts/test-hosted-operator-console.py
git commit -m "feat: add hosted operator list APIs"
```

### Task 5: Add minimal HTML operator console views

**Files:**
- Modify: `server/app.py`
- Modify: `server/templates/index.html`
- Create: `server/templates/submissions.html`
- Create: `server/templates/reviews.html`
- Create: `server/templates/jobs.html`
- Modify: `scripts/test-hosted-api.py`
- Modify: `scripts/test-hosted-operator-console.py`

**Step 1: Write failing UI assertions**

Extend hosted app smoke coverage so maintainers can visit:

- `GET /submissions`
- `GET /reviews`
- `GET /jobs`

Behavior:

- these pages require a maintainer bearer token
- each page renders a small HTML table or list of current items
- the index page should link to these three operator views

Assertions may stay simple and text-based:

```python
response = client.get('/jobs', headers=maintainer_headers)
if response.status_code != 200 or 'Jobs' not in response.text:
    fail(...)
```

**Step 2: Implement the minimal HTML console**

Use server-rendered templates only:

- no JS app
- no pagination beyond simple `limit`
- enough columns to inspect ID, status, actor, skill/submission reference, and timestamps

Recommended routes:

- `GET /submissions`
- `GET /reviews`
- `GET /jobs`

Each route should:

- require a maintainer token
- query the latest rows
- render them through the new templates

**Step 3: Run focused tests to verify they pass**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
export PYTHONPATH=$PWD
python scripts/test-hosted-api.py
python scripts/test-hosted-operator-console.py
```

Expected: PASS.

**Step 4: Commit**

```bash
git add server/app.py server/templates/index.html server/templates/submissions.html server/templates/reviews.html server/templates/jobs.html scripts/test-hosted-api.py scripts/test-hosted-operator-console.py
git commit -m "feat: add hosted operator console pages"
```

### Task 6: Update docs and run final verification

**Files:**
- Modify: `docs/ai/hosted-registry.md`
- Modify: `docs/ai/server-api.md`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`

**Step 1: Update docs**

Document:

- new registry auth env contract:
  - `INFINITAS_REGISTRY_READ_TOKENS`
- that `/registry/*` can be public in dev or bearer-protected in hosted deployments
- that operators now have minimal console pages:
  - `/submissions`
  - `/reviews`
  - `/jobs`
- matching `registryctl.py` list subcommands

Keep the docs honest about what is still missing:

- no per-user registry scopes yet
- no polished workflow UI yet
- HTML console is intentionally minimal

**Step 2: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
export PYTHONPATH=$PWD
python scripts/test-hosted-registry-auth.py
python scripts/test-hosted-api.py
python scripts/test-hosted-artifact-layout.py
python scripts/test-hosted-registry-source.py
python scripts/test-hosted-registry-install.py
python scripts/test-hosted-registry-e2e.py
python scripts/test-submission-review-api.py
python scripts/test-hosted-operator-console.py
python scripts/test-worker-publish.py
python scripts/test-hosted-publish-hooks.py
git diff --check
git status --short
```

Expected: all checks pass and only intentional tracked changes remain.

If `.state/` appears, clean it before the final `git status --short`.

**Step 3: Commit**

```bash
git add docs/ai/hosted-registry.md docs/ai/server-api.md docs/ops/server-deployment.md README.md
git commit -m "docs: describe hosted auth and operator console"
```
