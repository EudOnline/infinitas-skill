# Server-Hosted Private Skill Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn `infinitas-skill` into a server-hosted private registry where the server owns the writable source of truth, clients install from hosted immutable artifacts, contributors submit through Web/CLI APIs, and GitHub becomes a downstream mirror.

**Architecture:** Implement the hosted registry in three layers. First, extend the existing registry/install toolchain to understand a remote `http` registry and hosted artifact URLs so consumers stop cloning the whole repo. Second, add a small Python control plane with a database, authenticated API, job queue, and worker that drives the current review/publish scripts against a server-owned repository. Third, add mirroring, backup, and deployment docs so the hosted platform is operationally safe.

**Tech Stack:** Existing Bash and Python 3.11 scripts, new `pyproject.toml` managed with `uv`, FastAPI for API + HTML control pages, SQLAlchemy or SQLModel with SQLite-first / PostgreSQL-ready schema, Jinja2 for lightweight server-rendered pages, existing release/attestation helpers, filesystem-backed artifact storage, and GitHub as a mirror remote.

---

## Preconditions

- Create a dedicated worktree before implementation.
- Keep the current repository layout as the content and release source model.
- Do not weaken the current `immutable-only` install policy.
- Treat GitHub as a write-only mirror target from the hosted system.
- Keep phase 1 deployable on one small server.

## Scope decisions

- Add an `http` registry source type instead of replacing the current `git` and `local` sources.
- Reuse current `catalog/` outputs as the canonical hosted distribution contract.
- Add a new `server/` Python package rather than rewriting the current `scripts/` folder into a framework app.
- Start with filesystem-backed artifacts and SQLite for the smallest deployable version, but keep abstractions clean so PostgreSQL and object storage can be added later.
- Introduce an API-backed CLI entrypoint for hosted operations while preserving current local scripts for repo operators.

## Non-goals

- Do not implement a public marketplace.
- Do not replace signed release tags, provenance, or compatibility evidence.
- Do not support bidirectional sync from GitHub.
- Do not build real-time collaborative editing.
- Do not auto-publish to ClawHub in the first pass.

### Task 1: Add hosted registry source contracts and validation

**Files:**
- Modify: `schemas/registry-sources.schema.json`
- Modify: `scripts/registry_source_lib.py`
- Modify: `scripts/check-registry-sources.py`
- Create: `scripts/test-hosted-registry-source.py`
- Create: `docs/ai/hosted-registry.md`
- Modify: `docs/multi-registry.md`
- Modify: `README.md`

**Step 1: Write the failing test**

Create `scripts/test-hosted-registry-source.py` with scenarios that:

- validate a registry config containing `kind: "http"`
- require a `base_url`
- reject missing HTTPS hosts for `private`, `trusted`, or `public` remote registries
- reject invalid auth modes
- resolve the hosted registry identity without requiring a local clone

Use a payload shaped like:

```json
{
  "default_registry": "hosted",
  "registries": [
    {
      "name": "hosted",
      "kind": "http",
      "base_url": "https://skills.example.com/registry",
      "enabled": true,
      "priority": 100,
      "trust": "private",
      "auth": {
        "mode": "token",
        "env": "INFINITAS_REGISTRY_TOKEN"
      }
    }
  ]
}
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-registry-source.py
```

Expected: FAIL because `http` registry sources are not defined yet.

**Step 3: Extend the schema**

Update `schemas/registry-sources.schema.json` so registry entries support:

- `kind: "http"`
- `base_url`
- `auth.mode`
- `auth.env`
- optional catalog path overrides only if the defaults must differ

Keep current `git` and `local` behavior unchanged.

**Step 4: Extend registry resolution helpers**

Update `scripts/registry_source_lib.py` so:

- `kind: http` resolves to a URL, not a local path
- validation enforces HTTPS for non-local hosted registries
- registry identity returns hosted metadata without Git commit expectations
- current `git` / `local` logic keeps working

**Step 5: Document the hosted registry contract**

Document:

- required hosted endpoints
- token auth expectations
- trust and update semantics for hosted registries
- why hosted install still uses immutable manifests and provenance

