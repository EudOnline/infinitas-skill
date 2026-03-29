# Private-First Registry Incremental Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evolve the hosted control plane into a private-first registry by adding release, exposure, access, and audience-aware discovery primitives without breaking the current submission/review/job workflow during migration.

**Architecture:** Keep the current hosted UI, `/api/v1/submissions`, `/api/v1/reviews`, `/api/v1/jobs`, and `/registry/*` surfaces operational while introducing an additive module layer under `server/modules/`. New private-first tables and services become the durable model for releases, sharing, and access control; legacy routes and worker jobs bridge into that model until the new path is proven end-to-end. Do not delete the old workflow in this plan. Replace it only after the new domain has real traffic, real artifacts, and passing compatibility checks.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, Jinja2, httpx, SQLite for local/dev, filesystem-backed immutable artifacts, existing `scripts/publish-skill.sh` and `scripts/pull-skill.sh` wrappers, `uv run`, targeted Python smoke tests.

**Supersedes:** `docs/plans/2026-03-28-private-first-registry-rearchitecture-implementation-plan.md`. The older draft assumed an all-at-once replacement of the hosted workflow; this plan preserves the current hosted console and adds the private-first model incrementally.

---

## Preconditions

- Create a dedicated worktree before implementation with `@superpowers:using-git-worktrees`.
- Use `@superpowers:test-driven-development` inside each task: write the failing test first, then make it pass with the smallest durable change.
- Use `@superpowers:verification-before-completion` before claiming any task is done.
- Keep the current `/submissions`, `/reviews`, `/jobs`, and `/registry/*` routes working until the compatibility bridge is complete.
- Treat `User`, `Submission`, `Review`, and `Job` as compatibility tables during this plan, not the final product model.
- Reuse the existing immutable artifact pipeline where possible; do not invent a second bundle format.

## Scope Rules

- `token-visible` must not become a first-class database enum.
- Public exposure must require a blocking review case.
- Private release creation must not require review by default.
- Existing bearer tokens and browser cookie sessions must continue to work during migration.
- Legacy publish flow must start writing into the new release graph before any UI cutover.
- This plan is API-first. UI expansion happens only after the new domain passes API and worker verification.

## Explicit Non-Goals

- Do not delete `server/api/submissions.py`, `server/api/reviews.py`, `server/api/skills.py`, or `server/worker.py` in this plan.
- Do not replace the current kawaii operator UI with a brand-new product surface immediately.
- Do not require PostgreSQL-only behavior for the first implementation slice; keep SQLite dev mode working.
- Do not redesign the immutable artifact format.
- Do not migrate every CLI command at once; start with the hosted registry control plane and discovery/install entrypoints only.

### Task 1: Add migration discipline and shared private-first scaffolding

**Files:**
- Modify: `pyproject.toml`
- Modify: `server/db.py`
- Modify: `scripts/run-hosted-worker.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/20260329_0001_bootstrap_alembic.py`
- Create: `server/modules/__init__.py`
- Create: `server/modules/shared/__init__.py`
- Create: `server/modules/shared/metadata.py`
- Create: `server/modules/shared/enums.py`
- Create: `server/modules/shared/json.py`
- Create: `scripts/test-private-registry-bootstrap.py`

**Step 1: Write the failing bootstrap test**

Create `scripts/test-private-registry-bootstrap.py` that:

- creates a temporary SQLite database
- runs `uv run alembic upgrade head`
- imports `server.app.create_app`
- calls `ensure_database_ready()`
- verifies the database contains `users`, `submissions`, `reviews`, `jobs`, and `alembic_version`
- verifies `GET /healthz` still returns `200`

Start with assertions shaped like:

```python
assert table_exists(db_path, 'users')
assert table_exists(db_path, 'alembic_version')
assert client.get('/healthz').status_code == 200
```

