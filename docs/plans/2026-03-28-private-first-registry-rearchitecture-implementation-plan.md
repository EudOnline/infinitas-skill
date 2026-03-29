# Private-First Registry Rearchitecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current submission / review / promote / publish workflow with a private-first registry architecture built around drafts, immutable releases, exposure policies, review cases, access grants, and audience-aware discovery/install APIs.

**Architecture:** Build the new platform as a modular monolith inside the existing `server/` package. Keep `server/app.py`, `server/db.py`, and `server/auth.py` as thin composition entrypoints, but move domain logic into `server/modules/authoring`, `server/modules/release`, `server/modules/exposure`, `server/modules/review`, `server/modules/access`, `server/modules/discovery`, and `server/modules/audit`. Introduce real DB migrations, content-addressed release artifacts, policy-driven review, principal-aware authz, and audience-specific catalog projections. Once the new stack is complete, delete the old submission-centric routers and scripts instead of preserving compatibility.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, Jinja2, httpx, SQLite for local/dev, PostgreSQL-ready schema design, filesystem-backed artifact storage abstraction, existing manifest/provenance helpers where still useful, and `uv run` for repeatable commands.

---

## Preconditions

- Create a dedicated worktree before implementation.
- Treat the current hosted registry flow as replaceable, not sacred.
- Do not add new features to `Submission`, `Review`, `Job`, or the old `/api/v1/submissions` lifecycle while this plan is in flight.
- Prefer additive cutover in code, but not compatibility in product behavior.
- Use `@superpowers:test-driven-development` for each task that touches behavior.
- Use `@superpowers:verification-before-completion` before claiming the cutover is done.

## Scope Rules

- The target product model is the one defined in [2026-03-28-private-skill-registry-rearchitecture-design.md](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/plans/2026-03-28-private-skill-registry-rearchitecture-design.md).
- `token-visible` must not appear in the DB schema as a first-class visibility enum.
- Public exposure must require blocking review.
- Private and grant exposure must not require review by default.
- Search and install must become audience-aware.
- The final system may reuse release artifact formats, but it must not reuse the old status model.

## Explicit Non-Goals

- Do not preserve old API response shapes.
- Do not preserve old UI wording such as "submission", "promote", or "publish" as the main user journey.
- Do not add compatibility shims for the old CLI beyond what is needed for developer sanity during local bring-up.
- Do not keep `require_registry_reader` as the primary access model.

## Recommended Delivery Order

1. Stand up migrations and module skeletons first.
2. Land the new write model second.
3. Land authz and grants before public discovery.
4. Land projections and install resolution before UI cutover.
5. Delete the old lifecycle only after the new end-to-end path passes.

### Task 1: Establish the new server skeleton and real DB migrations

**Files:**
- Modify: `pyproject.toml`
- Modify: `server/app.py`
- Modify: `server/db.py`
- Modify: `server/settings.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/20260328_0001_private_registry_bootstrap.py`
- Create: `server/modules/__init__.py`
- Create: `server/modules/shared/__init__.py`
- Create: `server/modules/shared/metadata.py`
- Create: `server/modules/shared/enums.py`
- Create: `server/modules/shared/json.py`
- Create: `scripts/test-private-registry-bootstrap.py`
- Modify: `scripts/run-hosted-worker.py`

**Step 1: Write the failing bootstrap test**

Create `scripts/test-private-registry-bootstrap.py` that:

- sets a temp `INFINITAS_SERVER_DATABASE_URL`
- runs `uv run alembic upgrade head`
- imports `server.app.create_app`
- verifies `GET /healthz` returns `200`
- verifies the migration created an `alembic_version` table

Start with assertions shaped like:

```python
response = client.get('/healthz')
assert response.status_code == 200
assert table_exists(db_path, 'alembic_version')
```