**Step 6: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-registry-source.py
```

Expected: PASS.

**Step 7: Commit**

```bash
git add schemas/registry-sources.schema.json scripts/registry_source_lib.py scripts/check-registry-sources.py scripts/test-hosted-registry-source.py docs/ai/hosted-registry.md docs/multi-registry.md README.md
git commit -m "feat: add hosted http registry source contract"
```

### Task 2: Teach discovery and install flows to pull from hosted immutable artifacts

**Files:**
- Create: `scripts/http_registry_lib.py`
- Modify: `scripts/resolve-skill-source.py`
- Modify: `scripts/pull-skill.sh`
- Modify: `scripts/install-by-name.sh`
- Modify: `scripts/check-skill-update.sh`
- Modify: `scripts/upgrade-skill.sh`
- Modify: `scripts/resolve-install-plan.py`
- Create: `scripts/test-hosted-registry-install.py`
- Modify: `catalog/ai-index.json` contract docs in `docs/ai/discovery.md`
- Modify: `docs/ai/pull.md`

**Step 1: Write the failing install test**

Create `scripts/test-hosted-registry-install.py` that:

- spins up a temp HTTP server serving fixture `ai-index.json`, `distributions.json`, manifest, bundle, and provenance
- configures a temp `registry-sources.json` with `kind: http`
- runs `scripts/install-by-name.sh operate-infinitas-skill <target-dir>`
- asserts the installed target contains the expected files plus install manifest metadata recording the hosted source

Also assert that the installer fails if:

- the manifest sha256 does not match
- required provenance is missing
- the hosted version is not declared installable

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-registry-install.py
```

Expected: FAIL because the current install flow assumes local registry roots.

**Step 3: Add hosted fetch helpers**

Create `scripts/http_registry_lib.py` with helpers shaped like:

```python
def fetch_json(base_url: str, path: str, token_env: str | None = None) -> dict:
    ...


def fetch_binary(base_url: str, path: str, output: Path, token_env: str | None = None) -> Path:
    ...
```

Implement:

- `Authorization: Bearer` header support via env-configured token
- safe temp-file downloads
- explicit error messages for 401, 403, 404, and hash mismatches

**Step 4: Make discovery and install remote-aware**

Update the resolver and installer stack so:

- `resolve-skill-source.py` can read hosted `ai-index.json` / `distributions.json`
- `pull-skill.sh` downloads manifest + bundle + provenance for hosted registries
- `install-by-name.sh`, `check-skill-update.sh`, and `upgrade-skill.sh` preserve source identity for `http` registries
- install manifests record the hosted source URL and resolved version

**Step 5: Update protocol docs**

Document that hosted install:

- does not clone the registry
- still uses immutable artifact verification
- still refuses mutable source installs

