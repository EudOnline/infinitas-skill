---
audience: contributors, reviewers, operators
owner: repository maintainers
source_of_truth: pytest and repository quality gates
last_reviewed: 2026-07-14
status: maintained
---

# Testing

All automated behavior tests live under `tests/` and run through pytest. Top-level scripts are build or verification infrastructure, not a second test framework.

## Everyday workflow

```bash
uv sync --all-groups
make ci-fast
```

For a focused change, run the smallest relevant pytest module first, then run the complete gate before declaring completion.

```bash
.venv/bin/pytest tests/unit/discovery/test_ai_index_validation.py -q --override-ini=addopts=
.venv/bin/pytest tests/integration/test_cli_install_workflows.py -q --override-ini=addopts=
```

`--override-ini=addopts=` disables repository coverage flags for a fast focused run. It must not be used for the authoritative coverage result.

## Test groups

| Group | Purpose |
|---|---|
| `tests/unit` | Pure domain logic, parser contracts, governance and static architecture checks |
| `tests/integration` | CLI workflows, database behavior, API/UI assembly and generated contracts |
| `tests/security` | Authentication, authorization, CSRF, rate limiting and archive safety |
| `tests/performance` | Pagination and query-count/performance contracts |
| `tests/e2e` | Live server and browser behavior |

The non-E2E suite is run as one coverage authority:

```bash
.venv/bin/pytest tests/unit tests/integration tests/security tests/performance --cov-fail-under=64
```

Coverage is branch-aware. `scripts/check-all.sh` applies `--cov-fail-under=64` to
the combined non-E2E run; focused runs must use
`--override-ini=addopts=`. The release target remains 75% line coverage and 60%
branch coverage, and the enforced floor should only move upward as tests are
added. Remove stale `.coverage*` files before diagnosing a discrepancy.

## Static gates

```bash
make lint-maintained
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/infinitas_skill server
git diff --check
```

Mypy is strict for production code: every production function is typed, implicit optional values are rejected, and unused ignores fail the gate.

## Architecture and maintainability

```bash
.venv/bin/pytest tests/unit/governance/test_clean_architecture_contract.py -q --override-ini=addopts=
.venv/bin/pytest tests/integration/test_maintainability_budgets.py -q --override-ini=addopts=
```

These tests enforce:

- no production import cycles or central model module;
- no UI-to-API coupling or project-internal adapters;
- one initial Alembic migration;
- production modules at or below 600 lines;
- production functions at or below 100 lines;
- `server/static/css/input.css` at or below 1000 lines;
- exactly four top-level build/verification scripts.

## Database and generated contracts

```bash
.venv/bin/pytest tests/integration/test_alembic_metadata.py -q --override-ini=addopts=
.venv/bin/python scripts/generate-openapi.py --check
npm run build
```

The Alembic test is the authoritative migration gate: it creates an empty
database, upgrades to `head`, runs `alembic check` against that migrated temporary
database, downgrades to `base`, and verifies that application tables are gone.
This avoids coupling release readiness to a developer's local database state.
OpenAPI check generates the schema without entering application lifespan or
writing a database.

## Complete closeout

```bash
./scripts/check-all.sh
```

Equivalent explicit matrix:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/infinitas_skill server
.venv/bin/pytest tests/unit tests/integration tests/security tests/performance --cov-fail-under=64
.venv/bin/pytest tests/e2e
.venv/bin/pytest tests/integration/test_alembic_metadata.py -q --override-ini=addopts=
.venv/bin/python scripts/generate-openapi.py --check
.venv/bin/pip-audit --cache-dir "$(mktemp -d)" --progress-spinner=off
npm audit --registry=https://registry.npmjs.org --audit-level=high
npm run build
git diff --check
```

## Environment notes

CI uses Python 3.11. Some Python 3.13 environments can block synchronous FastAPI `TestClient` worker-thread execution; a test that produces no assertion output and never returns should be rechecked under Python 3.11 before changing application behavior. Browser E2E also requires permission to bind a local socket and an installed Playwright browser.