**Step 2: Run the bootstrap test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-bootstrap.py
```

Expected: FAIL because Alembic is not configured and the new shared module layer does not exist.

**Step 3: Add the migration and shared-module foundation**

Update `pyproject.toml` to add `alembic`.

Create:

- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `server/modules/shared/metadata.py`
- `server/modules/shared/enums.py`
- `server/modules/shared/json.py`

Use `server/db.py` as the thin runtime wrapper over the SQLAlchemy engine/session factory, but change `ensure_database_ready()` so it runs migrations instead of `Base.metadata.create_all(...)`.

The first migration should create only the minimum shared tables needed for app boot:

- `users`
- `alembic_version` via Alembic

Keep old tables alone for now; do not drop them in bootstrap.

**Step 4: Wire app and worker boot to migrations**

Update:

- `server/app.py`
- `server/db.py`
- `scripts/run-hosted-worker.py`

So that:

- app startup ensures migrations are applied
- worker boot does the same
- bootstrap users are still seeded after migration

**Step 5: Re-run the focused bootstrap test**

Run:

```bash
uv run python3 scripts/test-private-registry-bootstrap.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add pyproject.toml alembic.ini alembic/env.py alembic/script.py.mako alembic/versions/20260328_0001_private_registry_bootstrap.py server/app.py server/db.py server/settings.py server/modules/__init__.py server/modules/shared/__init__.py server/modules/shared/metadata.py server/modules/shared/enums.py server/modules/shared/json.py scripts/test-private-registry-bootstrap.py scripts/run-hosted-worker.py
git commit -m "feat: add private registry migration and module scaffold"
```

### Task 2: Introduce the canonical write model and keep the old model isolated

**Files:**
- Modify: `server/models.py`
- Create: `server/modules/authoring/__init__.py`
- Create: `server/modules/authoring/models.py`
- Create: `server/modules/release/__init__.py`
- Create: `server/modules/release/models.py`
- Create: `server/modules/exposure/__init__.py`
- Create: `server/modules/exposure/models.py`
- Create: `server/modules/review/__init__.py`
- Create: `server/modules/review/models.py`
- Create: `server/modules/access/__init__.py`
- Create: `server/modules/access/models.py`
- Create: `server/modules/audit/__init__.py`
- Create: `server/modules/audit/models.py`
- Create: `alembic/versions/20260328_0002_private_registry_core_tables.py`
- Create: `scripts/test-private-registry-domain-model.py`

**Step 1: Write the failing domain-model test**

Create `scripts/test-private-registry-domain-model.py` with scenarios that:

- create a `Skill`, `SkillDraft`, `SkillVersion`, `Release`, `Exposure`, `ReviewCase`, `AccessGrant`, and `Credential`
- verify a `Release` references exactly one immutable `SkillVersion`
- verify an `Exposure` references a `Release` instead of a draft
- verify `public` exposure defaults to blocking review
- verify `grant` exposure can exist without a review case

Use assertions shaped like:

```python
assert exposure.release_id == release.id
assert exposure.review_requirement == 'blocking'
assert release.skill_version_id == version.id
```

**Step 2: Run the domain-model test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-domain-model.py
```

Expected: FAIL because the new tables and relationships do not exist.

**Step 3: Add the new domain tables**

Create models for:

- `Skill`
- `SkillDraft`
- `SkillVersion`
- `Release`
- `Artifact`
- `Principal`
- `Team`
- `TeamMembership`
- `ServicePrincipal`
- `Exposure`
- `ReviewPolicy`
- `ReviewCase`
- `ReviewDecision`
- `AccessGrant`
- `Credential`
- `AuditEvent`

Keep these in module-local `models.py` files and re-export them from `server/models.py` so SQLAlchemy metadata discovery stays simple during the transition.

**Step 4: Add the migration**

Create `alembic/versions/20260328_0002_private_registry_core_tables.py` to create the new tables without deleting the old `submissions`, `reviews`, and `jobs` tables yet.

Add indexes for:

- `skills(namespace_id, slug)`
- `skill_versions(skill_id, version)`
- `releases(skill_version_id, state)`
- `principals(kind, slug)`
- `teams(slug)`
- `team_memberships(user_id, team_id)`
- `service_principals(slug)`
- `exposures(release_id, audience_type, state)`
- `credentials(principal_id, type, revoked_at, expires_at)`

