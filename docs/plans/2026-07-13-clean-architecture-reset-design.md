# Infinitas Skill Clean Architecture Reset Design

**Date:** 2026-07-13  
**Status:** Validated  
**Audience:** Maintainers implementing the pre-release cleanup

## 1. Context

The project has not been released and has no external backward-compatibility obligation. Existing
development databases, local artifacts, Alembic history, legacy manifests, old schema variants,
internal import paths, and shadow test entrypoints may be deleted. The cleanup therefore optimizes
for one canonical architecture instead of preserving migration intermediates.

Platform compatibility remains a product capability. Code that evaluates whether a skill supports
OpenClaw, Codex, Claude, or another runtime is not legacy compatibility and must remain. What is
removed is backward compatibility with superseded project-internal formats and entrypoints.

## 2. Design Goals

1. One authoritative module for every domain concept.
2. No internal re-exports, aliases, compatibility shims, or legacy loaders.
3. No import-time database migration or bootstrap side effects.
4. One transaction boundary for each HTTP request or background use case.
5. UI and JSON API share application read models, but neither imports the other.
6. One CLI entrypoint and one pytest-based test system.
7. One clean initial database migration.
8. Full-repository Ruff and Mypy gates without debt budgets.
9. Small orchestration modules with explicit dependencies.
10. A smaller frontend design system without legacy CSS layers.

## 3. Selected Approach

Use an in-place hard reset. Preserve current intended behavior and security properties, but replace
the internal structure directly. Do not introduce temporary adapters unless required within a single
task to keep tests runnable; any such adapter must be deleted in the same task.

An incremental compatibility migration was rejected because it would retain the exact re-exports,
legacy parsers, migrations, scripts, and dual test topology that the cleanup is intended to remove.
A separate rewrite was rejected because it would risk losing verified release, policy, signing,
authentication, and registry behavior.

## 4. Target Backend Structure

```text
server/
  app.py                    # create_app() and ASGI app only
  lifecycle.py              # startup/shutdown orchestration
  settings.py
  db.py                     # engine, session factory, request transaction
  model_base.py             # Base and utcnow only
  model_registry.py         # imports model modules for Alembic; exports nothing
  exceptions.py
  middleware.py
  modules/
    system/
      router.py
    identity/
      models.py             # User, Principal, Credential, teams
      schemas.py
      repository.py
      service.py
      router.py             # login, logout, profile, credentials
    access/
      models.py             # grants and access policy records
      schemas.py
      repository.py
      service.py
      router.py             # object tokens and share links
    authoring/
    release/
    exposure/
    review/
    discovery/
    registry/
    audit/
    jobs/
      models.py
      repository.py
      service.py
    library/
      queries.py            # UI/API-neutral SQL queries
      read_models.py        # typed projections
      service.py
      router.py
  ui/
    routes/
      home.py
      library.py
      profile.py
      settings.py
    context.py
    navigation.py
    i18n.py
```

`server/api/` is removed. API routers belong to their domains. Domain `__init__.py` files remain
empty and never import routers or models. `server.models` is deleted. All consumers import the model
from its owning domain.

## 5. Application Lifecycle and Transactions

`create_app(settings=None)` constructs the application without touching the database. FastAPI
lifespan performs database readiness checks and optional development bootstrap. Schema generation
uses the same factory without entering lifespan.

`get_db()` owns the HTTP transaction:

- yield one session;
- commit after a successful request;
- roll back on an exception;
- always close the session.

Repositories may query, add, and flush. Domain services may coordinate repositories but may not
commit or roll back. Background workers use an explicit `session_scope()` context manager with the
same semantics. This removes the current mixture of commits in routers and services and makes
multi-domain operations atomic.

## 6. Model and Migration Reset

Move `User` and identity-related records into `modules/identity/models.py`; move `Job` into
`modules/jobs/models.py`. Each remaining domain owns its ORM models. `model_registry.py` imports all
model modules only so Alembic can populate `Base.metadata`; it has no public model facade.

Delete every existing file under `alembic/versions/` and generate one `0001_initial.py` from the clean
metadata. Delete local development databases and generated database state. The initial migration
must support both upgrade from an empty database and downgrade back to an empty database.

No migration contains legacy rename, copy, backfill, cutover, or drop-after-copy logic.

## 7. UI and API Boundary

Move library queries, aggregation, and projection building from `server/ui/library_*` into
`server/modules/library`. Both HTML routes and JSON routes consume typed read models from that
module. UI modules only select templates, localize labels, and assemble presentation context.

The JSON API never imports `server.ui`. UI routes may import domain services and read models but do
not call JSON endpoints internally.

Split the current `register_ui_routes()` into page-specific router modules. `app.py` includes each UI
router explicitly, just as it includes domain API routers.

