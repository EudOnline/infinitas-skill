# Clean Architecture Reset Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the unreleased project's migration intermediates with one clean architecture, one
database schema, one CLI entrypoint, and one pytest-based verification system.

**Architecture:** Use a hard cutover. Domain modules own models, routers, services, repositories, and
schemas. UI and JSON API consume shared application read models without importing each other. The
request/session boundary owns transactions, FastAPI lifespan owns initialization, and internal
compatibility code is deleted instead of deprecated.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, pytest, Ruff, Mypy, Jinja2, native ES
modules, Tailwind CSS.

---

## Execution Preconditions

- Execute in an isolated worktree after deciding how to preserve the current dirty workspace.
- The user has authorized deletion of development databases, local state, and migration history.
- Do not preserve old internal imports, schemas, command aliases, routes, or test entrypoints.
- Do not create commits unless the user separately authorizes commit operations.
- Use `superpowers:test-driven-development` for every behavior or architecture change.
- Use `superpowers:systematic-debugging` for every unexpected failure.
- Use `superpowers:verification-before-completion` before closing each task.

### Task 1: Install Clean-Architecture Guardrails

**Files:**
- Create: `tests/helpers/import_graph.py`
- Create: `tests/unit/governance/test_clean_architecture_contract.py`
- Modify: `tests/integration/test_maintainability_budgets.py`

**Step 1: Write the failing import-graph helper tests**

Implement an AST-only helper that returns internal import edges and strongly connected components.
The test must assert that scanning `server/` and `src/infinitas_skill/` returns no multi-module SCC.

**Step 2: Add failing architecture assertions**

The governance test must assert:

```python
assert not (ROOT / "server" / "models.py").exists()
assert not (ROOT / "server" / "api").exists()
assert not list((ROOT / "scripts").glob("test-*.py"))
assert len(list((ROOT / "alembic" / "versions").glob("*.py"))) == 1
```

It must also scan production imports and reject:

- `from server.models ...`;
- imports from `server.ui` by `server/modules`;
- `sys.path.insert` or `sys.path.append`;
- non-empty domain `__init__.py` files that import routers or models;
- the phrases `backward compatibility`, `backwards-compatible`, or `re-export` in production code.

**Step 3: Run and verify RED**

Run:

```bash
.venv/bin/pytest tests/unit/governance/test_clean_architecture_contract.py -q --override-ini=addopts=
```

Expected: FAIL on `server/models.py`, multiple migrations, script tests, compatibility re-exports,
and import cycles.

**Step 4: Replace line-count budgets with target ceilings**

Set final production ceilings in `test_maintainability_budgets.py`:

- production module: 600 lines maximum;
- production function: 100 lines maximum;
- `server/static/css/input.css`: 1,000 lines maximum;
- top-level scripts: 20 maximum.

Keep these tests failing until later tasks satisfy them.

### Task 2: Give Every ORM Model One Owner

**Files:**
- Create: `server/modules/identity/models.py`
- Create: `server/modules/identity/__init__.py`
- Create: `server/modules/jobs/models.py`
- Create: `server/modules/jobs/__init__.py`
- Create: `server/model_registry.py`
- Modify: `server/model_base.py`
- Modify: `server/db.py`
- Modify: `server/jobs.py`
- Modify: `server/worker.py`
- Modify: `server/auth.py`
- Modify: `server/rate_limit.py`
- Modify: `server/api/auth.py`
- Modify: `server/api/activity.py`
- Modify: `server/api/profile.py`
- Modify: `server/modules/access/authn.py`
- Modify: `server/modules/access/authz.py`
- Modify: `server/modules/access/models.py`
- Modify: `server/modules/access/service.py`
- Modify: `server/modules/access/share_links.py`
- Modify: `server/modules/access/token_service.py`
- Modify: `server/modules/audit/read_model.py`
- Modify: `server/modules/discovery/projections.py`
- Modify: `server/modules/exposure/service.py`
- Modify: `server/modules/profile/service.py`
- Modify: `server/modules/release/router.py`
- Modify: `server/modules/release/service.py`
- Modify: `server/modules/review/service.py`
- Modify: `server/ui/activity.py`
- Modify: `server/ui/auth_state.py`
- Modify: `server/ui/console.py`
- Modify: `server/ui/library_access.py`
- Modify: `server/ui/library_objects.py`
- Modify: `server/ui/library_releases.py`
- Modify: `server/ui/library_scope.py`
- Modify: `server/ui/queries.py`
- Delete: `server/models.py`
- Test: `tests/unit/server/test_model_imports.py`
- Test: `tests/integration/test_alembic_metadata.py`