**Step 5: Re-run the focused domain-model test**

Run:

```bash
uv run python3 scripts/test-private-registry-domain-model.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/models.py server/modules/authoring/__init__.py server/modules/authoring/models.py server/modules/release/__init__.py server/modules/release/models.py server/modules/exposure/__init__.py server/modules/exposure/models.py server/modules/review/__init__.py server/modules/review/models.py server/modules/access/__init__.py server/modules/access/models.py server/modules/audit/__init__.py server/modules/audit/models.py alembic/versions/20260328_0002_private_registry_core_tables.py scripts/test-private-registry-domain-model.py
git commit -m "feat: add private registry core domain model"
```

### Task 3: Replace global registry-reader auth with principal, grant, and credential authz

**Files:**
- Modify: `server/auth.py`
- Modify: `server/settings.py`
- Modify: `server/api/auth.py`
- Create: `server/modules/access/schemas.py`
- Create: `server/modules/access/service.py`
- Create: `server/modules/access/router.py`
- Create: `server/modules/access/authn.py`
- Create: `server/modules/access/authz.py`
- Create: `server/modules/access/bootstrap.py`
- Create: `scripts/test-private-registry-access-api.py`
- Modify: `scripts/test-hosted-registry-auth.py`
- Modify: `scripts/registryctl.py`

**Step 1: Write the failing access/auth test**

Create `scripts/test-private-registry-access-api.py` that:

- creates users, teams, and service principals
- issues a `personal_token`
- issues a `grant_token`
- verifies a grant token can read only the release tied to its grant
- verifies anonymous requests cannot access `/api/v1/catalog/me`
- verifies user tokens no longer need to masquerade as `registry_read_tokens`

Use request assertions shaped like:

```python
assert denied.status_code == 401
assert allowed.status_code == 200
assert payload['credential']['type'] == 'grant_token'
```

**Step 2: Run the access/auth test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-access-api.py
```

Expected: FAIL because the current auth layer only knows user tokens and global registry read tokens.

**Step 3: Implement the new access module**

Create:

- `server/modules/access/schemas.py`
- `server/modules/access/service.py`
- `server/modules/access/router.py`
- `server/modules/access/authn.py`
- `server/modules/access/authz.py`
- `server/modules/access/bootstrap.py`

Support:

- principal types `user | team | service | anonymous`
- credentials `personal_token | service_token | grant_token | ephemeral_download_token`
- resource selectors
- scope checks like `draft:write`, `release:read`, `exposure:manage`, `artifact:download`

**Step 4: Rewire the old auth entrypoints to the new access layer**

Update:

- `server/auth.py`
- `server/api/auth.py`
- `server/settings.py`
- `scripts/registryctl.py`

So that:

- hosted login probes current principal state
- bearer tokens resolve through the new credential table
- `registry_read_tokens` becomes deprecated and stops gating new discovery endpoints

Keep the old setting readable only long enough for local test fixtures, then remove it in Task 9.

**Step 5: Re-run focused access tests**

Run:

```bash
uv run python3 scripts/test-private-registry-access-api.py
uv run python3 scripts/test-hosted-registry-auth.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/auth.py server/settings.py server/api/auth.py server/modules/access/schemas.py server/modules/access/service.py server/modules/access/router.py server/modules/access/authn.py server/modules/access/authz.py server/modules/access/bootstrap.py scripts/test-private-registry-access-api.py scripts/test-hosted-registry-auth.py scripts/registryctl.py
git commit -m "feat: add principal and credential based authz"
```

### Task 4: Implement authoring APIs for skills, drafts, and immutable version sealing

**Files:**
- Create: `server/modules/authoring/schemas.py`
- Create: `server/modules/authoring/service.py`
- Create: `server/modules/authoring/router.py`
- Create: `server/modules/authoring/repository.py`
- Modify: `server/app.py`
- Create: `scripts/test-private-registry-authoring-api.py`
- Modify: `scripts/registryctl.py`
- Modify: `docs/ai/server-api.md`

**Step 1: Write the failing authoring API test**

Create `scripts/test-private-registry-authoring-api.py` that:

- creates a skill
- creates a draft
- patches draft metadata
- seals the draft into a `SkillVersion`
- verifies the sealed draft can no longer be edited

Use API assertions shaped like:

```python
assert create_skill.status_code == 201
assert seal_response.json()['version'] == '0.1.0'
assert patch_after_seal.status_code == 409
```

**Step 2: Run the authoring API test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-authoring-api.py
```