## 8. CLI Structure

```text
src/infinitas_skill/
  cli/main.py               # parser root and registrar loop only
  install/
    cli.py                  # install command registration
    common.py
    exact.py
    resolve.py
    sync.py
    update.py
    switch.py
    rollback.py
    upgrade.py
  release/
    cli.py
  policy/
    cli.py
  registry/
    cli.py
  discovery/
    cli.py
  server/
    cli.py
```

Delete `install/workflows.py` and `install/workflows_parsers.py`. Each command module owns its parser
configuration and handler. `cli/main.py` imports one registrar per domain rather than every command
function. No command is dynamically imported from `scripts/`, and no internal parser function is
re-exported.

## 9. Compatibility Deletion Policy

Delete code whose purpose is any of the following:

- accepting a missing or superseded schema version;
- loading legacy `SKILL.md + _meta.json` layouts when the canonical format is required;
- resolving `_legacy` distribution paths;
- backfilling old manifests;
- retaining old command names, endpoint aliases, redirects, or import paths;
- copying legacy entries during rendering;
- re-exporting a function after it moved modules;
- testing removed compatibility behavior.

Keep code that evaluates current platform/runtime compatibility, current policy compatibility, or
current install constraints.

All current schemas become strict. Required version fields must be present and equal the single
supported version. Invalid older data fails with a concise validation error instead of being adapted.

## 10. Tests and Quality Gates

All automated tests live under `tests/` and run through pytest. Delete every `scripts/test-*.py` file.
Migrate unique current-behavior scenarios before deletion; delete scenarios that only prove legacy
behavior.

The normal test matrix is:

```text
pytest tests/unit
pytest tests/integration
pytest tests/security
pytest tests/performance
pytest tests/e2e
```

The non-E2E suites also run once in a combined process to produce a single coverage report. Start
with line coverage 75% and branch coverage 60%; raise the target after script-test migration. Add a
clean-interpreter import graph test and fail on every strongly connected component.

Final static gates:

- `ruff check .` with no debt budget file;
- `ruff format --check .`;
- Mypy with `check_untyped_defs=true`, followed by `disallow_untyped_defs=true` for production code;
- one Alembic initial migration and clean `alembic check`;
- deterministic OpenAPI check;
- frontend build and generated-asset consistency check.

## 11. Scripts and Operations

Scripts are allowed only when they are executable operational artifacts that do not belong in the
installed CLI. Prefer adding a CLI command and deleting the wrapper. Target fewer than 20 scripts,
zero `test-*.py` scripts, and zero `sys.path` mutation.

`scripts/check-all.sh` becomes a thin sequence of canonical commands rather than an alternate test
framework. The final top-level scripts are limited to `check-all.sh`, `generate-openapi.py`,
`purgecss-run.js`, and `build-asset-hashes.js`. Release, repair, signing, validation, snapshot, backup,
and integrity operations become installed CLI commands.

## 12. Frontend Cleanup

Retain server-rendered HTML and native ES modules. Do not add a frontend framework. Replace the
3,000-line legacy CSS layer with one compact Tailwind input containing tokens and a small set of
semantic components. Remove unused glow, candy, neon, legacy theme, and duplicated dark-mode rules.

Targets:

- source CSS under 1,000 lines;
- no `transition: all`;
- no decorative `backdrop-filter`;
- colors expressed through one token palette;
- page-specific styling expressed primarily through Tailwind utilities;
- existing keyboard, focus trap, reduced-motion, responsive, and dark-mode behavior retained.

## 13. Error Handling

Use one domain exception hierarchy in `server/exceptions.py`. Domain services raise typed exceptions;
routers translate them through shared exception handlers rather than repeating `try/except` blocks in
every endpoint. CLI commands return a shared result/error type that renders JSON or human-readable
output at the outer boundary.

Do not catch broad exceptions unless adding context and re-raising, rolling back a transaction at the
outer boundary, or converting an external-process failure into a typed domain error.

## 14. Completion Criteria

- One Alembic migration.
- Zero imports from `server.models`; file deleted.
- Zero production imports from `server.ui` outside UI route modules.
- Zero eager router/model imports in package `__init__.py` files.
- Zero import cycles.
- Zero internal backward-compatibility re-exports.
- Zero `scripts/test-*.py` files.
- Zero `sys.path` mutation outside isolated test bootstrap code; target zero everywhere.
- Full Ruff pass without budgets and without broad directory ignores.
- Mypy checks bodies of all production functions.
- One authoritative coverage report with enforced thresholds.
- No production function over 100 lines; target 80 lines.
- No production module over 600 lines; target 500 lines.
- CSS source under 1,000 lines.
- Unit, integration, security, performance, Alembic, OpenAPI, and frontend gates pass.