**Step 1: Add failing direct-model-import tests**

Assert that `User`, `Principal`, and `Credential` import from identity; `Job` imports from jobs; and
every other model imports from its owning domain without importing `server.models`.

**Step 2: Move `User` and `Job`**

Move the class definitions without changing their final schema. Move access-owned identity records
into `identity/models.py`; keep access grants in `access/models.py`.

**Step 3: Create the metadata registry**

`server/model_registry.py` imports each domain model module for side effects and exports nothing.
Alembic imports `Base` and then imports `server.model_registry` once.

**Step 4: Replace all central model imports**

Use:

```bash
rg -n "from server\.models import|import server\.models" server tests
```

Expected after replacement: no production matches.

**Step 5: Delete `server/models.py` and run GREEN**

Run:

```bash
.venv/bin/pytest tests/unit/server/test_model_imports.py -q --override-ini=addopts=
.venv/bin/python -W error -c "from server.model_base import Base; import server.model_registry; print(len(Base.metadata.tables))"
```

Expected: PASS and a non-zero table count without warnings.

### Task 3: Replace Migration History with One Initial Migration

**Files:**
- Delete: `alembic/versions/20260329_0001_bootstrap_alembic.py`
- Delete: `alembic/versions/20260329_0002_release_graph.py`
- Delete: `alembic/versions/20260329_0003_exposure_access_review.py`
- Delete: `alembic/versions/20260329_0004_private_first_cutover.py`
- Delete: `alembic/versions/20260329_0005_personal_token_hash_cutover.py`
- Delete: `alembic/versions/20260405_0006_add_job_leases.py`
- Delete: `alembic/versions/20260419_0007_registry_objects_and_draft_content.py`
- Delete: `alembic/versions/20260420_0008_add_release_platform_compatibility_json.py`
- Delete: `alembic/versions/20260424_0001_product_tokens_and_share_links.py`
- Delete: `alembic/versions/20260601_0009_add_composite_indexes.py`
- Delete: `alembic/versions/20260601_0010_add_rate_limit_entries_table.py`
- Delete: `alembic/versions/20260602_0011_remove_registry_object_abstraction.py`
- Delete: `alembic/versions/20260604_0012_add_performance_indexes.py`
- Delete: `alembic/versions/20260611_0013_add_fk_constraints_and_indexes.py`
- Delete: `alembic/versions/20260611_0014_add_remaining_fk_indexes.py`
- Delete: `alembic/versions/52ab6f2e589e_add_user_password_hash.py`
- Delete: `alembic/versions/6fe6c7710a23_drop_user_unused_columns.py`
- Delete: `alembic/versions/df25325e7fd0_drop_share_links.py`
- Delete: `alembic/versions/e8763ef508a1_drop_skill_drafts_and_created_from_.py`
- Create: `alembic/versions/0001_initial.py`
- Modify: `alembic/env.py`
- Modify: `tests/integration/test_alembic_metadata.py`
- Delete: compatibility-only migration tests identified by `rg -n "cutover|legacy|downgrade base" tests scripts`

**Step 1: Rewrite the migration test for the target contract**

Test empty DB → `upgrade head` → `alembic check` → `downgrade base` → no application tables.

**Step 2: Delete local database state**

Remove development SQLite databases and database-derived `.state` artifacts inside the isolated
worktree. Do not remove canonical source catalog or skill definitions.

**Step 3: Generate and review the initial migration**

Run:

```bash
.venv/bin/alembic revision --autogenerate -m "initial schema" --rev-id 0001
```

Rename the generated file to `0001_initial.py`. Review every table, FK, unique constraint, and index.
No operation may contain rename, data copy, conditional legacy detection, or backfill logic.

**Step 4: Verify GREEN**

Run:

```bash
.venv/bin/pytest tests/integration/test_alembic_metadata.py -q --override-ini=addopts=
```

Expected: PASS.

### Task 4: Move Initialization into Lifespan and Centralize Transactions