Expected: FAIL because no authoring routes exist yet.

**Step 3: Implement the authoring module**

Create:

- `server/modules/authoring/schemas.py`
- `server/modules/authoring/service.py`
- `server/modules/authoring/router.py`
- `server/modules/authoring/repository.py`

Routes to add:

- `POST /api/v1/skills`
- `GET /api/v1/skills/{skill_id}`
- `POST /api/v1/skills/{skill_id}/drafts`
- `PATCH /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/seal`

Seal behavior must:

- freeze content and metadata
- compute content digest
- create `SkillVersion`
- move draft state from `open` to `sealed`

**Step 4: Mount the new router and add CLI verbs**

Update:

- `server/app.py`
- `scripts/registryctl.py`
- `docs/ai/server-api.md`

Add CLI commands:

- `skills create`
- `drafts create`
- `drafts update`
- `drafts seal`

**Step 5: Re-run focused authoring tests**

Run:

```bash
uv run python3 scripts/test-private-registry-authoring-api.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/modules/authoring/schemas.py server/modules/authoring/service.py server/modules/authoring/router.py server/modules/authoring/repository.py server/app.py scripts/test-private-registry-authoring-api.py scripts/registryctl.py docs/ai/server-api.md
git commit -m "feat: add skill draft and version authoring api"
```

### Task 5: Implement release creation and immutable artifact materialization

**Files:**
- Create: `server/modules/release/schemas.py`
- Create: `server/modules/release/service.py`
- Create: `server/modules/release/router.py`
- Create: `server/modules/release/storage.py`
- Create: `server/modules/release/materializer.py`
- Modify: `server/worker.py`
- Modify: `server/jobs.py`
- Modify: `server/artifact_ops.py`
- Create: `scripts/materialize-release.py`
- Create: `scripts/test-private-registry-release-api.py`
- Create: `scripts/test-private-registry-release-worker.py`

**Step 1: Write the failing release tests**

Create `scripts/test-private-registry-release-api.py` and `scripts/test-private-registry-release-worker.py` that:

- create a `Release` from a sealed `SkillVersion`
- queue release materialization work
- verify artifacts are content-addressed
- verify `ready` releases cannot be mutated
- verify a second materialization of the same version is idempotent

Use assertions shaped like:

```python
assert release['state'] == 'preparing'
assert finished_release['state'] == 'ready'
assert manifest['sha256']
assert retry_response.status_code in (200, 409)
```

**Step 2: Run the release tests to verify they fail**

Run:

```bash
uv run python3 scripts/test-private-registry-release-api.py
uv run python3 scripts/test-private-registry-release-worker.py
```

Expected: FAIL because releases are still implicitly driven by `publish_submission`.

**Step 3: Implement the release module**

Create:

- `server/modules/release/schemas.py`
- `server/modules/release/service.py`
- `server/modules/release/router.py`
- `server/modules/release/storage.py`
- `server/modules/release/materializer.py`
- `scripts/materialize-release.py`

Routes to add:

- `POST /api/v1/versions/{version_id}/releases`
- `GET /api/v1/releases/{release_id}`
- `GET /api/v1/releases/{release_id}/artifacts`

Use filesystem-backed storage first, but make `storage.py` an interface layer so object storage can be swapped in later.

**Step 4: Rewire worker and artifact operations**

Update:

- `server/worker.py`
- `server/jobs.py`
- `server/artifact_ops.py`

So that the worker can process a new `materialize_release` job kind and emit:

- bundle
- manifest
- signature
- provenance
- optional preview

Do not call `scripts/publish-skill.sh` from the new flow.

**Step 5: Re-run focused release tests**

Run:

```bash
uv run python3 scripts/test-private-registry-release-api.py
uv run python3 scripts/test-private-registry-release-worker.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/modules/release/schemas.py server/modules/release/service.py server/modules/release/router.py server/modules/release/storage.py server/modules/release/materializer.py server/worker.py server/jobs.py server/artifact_ops.py scripts/materialize-release.py scripts/test-private-registry-release-api.py scripts/test-private-registry-release-worker.py
git commit -m "feat: add immutable release materialization flow"
```

### Task 6: Implement exposure, review policy, and review-case workflows

**Files:**
- Create: `server/modules/exposure/schemas.py`
- Create: `server/modules/exposure/service.py`
- Create: `server/modules/exposure/router.py`
- Create: `server/modules/review/schemas.py`
- Create: `server/modules/review/service.py`
- Create: `server/modules/review/router.py`
- Create: `server/modules/review/policy.py`
- Create: `server/modules/review/default_policy.py`
- Create: `scripts/test-private-registry-exposure-review.py`
- Modify: `server/app.py`
- Modify: `docs/review-workflow.md`

**Step 1: Write the failing exposure/review test**

Create `scripts/test-private-registry-exposure-review.py` that:

- creates a `private` exposure and verifies no review case is opened
- creates a `grant` exposure with `requested_review_mode=advisory` and verifies activation does not block
- creates a `public` exposure and verifies a blocking review case is opened automatically
- approves the public review case and verifies the exposure becomes `active`
- rejects a second public exposure and verifies it stays inactive

Use assertions shaped like:

```python
assert private_exposure['state'] == 'active'
assert public_exposure['state'] == 'review_open'
assert review_case['mode'] == 'blocking'
assert approved_exposure['state'] == 'active'
```

**Step 2: Run the exposure/review test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-exposure-review.py
```

Expected: FAIL because exposure and review are still coupled to the old submission objects.

**Step 3: Implement the exposure module**

Create:

- `server/modules/exposure/schemas.py`
- `server/modules/exposure/service.py`
- `server/modules/exposure/router.py`

Routes to add:

- `POST /api/v1/releases/{release_id}/exposures`
- `PATCH /api/v1/exposures/{exposure_id}`
- `POST /api/v1/exposures/{exposure_id}/activate`
- `POST /api/v1/exposures/{exposure_id}/revoke`

Support:

- `audience_type`
- `listing_mode`
- `install_mode`
- `requested_review_mode`
- state transitions `draft -> pending_policy -> review_open|active`

**Step 4: Implement policy-driven review**

Create:

- `server/modules/review/schemas.py`
- `server/modules/review/service.py`
- `server/modules/review/router.py`
- `server/modules/review/policy.py`
- `server/modules/review/default_policy.py`

Routes to add:

- `POST /api/v1/exposures/{exposure_id}/review-cases`
- `POST /api/v1/review-cases/{review_case_id}/decisions`
- `GET /api/v1/review-cases/{review_case_id}`

Encode the first-pass rules exactly:

- `public` -> `blocking`
- `grant + advisory requested` -> `advisory`
- `grant + blocking requested` -> `blocking`
- `private` -> `none`

**Step 5: Re-run focused exposure/review tests**

Run:

```bash
uv run python3 scripts/test-private-registry-exposure-review.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/modules/exposure/schemas.py server/modules/exposure/service.py server/modules/exposure/router.py server/modules/review/schemas.py server/modules/review/service.py server/modules/review/router.py server/modules/review/policy.py server/modules/review/default_policy.py scripts/test-private-registry-exposure-review.py server/app.py docs/review-workflow.md
git commit -m "feat: add exposure workflow and policy driven review"
```

### Task 7: Build audience-specific discovery projections and install-resolution endpoints

**Files:**
- Create: `server/modules/discovery/__init__.py`
- Create: `server/modules/discovery/schemas.py`
- Create: `server/modules/discovery/service.py`
- Create: `server/modules/discovery/router.py`
- Create: `server/modules/discovery/projections.py`
- Create: `server/modules/discovery/search.py`
- Modify: `server/app.py`
- Modify: `server/worker.py`
- Modify: `scripts/http_registry_lib.py`
- Modify: `scripts/resolve-install-plan.py`
- Modify: `scripts/pull-skill.sh`
- Modify: `scripts/install-by-name.sh`
- Modify: `scripts/check-skill-update.sh`
- Create: `scripts/test-private-registry-discovery.py`
- Create: `scripts/test-private-registry-install-resolution.py`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/ai/pull.md`