**Step 2: Run the bootstrap test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-bootstrap.py
```

Expected: FAIL because Alembic is not configured and `server/db.py` still uses `Base.metadata.create_all(...)` directly.

**Step 3: Add Alembic and the shared module layer**

Update `pyproject.toml` to include `alembic`.

Create:

- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `server/modules/shared/metadata.py`
- `server/modules/shared/enums.py`
- `server/modules/shared/json.py`

The first migration should create only the shared baseline needed for app boot and compatibility:

- `users`
- `submissions`
- `reviews`
- `jobs`
- `alembic_version`

**Step 4: Rewire database boot to run migrations first**

Update `server/db.py` and `scripts/run-hosted-worker.py` so:

- `ensure_database_ready()` runs Alembic before seeding users
- app and worker boot still seed bootstrap users
- SQLite path creation still works

**Step 5: Re-run the focused bootstrap test**

Run:

```bash
uv run python3 scripts/test-private-registry-bootstrap.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add pyproject.toml alembic.ini alembic/env.py alembic/script.py.mako alembic/versions/20260329_0001_bootstrap_alembic.py server/db.py scripts/run-hosted-worker.py server/modules/__init__.py server/modules/shared/__init__.py server/modules/shared/metadata.py server/modules/shared/enums.py server/modules/shared/json.py scripts/test-private-registry-bootstrap.py
git commit -m "feat: add private registry migration scaffold"
```

### Task 2: Introduce the additive release graph without touching legacy routes

**Files:**
- Modify: `server/models.py`
- Create: `server/modules/authoring/__init__.py`
- Create: `server/modules/authoring/models.py`
- Create: `server/modules/release/__init__.py`
- Create: `server/modules/release/models.py`
- Create: `alembic/versions/20260329_0002_release_graph.py`
- Create: `scripts/test-private-registry-release-graph.py`

**Step 1: Write the failing release-graph test**

Create `scripts/test-private-registry-release-graph.py` with scenarios that:

- create `Namespace`, `Skill`, `SkillDraft`, `SkillVersion`, `Release`, and `Artifact`
- verify a release points to exactly one immutable version
- verify artifacts are content-addressed records attached to a release
- verify legacy tables still exist after the migration

Use assertions shaped like:

```python
assert release.skill_version_id == version.id
assert artifact.release_id == release.id
assert skill.namespace_id == namespace.id
```

**Step 2: Run the release-graph test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-release-graph.py
```

Expected: FAIL because the new tables and metadata do not exist.

**Step 3: Add the core private-first tables**

Create models for:

- `Namespace`
- `Skill`
- `SkillDraft`
- `SkillVersion`
- `Release`
- `Artifact`

Keep them in module-local files and re-export them from `server/models.py` so SQLAlchemy metadata remains discoverable.

**Step 4: Add the migration**

Create `alembic/versions/20260329_0002_release_graph.py` with additive tables and indexes:

- `namespaces(slug)`
- `skills(namespace_id, slug)`
- `skill_drafts(skill_id, state)`
- `skill_versions(skill_id, version)`
- `releases(skill_version_id, state)`
- `artifacts(release_id, kind, digest)`

Do not alter legacy `submissions`, `reviews`, or `jobs` yet.

**Step 5: Re-run the focused release-graph test**

Run:

```bash
uv run python3 scripts/test-private-registry-release-graph.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/models.py server/modules/authoring/__init__.py server/modules/authoring/models.py server/modules/release/__init__.py server/modules/release/models.py alembic/versions/20260329_0002_release_graph.py scripts/test-private-registry-release-graph.py
git commit -m "feat: add private registry release graph"
```

### Task 3: Add exposure, review-case, grant, and credential tables with compatibility auth

**Files:**
- Modify: `server/models.py`
- Modify: `server/auth.py`
- Modify: `server/api/auth.py`
- Create: `server/modules/exposure/__init__.py`
- Create: `server/modules/exposure/models.py`
- Create: `server/modules/review/__init__.py`
- Create: `server/modules/review/models.py`
- Create: `server/modules/access/__init__.py`
- Create: `server/modules/access/models.py`
- Create: `server/modules/access/service.py`
- Create: `server/modules/access/authn.py`
- Create: `server/modules/access/authz.py`
- Create: `alembic/versions/20260329_0003_exposure_access_review.py`
- Create: `scripts/test-private-registry-access-policy.py`