**Files:**
- Create: `server/lifecycle.py`
- Create: `server/bootstrap.py`
- Modify: `server/app.py`
- Delete: `server/app_factory.py`
- Modify: `scripts/generate-openapi.py`
- Modify: `server/db.py`
- Modify: `server/modules/authoring/service.py`
- Modify: `server/modules/exposure/service.py`
- Modify: `server/modules/profile/service.py`
- Modify: `server/modules/release/router.py`
- Modify: `server/modules/release/service.py`
- Modify: `server/modules/review/router.py`
- Modify: `server/modules/review/service.py`
- Modify: `server/api/auth.py`
- Modify: `server/api/object_tokens.py`
- Modify: `server/api/share_links.py`
- Test: `tests/integration/test_db_utils.py`
- Test: `tests/unit/server_ops/test_openapi_generation.py`
- Create: `tests/integration/test_transaction_boundaries.py`

**Step 1: Write failing lifecycle tests**

Importing `server.app` or calling `create_app()` must not create a database file. Entering lifespan
must initialize the database exactly once.

**Step 2: Write failing transaction tests**

Prove that a successful request commits, an exception rolls back, and a service can participate in a
larger transaction without committing independently.

**Step 3: Implement `get_db()` transaction ownership**

Use this shape:

```python
def get_db():
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Add a separate `session_scope()` context manager for workers and CLI server operations.

**Step 4: Remove inner commits and rollbacks**

Repositories flush when IDs are needed. Services return mutated objects. Routers do not commit.

**Step 5: Move bootstrap out of DB infrastructure**

`bootstrap.py` owns development bootstrap users and credentials. `db.py` contains no imports from
`server.auth` or domain services.

**Step 6: Verify GREEN**

Run the new lifecycle/transaction tests plus auth, release, exposure, and review integration tests.

### Task 5: Move API Routers into Owning Domains

**Files:**
- Create: `server/modules/system/router.py`
- Create: `server/modules/system/__init__.py`
- Create: `server/modules/identity/router.py`
- Create: `server/modules/identity/auth.py`
- Create: `server/modules/identity/guards.py`
- Create: `server/modules/identity/repository.py`
- Create: `server/modules/identity/schemas.py`
- Create: `server/modules/identity/service.py`
- Create: `server/modules/audit/router.py`
- Create: `server/modules/library/router.py`
- Modify: `server/modules/access/router.py`
- Modify: `server/modules/discovery/router.py`
- Modify: `server/app.py`
- Modify: all production imports of `server.auth` and `server.auth_guards`
- Delete: `server/auth.py`
- Delete: `server/auth_guards.py`
- Delete: `server/modules/profile/service.py`
- Delete: `server/modules/profile/__init__.py`
- Delete: `server/api/activity.py`
- Delete: `server/api/auth.py`
- Delete: `server/api/library.py`
- Delete: `server/api/object_tokens.py`
- Delete: `server/api/profile.py`
- Delete: `server/api/search.py`
- Delete: `server/api/share_links.py`
- Delete: `server/api/system.py`
- Delete: `server/api/__init__.py`
- Test: `tests/integration/test_api_endpoints.py`
- Test: `tests/unit/server_ops/test_openapi_generation.py`

**Step 1: Add a failing route ownership contract**

Assert that every OpenAPI operation maps to a router under `server/modules/*/router.py` and that
`server/api` does not exist.

**Step 2: Move routes without aliases**

Preserve the current canonical HTTP paths only. Remove old path aliases and duplicate route concepts
that exist solely for a prior implementation. Keep distinct `/me` endpoints only when they represent
different current resources, as documented by the dual-consumer architecture.

Move password/session cryptography and current-user dependencies into `identity/auth.py`. Move
identity lookup and credential lifecycle operations out of `access/service.py` into
`identity/service.py`. `access` retains grants, object tokens, share credentials, and access-policy
evaluation only.

**Step 3: Regenerate OpenAPI and verify paths**

Run:

```bash
.venv/bin/python scripts/generate-openapi.py
.venv/bin/python scripts/generate-openapi.py --check
```

Expected: PASS and no compatibility-only paths.

### Task 6: Create UI/API-Neutral Library Read Models

**Files:**
- Create: `server/modules/library/read_models.py`
- Create: `server/modules/library/__init__.py`
- Create: `server/modules/library/queries.py`
- Create: `server/modules/library/service.py`
- Create: `server/modules/library/schemas.py`
- Modify: `server/modules/library/router.py`
- Modify: `server/ui/library_objects.py`
- Modify: `server/ui/library_releases.py`
- Modify: `server/ui/library_scope.py`
- Modify: `server/ui/library_access.py`
- Modify: `server/ui/library_shares.py`
- Test: `tests/integration/test_library_api.py`
- Test: `tests/integration/test_private_registry_ui.py`

**Step 1: Add a failing boundary test**

AST-scan `server/modules` and reject imports from `server.ui`.

**Step 2: Move SQL and aggregation logic**

Move object, release, access, share, and activity projections into typed read models. UI helpers may
only translate those read models into localized template context.

**Step 3: Verify both consumers**

Run API contract tests and HTML template-context tests against the same seeded records. Expected:
equivalent IDs, counts, visibility state, and release state.

### Task 7: Split UI Route Registration and Remove Package Import Cycles

**Files:**
- Create: `server/ui/routes/home.py`
- Create: `server/ui/routes/library.py`
- Create: `server/ui/routes/profile.py`
- Create: `server/ui/routes/settings.py`
- Create: `server/ui/routes/__init__.py`
- Delete: `server/ui/routes.py`
- Modify: `server/app.py`
- Replace contents with empty modules: `server/modules/discovery/__init__.py`
- Replace contents with empty modules: `server/modules/registry/__init__.py`
- Replace contents with empty modules: `server/modules/access/__init__.py`
- Replace contents with empty modules: `server/modules/authoring/__init__.py`
- Replace contents with empty modules: `server/modules/audit/__init__.py`
- Replace contents with empty modules: `server/modules/exposure/__init__.py`
- Replace contents with empty modules: `server/modules/release/__init__.py`
- Replace contents with empty modules: `server/modules/review/__init__.py`
- Replace contents with empty modules: `server/modules/identity/__init__.py`
- Replace contents with empty modules: `server/modules/jobs/__init__.py`
- Replace contents with empty modules: `server/modules/library/__init__.py`
- Replace contents with empty modules: `server/modules/system/__init__.py`
- Test: `tests/unit/server/test_model_imports.py`
- Test: `tests/unit/governance/test_clean_architecture_contract.py`

**Step 1: Add failing direct-import tests for all routers**

Every router and page route module must import successfully in a clean interpreter.

**Step 2: Split page routers**

No route registration function may exceed 100 lines. Shared template context moves to
`server/ui/context.py`.

**Step 3: Remove eager package exports**

All production imports use explicit modules such as `server.modules.registry.service`, never package
facades.

**Step 4: Verify the import graph**

Run the SCC test. Expected: zero cycles.

### Task 8: Replace the Install Workflow God Module

**Files:**
- Create: `src/infinitas_skill/install/cli.py`
- Create: `src/infinitas_skill/install/common.py`
- Create: `src/infinitas_skill/install/resolve.py`
- Create: `src/infinitas_skill/install/exact.py`
- Create: `src/infinitas_skill/install/sync.py`
- Create: `src/infinitas_skill/install/update.py`
- Create: `src/infinitas_skill/install/switch.py`
- Create: `src/infinitas_skill/install/rollback.py`
- Create: `src/infinitas_skill/install/upgrade.py`
- Modify: `src/infinitas_skill/cli/main.py`
- Delete: `src/infinitas_skill/install/workflows.py`
- Delete: `src/infinitas_skill/install/workflows_parsers.py`
- Test: `tests/integration/test_cli_install_workflows.py`
- Test: `tests/integration/test_cli_install_planning.py`
- Test: `tests/integration/test_cli_update_workflows.py`

**Step 1: Add failing CLI registration tests**

`cli/main.py` must import only `configure_*_cli` registrars, not individual install handlers.

**Step 2: Move one command at a time**

Recommended order: resolve → exact → by-name → check-update → sync → switch → rollback → upgrade.
For each command: move its parser, move its handler, run its focused test, then remove the old code.

**Step 3: Extract only genuinely shared helpers**

Place subprocess invocation, payload emission, and common source resolution in `common.py`. Do not
create a second general-purpose workflow module.

**Step 4: Delete old workflow files**

Run:

```bash
rg -n "install\.workflows|workflows_parsers" src tests scripts
```

Expected: no matches.

### Task 9: Delete Legacy Formats and Compatibility Behavior

**Files:**
- Modify: `src/infinitas_skill/skills/schema_version.py`
- Modify: `src/infinitas_skill/skills/canonical.py`
- Modify: `src/infinitas_skill/skills/render.py`
- Modify: `src/infinitas_skill/install/distribution.py`
- Modify: `src/infinitas_skill/install/source_resolution.py`
- Modify: `src/infinitas_skill/install/target_validation.py`
- Modify: `src/infinitas_skill/install/install_manifest.py`
- Modify: `src/infinitas_skill/install/installed_integrity.py`
- Modify: `server/modules/release/materializer.py`
- Modify: `server/ui/routes/home.py`
- Delete: `scripts/backfill-distribution-manifests.py`
- Delete: `scripts/test-compat-regression.py`
- Delete: `scripts/test-install-manifest-compat.py`
- Delete: `scripts/test-legacy-distribution-backfill.py`
- Delete: `scripts/test-private-first-cutover-schema.py`
- Delete: `scripts/test-skill-meta-compat.py`
- Delete: legacy-only unit tests under `tests/unit/install/` and `tests/unit/skills/`
- Delete: compatibility-only fixtures under `catalog/distributions/_legacy/`

**Step 1: Write strict-schema tests**

Missing schema version, old skill layout, old install manifest, or `_legacy` distribution path must
fail with a typed validation error.

**Step 2: Remove adapters**

Delete `_legacy_*`, `load_legacy_*`, deprecated-field aliases, missing-version defaults, legacy copy,
and backfill branches. Do not replace them with warnings.

**Step 3: Remove compatibility redirects and aliases**

Delete `/v2` and any other route or command alias that has no current product purpose.

**Step 4: Verify terminology carefully**

Run:

```bash
rg -n -i "legacy|backward compatibility|backwards-compatible|re-export" server src tests scripts
```

Review every remaining match. Platform/runtime compatibility code is allowed; legacy format support
is not.

### Task 10: Collapse Scripts into the CLI and Tests into Pytest

**Files:**
- Modify: `scripts/check-all.sh`
- Modify: `Makefile`
- Modify: `.github/workflows/validate.yml`
- Modify: `src/infinitas_skill/registry/cli.py`
- Modify: `src/infinitas_skill/release/cli.py`
- Create: `src/infinitas_skill/server/cli.py`
- Modify: `src/infinitas_skill/policy/cli.py`
- Modify: `src/infinitas_skill/compatibility/checks.py`
- Create or extend pytest files under `tests/unit`, `tests/integration`, `tests/security`, and `tests/e2e`
- Delete: every remaining `scripts/test-*.py`
- Delete or migrate: remaining Python and shell scripts not included in the final whitelist below

**Step 1: Classify all 77 script tests**

Create a temporary checklist with three dispositions:

- migrate current unique behavior to pytest;
- delete because pytest already covers it;
- delete because it only tests removed compatibility behavior.

Process the scripts in these batches:

1. Governance/policy: `test-check-policy-packs.py`, `test-policy-*`, `test-review-governance.py`,
   `test-team-governance-scopes.py`, `test-namespace-identity.py`.
2. Install/discovery: `test-discovery-index.py`, `test-resolve-skill.py`, `test-install-by-name.py`,
   `test-skill-update.py`, `test-explain-install.py`, `test-recommend-skill.py`, `test-ai-*`.
3. Release/trust: `test-release-*`, `test-attestation-verification.py`,
   `test-transparency-log.py`, `test-signing-*`.
4. Hosted server/UI: `test-home-*`, `test-private-registry-*`, `test-hosted-*`,
   `test-server-ops.py`, `test-settings-hardening.py`.
5. Platform/export: `test-openclaw-*`, `test-codex-export.py`, `test-claude-export.py`,
   `test-platform-*`, `test-compatibility-evidence.py`.
6. Remaining inventory and integrity scripts.

**Step 2: Use RED-GREEN per migrated scenario**

For every script with unique current behavior, add a pytest test and run it before deleting the
script. The new test must fail if the script is temporarily hidden or its expected behavior is
removed.

**Step 3: Simplify `check-all.sh`**

Final script should run canonical commands only:

```bash
ruff check .
ruff format --check .
mypy src/infinitas_skill server
pytest tests/unit tests/integration tests/security tests/performance
pytest tests/e2e
alembic check
python scripts/generate-openapi.py --check
npm run build
```

Environment-dependent E2E may remain a separately required CI job, but not a Python shadow suite.

**Step 4: Move operational behavior into the installed CLI**

Migrate registry validation, catalog export, provenance/attestation generation and verification,
distribution manifest generation, signing checks, snapshot operations, server backup/restore,
integrity reporting, and release orchestration into their owning CLI domains. Delete the source
script immediately after its CLI command and tests pass.

The final `scripts/` top-level whitelist is:

```text
scripts/check-all.sh
scripts/generate-openapi.py
scripts/purgecss-run.js
scripts/build-asset-hashes.js
```

If an additional script is proposed, it must have a documented reason it cannot be an installed CLI
command, test, migration, or build step.

Delete `scripts/test_support/` after moving reusable fixtures to `tests/helpers/` or production
modules.

**Step 5: Verify deletion**

Run:

```bash
test "$(rg --files scripts | wc -l)" -le 4
test -z "$(rg --files scripts -g 'test-*.py')"
```

Expected: exit 0.

### Task 11: Replace Debt Budgets with Direct Quality Gates

**Files:**
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: `.github/workflows/validate.yml`
- Delete: `config/ruff-budgets.json`
- Delete: `scripts/check-ruff-budgets.py`
- Modify: `tests/integration/test_maintainability_budgets.py`

**Step 1: Add failing gate-contract tests**

Require full-repository Ruff, Ruff format check, strict production Mypy, combined coverage, Alembic,
OpenAPI, and frontend build in CI.

**Step 2: Remove all Ruff debt**

Run `ruff check .` and fix every result. Remove historical per-file ignores once their files pass.
Delete the budget checker only when direct Ruff passes.

**Step 3: Strengthen Mypy**

Set:

```toml
check_untyped_defs = true
disallow_untyped_defs = true
no_implicit_optional = true
warn_unused_ignores = true
```

Apply to production code. Tests may use a separate less-strict override if necessary.

**Step 4: Make coverage authoritative**

Run non-E2E suites in one process or combine parallel coverage data. Configure minimum line coverage
75% and branch coverage 60%. Delete stale coverage files before each run.

**Step 5: Verify GREEN**

Run all static gates and the combined non-E2E test suite.

### Task 12: Replace the Legacy Frontend CSS Layer

**Files:**
- Rewrite: `server/static/css/input.css`
- Modify: `tailwind.config.js`
- Modify: `server/templates/layout-kawaii.html`
- Modify: `server/templates/index-kawaii.html`
- Modify: `server/templates/manage.html`
- Modify: `server/templates/object-detail.html`
- Modify: `server/templates/release-detail-v2.html`
- Modify: `server/templates/profile.html`
- Modify: `server/templates/settings.html`
- Modify: `server/templates/login-kawaii.html`
- Modify: `server/templates/partials/home-hero.html`
- Modify: `server/templates/partials/home-console.html`
- Test: `tests/unit/governance/test_visual_intensity_contract.py`
- Test: `tests/integration/test_private_registry_ui.py`

**Step 1: Update the failing visual architecture contract**

Require CSS under 1,000 lines, zero `transition: all`, zero legacy design-system comment, and no
unused glow/candy/neon tokens. Preserve focus-visible, reduced-motion, dark-mode, and responsive
contracts.

**Step 2: Define one compact token palette**

Keep semantic colors, typography, spacing, radius, and shadow tokens. Remove duplicate RGB aliases
unless Tailwind requires them.

**Step 3: Move page styling to utilities**

Retain semantic component classes only for repeated interactive behavior such as buttons, inputs,
tabs, cards, tables, modals, and toasts.

**Step 4: Verify accessibility and build**

Run static UI contracts, Playwright E2E in an environment that permits it, and `npm run build`.

### Task 13: Final Documentation and Repository Cleanup

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/reference/testing.md`
- Modify: `docs/reference/api-reference.md`
- Modify: `docs/reference/metadata-schema.md`
- Modify: `docs/reference/install-manifest-format.md`
- Modify: `docs/guide/private-first-cutover.md` or delete if no longer current
- Modify: `docs/audits/2026-07-13-project-refactor-audit.md`
- Delete: obsolete compatibility, migration, and cutover documentation discovered by governance tests

**Step 1: Rewrite architecture guidance**

Document the domain ownership map, transaction rule, lifecycle rule, API/UI read-model boundary,
single schema, single migration, and pytest-only test policy.

**Step 2: Remove compatibility language**

Delete documentation for legacy formats, backfills, old routes, old commands, and upgrade paths that
no longer exist.

**Step 3: Run the full closeout matrix**

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/infinitas_skill server
.venv/bin/pytest tests/unit tests/integration tests/security tests/performance
.venv/bin/pytest tests/e2e
.venv/bin/pytest tests/integration/test_alembic_metadata.py -q --override-ini=addopts=
.venv/bin/python scripts/generate-openapi.py --check
npm run build
git diff --check
```

**Step 4: Confirm completion criteria**

Re-run `tests/unit/governance/test_clean_architecture_contract.py` and the maintainability tests.
Every target in the design document must pass without exclusions, budgets, or compatibility shims.