**Step 1: Write the failing discovery/install tests**

Create:

- `scripts/test-private-registry-discovery.py`
- `scripts/test-private-registry-install-resolution.py`

Cover:

- anonymous search returns only active public listed exposures
- authenticated search returns owned, granted, and public exposures
- grant token search returns only exposures tied to that grant
- install resolution returns manifest + artifact URLs only when the caller is authorized

Use assertions shaped like:

```python
assert public_only_names == ['reviewed-public-skill']
assert 'private-owner-skill' in me_names
assert denied.status_code == 403
assert install_payload['release_id']
```

**Step 2: Run the discovery/install tests to verify they fail**

Run:

```bash
uv run python3 scripts/test-private-registry-discovery.py
uv run python3 scripts/test-private-registry-install-resolution.py
```

Expected: FAIL because search and install are still based on global registry-reader access and static registry files.

**Step 3: Implement projections and discovery routes**

Create:

- `server/modules/discovery/schemas.py`
- `server/modules/discovery/service.py`
- `server/modules/discovery/router.py`
- `server/modules/discovery/projections.py`
- `server/modules/discovery/search.py`

Routes to add:

- `GET /api/v1/catalog/public`
- `GET /api/v1/catalog/me`
- `GET /api/v1/catalog/grant`
- `GET /api/v1/search/public`
- `GET /api/v1/search/me`
- `GET /api/v1/install/public/{skill_ref}`
- `GET /api/v1/install/me/{skill_ref}`
- `GET /api/v1/install/grant/{skill_ref}`

Projection refresh can be synchronous at first, but isolate it in `projections.py` so it can move to background jobs later.

**Step 4: Update install scripts to use the new API contract**

Update:

- `scripts/http_registry_lib.py`
- `scripts/resolve-install-plan.py`
- `scripts/pull-skill.sh`
- `scripts/install-by-name.sh`
- `scripts/check-skill-update.sh`
- `docs/ai/discovery.md`
- `docs/ai/pull.md`

So that hosted installs resolve through the new audience-specific endpoints instead of assuming one shared `/registry/...` read surface.

**Step 5: Re-run focused discovery/install tests**

Run:

```bash
uv run python3 scripts/test-private-registry-discovery.py
uv run python3 scripts/test-private-registry-install-resolution.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/modules/discovery/__init__.py server/modules/discovery/schemas.py server/modules/discovery/service.py server/modules/discovery/router.py server/modules/discovery/projections.py server/modules/discovery/search.py server/app.py server/worker.py scripts/http_registry_lib.py scripts/resolve-install-plan.py scripts/pull-skill.sh scripts/install-by-name.sh scripts/check-skill-update.sh scripts/test-private-registry-discovery.py scripts/test-private-registry-install-resolution.py docs/ai/discovery.md docs/ai/pull.md
git commit -m "feat: add audience aware discovery and install resolution"
```

### Task 8: Rebuild the Web UI and CLI around draft, release, share, and token management

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
- Modify: `scripts/registryctl.py`
- Create: `scripts/test-private-registry-ui.py`
- Create: `scripts/test-private-registry-cli.py`

**Step 1: Write the failing UI and CLI tests**