**Step 6: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-registry-install.py
```

Expected: PASS.

**Step 7: Run adjacent regression checks**

Run:

```bash
python3 scripts/test-distribution-install.py
python3 scripts/test-discovery-index.py
python3 scripts/test-install-by-name.py
python3 scripts/test-ai-pull.py
```

Expected: PASS.

**Step 8: Commit**

```bash
git add scripts/http_registry_lib.py scripts/resolve-skill-source.py scripts/pull-skill.sh scripts/install-by-name.sh scripts/check-skill-update.sh scripts/upgrade-skill.sh scripts/resolve-install-plan.py scripts/test-hosted-registry-install.py docs/ai/discovery.md docs/ai/pull.md
git commit -m "feat: install skills from hosted immutable registry artifacts"
```

### Task 3: Scaffold the hosted control plane and persistence layer

**Files:**
- Create: `pyproject.toml`
- Create: `server/__init__.py`
- Create: `server/app.py`
- Create: `server/settings.py`
- Create: `server/db.py`
- Create: `server/models.py`
- Create: `server/auth.py`
- Create: `server/templates/layout.html`
- Create: `server/templates/index.html`
- Create: `scripts/test-hosted-api.py`
- Modify: `README.md`

**Step 1: Write the failing API smoke test**

Create `scripts/test-hosted-api.py` with checks that:

- import the ASGI app from `server.app`
- hit `/healthz`
- hit `/login` or a lightweight auth bootstrap route
- hit `/api/v1/me` with a fixture token

Shape the test like:

```python
client = TestClient(app)
response = client.get('/healthz')
assert response.status_code == 200
assert response.json()['ok'] is True
```

**Step 2: Run the test to verify it fails**

Run:

```bash
uv run python scripts/test-hosted-api.py
```

Expected: FAIL because the app package and dependencies do not exist yet.

**Step 3: Add project packaging**

Create `pyproject.toml` with:

- `fastapi`
- `uvicorn`
- `sqlalchemy` or `sqlmodel`
- `jinja2`
- `httpx`

Keep the initial dependency set small. Do not add a frontend framework.

**Step 4: Implement the minimal app skeleton**

Create:

- `server/settings.py` for env-configured paths and secrets
- `server/db.py` for engine/session setup
- `server/models.py` for `users`, `jobs`, and a placeholder `submissions` table
- `server/auth.py` for token-based auth
- `server/app.py` for:
  - `/healthz`
  - `/`
  - `/api/v1/me`

**Step 5: Re-run the API smoke test**

Run:

```bash
uv run python scripts/test-hosted-api.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add pyproject.toml server/__init__.py server/app.py server/settings.py server/db.py server/models.py server/auth.py server/templates/layout.html server/templates/index.html scripts/test-hosted-api.py README.md
git commit -m "feat: scaffold hosted registry control plane"
```

### Task 4: Add submissions, reviews, and an API-backed CLI contract

**Files:**
- Create: `server/api/submissions.py`
- Create: `server/api/reviews.py`
- Create: `server/api/skills.py`
- Create: `server/schemas.py`
- Create: `scripts/registryctl.py`
- Create: `scripts/test-submission-review-api.py`
- Modify: `server/app.py`
- Modify: `server/models.py`
- Modify: `README.md`
- Create: `docs/ai/server-api.md`

**Step 1: Write the failing submission/review test**

Create `scripts/test-submission-review-api.py` that:

- creates a contributor token and a maintainer token
- POSTs a submission with a minimal skill payload
- transitions it through:
  - draft
  - validation requested
  - review requested
- approves it as maintainer
- asserts unauthorized contributors cannot approve

Also add a CLI smoke check:

```bash
uv run python scripts/registryctl.py submissions create --help
```

**Step 2: Run the test to verify it fails**

Run:

```bash
uv run python scripts/test-submission-review-api.py
```

Expected: FAIL because submissions, reviews, and the CLI do not exist yet.

**Step 3: Add submission/review models and routes**

Extend `server/models.py` and create route modules for:

- `POST /api/v1/submissions`
- `GET /api/v1/submissions/<id>`
- `POST /api/v1/submissions/<id>/request-review`
- `POST /api/v1/reviews/<id>/approve`
- `POST /api/v1/reviews/<id>/reject`

Record:

- actor id
- role
- timestamps
- status transitions
- payload summary

**Step 4: Add the CLI wrapper**

Create `scripts/registryctl.py` with subcommands shaped like:

```bash
uv run python scripts/registryctl.py submissions create
uv run python scripts/registryctl.py submissions request-review <id>
uv run python scripts/registryctl.py reviews approve <id>
uv run python scripts/registryctl.py releases publish <skill>
```

The CLI should call the hosted API, not mutate the repository directly.

**Step 5: Re-run the focused test**

Run:

```bash
uv run python scripts/test-submission-review-api.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/api/submissions.py server/api/reviews.py server/api/skills.py server/schemas.py scripts/registryctl.py scripts/test-submission-review-api.py server/app.py server/models.py README.md docs/ai/server-api.md
git commit -m "feat: add hosted submission and review control plane"
```

### Task 5: Add worker-executed repository mutation and signed publish jobs

**Files:**
- Create: `server/jobs.py`
- Create: `server/worker.py`
- Create: `server/repo_ops.py`
- Create: `server/artifact_ops.py`
- Create: `scripts/test-worker-publish.py`
- Modify: `server/app.py`
- Modify: `server/models.py`
- Modify: `docs/ai/publish.md`
- Modify: `docs/release-checklist.md`

**Step 1: Write the failing publish-job test**

Create `scripts/test-worker-publish.py` that:

- creates a temp server repo copied from the current repo
- seeds a draft submission for a fixture skill
- enqueues:
  - validate
  - promote
  - publish
- runs one worker loop
- asserts:
  - the skill lands in `skills/active/`
  - release outputs appear in `catalog/distributions/` and `catalog/provenance/`
  - the job log records each executed script

**Step 2: Run the test to verify it fails**

Run:

```bash
uv run python scripts/test-worker-publish.py
```

Expected: FAIL because no worker/job runner exists yet.

**Step 3: Implement repository and artifact operations**

Create:

- `server/repo_ops.py` for locked checkout mutation
- `server/artifact_ops.py` for syncing generated catalogs and bundles to the hosted artifact directory
- `server/jobs.py` for queue state transitions
- `server/worker.py` for sequential job execution

The worker should call existing scripts rather than reimplementing their core logic.

**Step 4: Add publish job routes**

Expose routes for:

- queueing validation jobs
- queueing review materialization jobs
- queueing publish jobs
- viewing job logs

Enforce that only maintainers may queue publish jobs.

**Step 5: Re-run the focused test**

Run:

```bash
uv run python scripts/test-worker-publish.py
```

Expected: PASS.

**Step 6: Run adjacent release regressions**

Run:

```bash
python3 scripts/test-release-invariants.py
python3 scripts/test-record-verified-support.py
python3 scripts/test-review-governance.py
```

Expected: PASS.

**Step 7: Commit**

```bash
git add server/jobs.py server/worker.py server/repo_ops.py server/artifact_ops.py scripts/test-worker-publish.py server/app.py server/models.py docs/ai/publish.md docs/release-checklist.md
git commit -m "feat: add hosted worker and publish job runner"
```

### Task 6: Add GitHub mirroring, backup hooks, and deployment docs

**Files:**
- Create: `scripts/mirror-registry.sh`
- Create: `scripts/test-mirror-registry.py`
- Create: `docs/ops/server-deployment.md`
- Create: `docs/ops/server-backup-and-restore.md`
- Modify: `README.md`
- Modify: `docs/trust-model.md`

**Step 1: Write the failing mirror/ops test**

Create `scripts/test-mirror-registry.py` with checks that:

- simulate a server repo with a configured mirror remote
- run the mirror helper in dry-run mode
- assert the script refuses:
  - missing remotes
  - dirty trees
  - reverse-sync flags

Also add doc assertions that:

- deployment docs mention one-way mirroring
- backup docs mention repo + db + artifacts

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-mirror-registry.py
```