**Step 1: Write the failing access-policy test**

Create `scripts/test-private-registry-access-policy.py` that:

- creates a private release, a grant-scoped release, and a public release
- verifies private exposure creates no review case by default
- verifies public exposure creates a blocking review case automatically
- verifies a grant credential can read only the release attached to its grant
- verifies an existing user token still authenticates current `/api/v1/*` routes

Use assertions shaped like:

```python
assert private_exposure.review_requirement == 'none'
assert public_case.status == 'pending'
assert denied.status_code == 403
assert legacy_me.status_code == 200
```

**Step 2: Run the access-policy test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-access-policy.py
```

Expected: FAIL because the new exposure, review, and credential tables do not exist.

**Step 3: Add the new additive policy tables**

Create models for:

- `Exposure`
- `ReviewCase`
- `ReviewDecision`
- `AccessGrant`
- `Credential`
- `ServicePrincipal`
- `Team`
- `TeamMembership`

Keep `User` as the human principal table during migration.

**Step 4: Rewire auth for compatibility**

Update `server/auth.py` and `server/api/auth.py` so:

- existing bearer tokens and auth cookies still authenticate `User`
- new credential records can authenticate non-user grant or service access
- `require_registry_reader_or_user(...)` can accept a scoped credential when appropriate

Do not remove the existing token fields from `users` in this task.

**Step 5: Re-run the focused access-policy test**

Run:

```bash
uv run python3 scripts/test-private-registry-access-policy.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/models.py server/auth.py server/api/auth.py server/modules/exposure/__init__.py server/modules/exposure/models.py server/modules/review/__init__.py server/modules/review/models.py server/modules/access/__init__.py server/modules/access/models.py server/modules/access/service.py server/modules/access/authn.py server/modules/access/authz.py alembic/versions/20260329_0003_exposure_access_review.py scripts/test-private-registry-access-policy.py
git commit -m "feat: add private registry exposure and access model"
```

### Task 4: Add audience-aware discovery and install resolution before any UI cutover

**Files:**
- Modify: `server/app.py`
- Modify: `server/auth.py`
- Modify: `scripts/pull-skill.sh`
- Modify: `scripts/install-by-name.sh`
- Modify: `scripts/check-skill-update.sh`
- Modify: `scripts/resolve-install-plan.py`
- Modify: `scripts/test-hosted-registry-auth.py`
- Create: `server/modules/discovery/__init__.py`
- Create: `server/modules/discovery/schemas.py`
- Create: `server/modules/discovery/service.py`
- Create: `server/modules/discovery/router.py`
- Create: `server/modules/discovery/projections.py`
- Create: `server/modules/discovery/search.py`
- Create: `scripts/test-private-registry-discovery.py`
- Create: `scripts/test-private-registry-install-resolution.py`

**Step 1: Write the failing discovery and install tests**

Create tests that verify:

- authenticated callers only see releases whose exposure or grants allow them
- anonymous callers only see public reviewed releases
- install resolution returns the exact artifact and manifest for one visible release
- legacy `/registry/*` routes still work for existing public or token-protected compatibility paths

Use assertions shaped like:

```python
assert visible_names == ['team/skill-a', 'lvxiaoer/skill-b']
assert anonymous_names == ['public/approved-skill']
assert plan['release']['id'] == release_id
```

**Step 2: Run the new tests to verify they fail**

Run:

```bash
uv run python3 scripts/test-private-registry-discovery.py
uv run python3 scripts/test-private-registry-install-resolution.py
```

Expected: FAIL because there is no audience-aware discovery layer yet.

**Step 3: Add the new discovery module**

Create:

- `server/modules/discovery/service.py`
- `server/modules/discovery/router.py`
- `server/modules/discovery/projections.py`
- `server/modules/discovery/search.py`
- `server/modules/discovery/schemas.py`

Expose additive routes such as:

- `GET /api/v1/private/catalog/me`
- `GET /api/v1/private/releases/{release_id}`
- `POST /api/v1/private/releases/{release_id}/download-token`

Keep `/registry/*` unchanged except for the auth checks needed to honor scoped credentials.

**Step 4: Update install-facing scripts incrementally**

Teach:

- `scripts/pull-skill.sh`
- `scripts/install-by-name.sh`
- `scripts/check-skill-update.sh`
- `scripts/resolve-install-plan.py`

to prefer the new authenticated discovery/install metadata when a hosted private registry base URL is in use, while preserving current immutable artifact behavior.

**Step 5: Re-run the focused discovery and install tests**

Run:

```bash
uv run python3 scripts/test-private-registry-discovery.py
uv run python3 scripts/test-private-registry-install-resolution.py
uv run python3 scripts/test-hosted-registry-auth.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/app.py server/auth.py scripts/pull-skill.sh scripts/install-by-name.sh scripts/check-skill-update.sh scripts/resolve-install-plan.py scripts/test-hosted-registry-auth.py server/modules/discovery/__init__.py server/modules/discovery/schemas.py server/modules/discovery/service.py server/modules/discovery/router.py server/modules/discovery/projections.py server/modules/discovery/search.py scripts/test-private-registry-discovery.py scripts/test-private-registry-install-resolution.py
git commit -m "feat: add audience-aware private registry discovery"
```

### Task 5: Bridge the current submission/review/publish workflow into the new release graph

**Files:**
- Modify: `server/api/submissions.py`
- Modify: `server/api/reviews.py`
- Modify: `server/api/skills.py`
- Modify: `server/jobs.py`
- Modify: `server/worker.py`
- Modify: `server/repo_ops.py`
- Create: `server/modules/legacy_bridge/__init__.py`
- Create: `server/modules/legacy_bridge/service.py`
- Create: `scripts/test-private-registry-legacy-bridge.py`

**Step 1: Write the failing compatibility-bridge test**

Create `scripts/test-private-registry-legacy-bridge.py` that:

- creates a legacy submission through the current API
- requests review and approves it
- queues publish through the existing publish endpoint
- runs the worker once
- verifies a `Skill`, `SkillVersion`, `Release`, and private default `Exposure` now exist in the new tables
- verifies the legacy submission status still reaches `published`

Use assertions shaped like:

```python
assert submission['status'] == 'published'
assert release.origin_kind == 'legacy_submission'
assert exposure.audience_type == 'private'
```

**Step 2: Run the compatibility-bridge test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-legacy-bridge.py
```

Expected: FAIL because the worker does not yet persist anything into the new release graph.

**Step 3: Add the bridge service**

Create `server/modules/legacy_bridge/service.py` that can:

- derive namespace and skill identity from a legacy submission
- create or update a private-first draft/version/release record
- register the published immutable artifacts
- create a default private exposure for the owner or maintainer scope

**Step 4: Thread the bridge through the current worker path**

Update:

- `server/api/skills.py`
- `server/jobs.py`
- `server/worker.py`
- `server/repo_ops.py`

so the existing `publish_submission` path still publishes the skill, syncs artifacts, and then records the corresponding private-first release data.

**Step 5: Re-run the compatibility-bridge test**

Run:

```bash
uv run python3 scripts/test-private-registry-legacy-bridge.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/api/submissions.py server/api/reviews.py server/api/skills.py server/jobs.py server/worker.py server/repo_ops.py server/modules/legacy_bridge/__init__.py server/modules/legacy_bridge/service.py scripts/test-private-registry-legacy-bridge.py
git commit -m "feat: bridge legacy publish flow into private registry"
```

### Task 6: Add minimal private-first operator APIs, read-only UI, and migration docs

**Files:**
- Modify: `server/app.py`
- Modify: `server/templates/layout-kawaii.html`
- Modify: `scripts/registryctl.py`
- Modify: `scripts/test-hosted-api.py`
- Modify: `README.md`
- Modify: `docs/ai/server-api.md`
- Modify: `docs/review-workflow.md`
- Create: `server/modules/authoring/schemas.py`
- Create: `server/modules/authoring/service.py`
- Create: `server/modules/authoring/router.py`
- Create: `server/modules/release/schemas.py`
- Create: `server/modules/release/service.py`
- Create: `server/modules/release/router.py`
- Create: `server/modules/exposure/schemas.py`
- Create: `server/modules/exposure/service.py`
- Create: `server/modules/exposure/router.py`
- Create: `server/modules/review/schemas.py`
- Create: `server/modules/review/service.py`
- Create: `server/modules/review/router.py`
- Create: `server/templates/releases.html`
- Create: `server/templates/exposures.html`
- Create: `docs/private-first-registry-migration.md`
- Create: `scripts/test-private-registry-ui.py`

**Step 1: Write the failing management and UI tests**

Create tests that verify:

- `GET /api/v1/private/releases` returns release records
- `POST /api/v1/private/exposures` can create a private or public exposure
- `GET /releases` and `GET /exposures` render inside the current kawaii shell for maintainers
- current `/submissions`, `/reviews`, and `/jobs` pages still render unchanged

Use assertions shaped like:

```python
assert response.status_code == 200
assert 'data-theme="kawaii"' in html
assert '/submissions' in html
assert release['qualified_name'] == 'lvxiaoer/example-skill'
```

**Step 2: Run the new tests to verify they fail**

Run:

```bash
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-hosted-api.py
```

Expected: FAIL because the new management routes and templates do not exist.

**Step 3: Add the new management routes**

Create additive routers for:

- drafts
- releases
- exposures
- review cases

Register them in `server/app.py` under a private-first API namespace and keep old API routes intact.

**Step 4: Add minimal read-only operator pages**

Create:

- `server/templates/releases.html`
- `server/templates/exposures.html`

These pages should reuse the current kawaii shell and present release/exposure counts and CLI mirrors, not a brand-new design system.

**Step 5: Update CLI and docs**

Extend `scripts/registryctl.py` with additive commands for:

- `releases list`
- `releases inspect`
- `exposures create`
- `exposures list`

Document the migration order and coexistence rules in:

- `docs/private-first-registry-migration.md`
- `docs/ai/server-api.md`
- `docs/review-workflow.md`
- `README.md`

**Step 6: Run the final verification matrix**

Run:

```bash
uv run python3 scripts/test-private-registry-bootstrap.py
uv run python3 scripts/test-private-registry-release-graph.py
uv run python3 scripts/test-private-registry-access-policy.py
uv run python3 scripts/test-private-registry-discovery.py
uv run python3 scripts/test-private-registry-install-resolution.py
uv run python3 scripts/test-private-registry-legacy-bridge.py
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-hosted-api.py
uv run python3 scripts/test-hosted-registry-auth.py
```

Expected: PASS.

**Step 7: Commit**

```bash
git add server/app.py server/templates/layout-kawaii.html scripts/registryctl.py scripts/test-hosted-api.py README.md docs/ai/server-api.md docs/review-workflow.md server/modules/authoring/schemas.py server/modules/authoring/service.py server/modules/authoring/router.py server/modules/release/schemas.py server/modules/release/service.py server/modules/release/router.py server/modules/exposure/schemas.py server/modules/exposure/service.py server/modules/exposure/router.py server/modules/review/schemas.py server/modules/review/service.py server/modules/review/router.py server/templates/releases.html server/templates/exposures.html docs/private-first-registry-migration.md scripts/test-private-registry-ui.py
git commit -m "feat: add private registry management surfaces"
```

## Exit Criteria

This plan is complete when all of the following are true:

1. The server boots through Alembic-managed migrations instead of raw `create_all(...)`.
2. Private-first release, exposure, review-case, and credential records can exist without deleting the legacy workflow.
3. Discovery and install resolution are audience-aware for the hosted private registry path.
4. The existing publish worker writes private-first release records as part of the legacy flow.
5. Maintainers can inspect releases and exposures through additive API and minimal hosted UI surfaces.
6. The old operator console still works throughout the migration.

## Post-Plan Follow-Up

Only after this plan passes should a follow-up plan consider:

- moving contributors from `Submission` to direct draft authoring
- retiring the old publish queue wording
- removing `User.token` in favor of first-class credential tables
- replacing `/submissions`, `/reviews`, and `/jobs` with fully private-first operator flows