Create:

- `scripts/test-private-registry-ui.py`
- `scripts/test-private-registry-cli.py`

Cover:

- homepage copy describes a private-first skill library
- console navigation uses `Skills`, `Drafts`, `Releases`, `Share`, `Access`, `Review`
- detail pages show `Private`, `Shared by token`, and `Public`
- CLI exposes commands for skills, drafts, releases, exposures, grants, and tokens

Use assertions shaped like:

```python
assert '私人技能库' in home_html
assert 'Shared by token' in share_html
assert 'drafts create' in cli_help
assert 'submissions create' not in cli_help
```

**Step 2: Run the UI and CLI tests to verify they fail**

Run:

```bash
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-private-registry-cli.py
```

Expected: FAIL because the UI and CLI still speak the old submission vocabulary.

**Step 3: Rebuild the server-rendered console**

Create:

- `server/templates/skills.html`
- `server/templates/skill-detail.html`
- `server/templates/draft-detail.html`
- `server/templates/release-detail.html`
- `server/templates/share-detail.html`
- `server/templates/access-tokens.html`
- `server/templates/review-cases.html`

Update:

- `server/app.py`
- `server/templates/layout-kawaii.html`
- `server/templates/index-kawaii.html`
- `server/templates/login-kawaii.html`
- `server/static/js/app.js`

The main information architecture should become:

- skill list
- draft editor/status
- release detail
- share/exposure management
- token/access management
- review inbox

**Step 4: Rebuild the CLI surface**

Update `scripts/registryctl.py` so the top-level nouns become:

- `skills`
- `drafts`
- `releases`
- `exposures`
- `grants`
- `tokens`
- `reviews`

Delete old `submissions` commands in Task 9, but stop advertising them here.

**Step 5: Re-run focused UI and CLI tests**

Run:

```bash
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-private-registry-cli.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/app.py server/static/js/app.js server/templates/layout-kawaii.html server/templates/index-kawaii.html server/templates/login-kawaii.html server/templates/skills.html server/templates/skill-detail.html server/templates/draft-detail.html server/templates/release-detail.html server/templates/share-detail.html server/templates/access-tokens.html server/templates/review-cases.html scripts/registryctl.py scripts/test-private-registry-ui.py scripts/test-private-registry-cli.py
git commit -m "feat: rebuild registry ui and cli around new lifecycle"
```

### Task 9: Cut over fully and delete the old submission-centric workflow

**Files:**
- Delete: `server/api/submissions.py`
- Delete: `server/api/reviews.py`
- Delete: `server/api/skills.py`
- Delete: `server/api/jobs.py`
- Delete: `server/schemas.py`
- Delete: `server/templates/submissions.html`
- Delete: `server/templates/reviews.html`
- Delete: `server/templates/jobs.html`
- Delete: `scripts/request-review.sh`
- Delete: `scripts/approve-skill.sh`
- Delete: `scripts/promote-skill.sh`
- Delete: `scripts/publish-skill.sh`
- Delete: `scripts/test-submission-review-api.py`
- Modify: `server/app.py`
- Modify: `server/worker.py`
- Modify: `server/jobs.py`
- Modify: `server/settings.py`
- Create: `alembic/versions/20260328_0003_drop_legacy_submission_tables.py`
- Create: `scripts/test-private-registry-e2e.py`
- Modify: `docs/ai/publish.md`
- Modify: `docs/ui-ux-analysis-and-rebuild.md`

**Step 1: Write the failing full cutover test**

Create `scripts/test-private-registry-e2e.py` that exercises the new happy path:

1. create a skill
2. create and update a draft
3. seal version
4. create release
5. materialize release
6. expose privately
7. create grant token
8. resolve install through grant token
9. request public exposure
10. approve review
11. resolve anonymous install

Also assert:

- `/api/v1/submissions` returns `404`
- CLI help no longer lists `submissions`
- old templates are unreachable

**Step 2: Run the full cutover test to verify it fails**

Run:

```bash
uv run python3 scripts/test-private-registry-e2e.py
```

Expected: FAIL until the old routers, settings, and scripts are removed.

**Step 3: Delete the old lifecycle and drop the old tables**

Delete:

- `server/api/submissions.py`
- `server/api/reviews.py`
- `server/api/skills.py`
- `server/api/jobs.py`
- `server/schemas.py`
- `server/templates/submissions.html`
- `server/templates/reviews.html`
- `server/templates/jobs.html`
- `scripts/request-review.sh`
- `scripts/approve-skill.sh`
- `scripts/promote-skill.sh`
- `scripts/publish-skill.sh`
- `scripts/test-submission-review-api.py`

Create `alembic/versions/20260328_0003_drop_legacy_submission_tables.py` to remove:

- `submissions`
- `reviews`
- legacy `jobs` rows or schema if the new release jobs now use a different table shape

Remove `registry_read_tokens` from `server/settings.py` completely in this step.

**Step 4: Rewire the app to only the new routers**

Update:

- `server/app.py`
- `server/worker.py`
- `server/jobs.py`
- `docs/ai/publish.md`
- `docs/ui-ux-analysis-and-rebuild.md`

The app should now mount only the new module routers and present only the new vocabulary.

**Step 5: Re-run full verification**

Run:

```bash
uv run python3 scripts/test-private-registry-bootstrap.py
uv run python3 scripts/test-private-registry-domain-model.py
uv run python3 scripts/test-private-registry-access-api.py
uv run python3 scripts/test-private-registry-authoring-api.py
uv run python3 scripts/test-private-registry-release-api.py
uv run python3 scripts/test-private-registry-release-worker.py
uv run python3 scripts/test-private-registry-exposure-review.py
uv run python3 scripts/test-private-registry-discovery.py
uv run python3 scripts/test-private-registry-install-resolution.py
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-private-registry-cli.py
uv run python3 scripts/test-private-registry-e2e.py
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add server/app.py server/worker.py server/jobs.py server/settings.py alembic/versions/20260328_0003_drop_legacy_submission_tables.py scripts/test-private-registry-e2e.py docs/ai/publish.md docs/ui-ux-analysis-and-rebuild.md
git rm server/api/submissions.py server/api/reviews.py server/api/skills.py server/api/jobs.py server/schemas.py server/templates/submissions.html server/templates/reviews.html server/templates/jobs.html scripts/request-review.sh scripts/approve-skill.sh scripts/promote-skill.sh scripts/publish-skill.sh scripts/test-submission-review-api.py
git commit -m "feat: cut over to private first registry lifecycle"
```

## Verification Checklist

- anonymous callers can only see approved public exposures
- a grant token can only resolve releases tied to its grant
- a user token never needs a global registry-read bypass
- draft edits are impossible after sealing
- release artifacts are immutable and content-addressed
- public exposures cannot activate without blocking approval
- private and grant exposures can activate without review unless the creator requested it
- UI copy no longer centers around submissions/promotion/publish
- no code path calls the old `scripts/publish-skill.sh` or `scripts/promote-skill.sh`

## Risks To Watch

- Avoid letting `server/models.py` become a second domain home; it should become an import barrel, not a logic hub.
- Do not leak policy decisions into routers; keep them in `server/modules/review/policy.py`.
- Do not let discovery query live tables ad hoc once projections exist.
- Do not keep long-lived plaintext tokens anywhere; only store hashes.
- Do not silently let one credential exceed its principal or grant scope.

## Nice-To-Have Follow-Ups After Cutover

- add team membership administration UI
- add short-lived signed download URLs for large artifact stores
- add approval expiry and re-review timers
- add malware or policy-pack scanning as a release prerequisite
- add PostgreSQL CI coverage alongside SQLite

## Recommended First Execution Slice

If implementation starts immediately, do not start with UI.

Start with:

1. Task 1
2. Task 2
3. Task 3

Those three tasks establish the minimum safe foundation. Everything after that becomes much easier to reason about.