Expected: FAIL because the mirror helper and ops docs do not exist yet.

**Step 3: Implement mirror helper**

Create `scripts/mirror-registry.sh` so it:

- verifies a clean source-of-truth repo
- verifies the target remote is explicit
- pushes the desired refs outward only
- supports dry-run output for operators

Do not allow it to fetch and merge GitHub back into the source-of-truth repo.

**Step 4: Write the deployment and restore runbooks**

Create `docs/ops/server-deployment.md` covering:

- reverse proxy
- app
- worker
- repo path
- artifact path
- secrets
- service startup

Create `docs/ops/server-backup-and-restore.md` covering:

- repo snapshots
- DB backups
- artifact backups
- recovery sequence

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-mirror-registry.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/mirror-registry.sh scripts/test-mirror-registry.py docs/ops/server-deployment.md docs/ops/server-backup-and-restore.md README.md docs/trust-model.md
git commit -m "docs: add hosted registry ops and mirror workflow"
```

### Task 7: Validate the hosted registry MVP end-to-end

**Files:**
- Modify: `scripts/check-all.sh`
- Create: `scripts/test-hosted-registry-e2e.py`
- Modify: `README.md`

**Step 1: Write the failing end-to-end test**

Create `scripts/test-hosted-registry-e2e.py` that:

- boots a temp hosted registry app
- seeds a maintainer and a contributor
- submits a fixture skill
- requests review
- approves and publishes as maintainer
- serves the generated artifacts over HTTP
- installs the released skill into a temp runtime directory through the hosted `http` registry source

Assert:

- the installed runtime skill matches the released version
- the install manifest records the hosted registry identity
- `doctor-signing.py` still verifies the release provenance

**Step 2: Run the test to verify it fails**

Run:

```bash
uv run python scripts/test-hosted-registry-e2e.py
```

Expected: FAIL until the hosted stack is fully wired together.

**Step 3: Wire the test into the main verification flow**

Update `scripts/check-all.sh` so the hosted end-to-end test can be run:

- by default in full environments
- or behind an env gate if startup time must stay bounded

**Step 4: Re-run the end-to-end test**

Run:

```bash
uv run python scripts/test-hosted-registry-e2e.py
```

Expected: PASS.

**Step 5: Run fresh full verification before claiming completion**

Run:

```bash
./scripts/check-all.sh
python3 scripts/doctor-signing.py operate-infinitas-skill --identity lvxiaoer --provenance catalog/provenance/operate-infinitas-skill-0.1.1.json
```

Expected: PASS, with hosted registry coverage included.

**Step 6: Commit**

```bash
git add scripts/check-all.sh scripts/test-hosted-registry-e2e.py README.md
git commit -m "test: cover hosted registry workflow end to end"
```

## Execution handoff

Plan complete and saved to:

- `docs/plans/2026-03-13-server-hosted-registry-design.md`
- `docs/plans/2026-03-13-server-hosted-registry-implementation.md`

Two execution options:

**1. Subagent-Driven (this session)** - implement phase-by-phase in this session, review between tasks.

**2. Parallel Session (separate)** - open a new session in a fresh worktree and execute this plan with `superpowers:executing-plans`.

Recommended start: implement **Task 1 + Task 2 first** so hosted install works before the full control plane lands.
