# Refactor Audit Remediation Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for every behavior change and superpowers:verification-before-completion before closing each task.

**Goal:** Resolve the verified high- and medium-priority defects from the 2026-07-13 refactor audit without disturbing unrelated work already present in the dirty worktree.

**Architecture:** Preserve the dual-consumer split between browser sessions and Agent/CLI credentials. Remove model import cycles through a dependency-free model base, align ORM metadata to the existing migration head, and make generators/tests deterministic and side-effect bounded. Historical migrations remain immutable unless a verified upgrade-path defect requires otherwise.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, pytest, Ruff, Mypy, shell/CI, Tailwind/PurgeCSS.

---

### Task 1: Separate Browser and Agent Credentials

**Files:**
- Modify: `server/db.py`
- Modify: `server/api/auth.py`
- Modify: `server/modules/access/service.py`
- Test: `tests/integration/test_api_endpoints.py`
- Test: `tests/integration/test_db_utils.py`

**Steps:**
1. Add a failing bootstrap test proving an auto-generated token is stored and resolves.
2. Add a failing restart test proving an existing generated token is not rotated.
3. Add a failing login test proving browser login does not revoke an Agent bearer token.
4. Run the three tests and confirm the audited failures.
5. Store the generated token value, generate it only when no personal credential exists, and distinguish browser credentials as `session`.
6. Retain compatibility for legacy `personal_token` session placeholders identified by `session:` hashes.
7. Run focused auth/database tests and the security suite.

### Task 2: Harden Hosted Restore Extraction

**Files:**
- Modify: `scripts/rehearse-hosted-restore.py`
- Test: `tests/unit/server_ops/test_restore_safety.py`

**Steps:**
1. Add failing traversal, absolute-path, symlink, and hardlink archive tests.
2. Confirm the unsafe archives escape or are accepted by the current extractor.
3. Add a member validator compatible with Python 3.11 and extract only validated members.
4. Run restore safety tests and existing hosted restore tests.

### Task 3: Remove Model Import Cycles

**Files:**
- Create: `server/model_base.py`
- Modify: `server/models.py`
- Modify: `server/modules/*/models.py`
- Modify: `server/rate_limit.py`
- Test: `tests/unit/server/test_model_imports.py`

**Steps:**
1. Add subprocess smoke tests importing each domain model entry from a clean interpreter.
2. Confirm direct `server.modules.access.authz` import fails.
3. Move `Base` and `utcnow` into the dependency-free model base.
4. Point all domain models to the new base while preserving `server.models` compatibility exports.
5. Run standalone unit collection and server integration tests.

### Task 4: Align ORM and Migration Metadata

**Files:**
- Modify: `server/models.py`
- Modify: `server/modules/access/models.py`
- Modify: `server/modules/authoring/models.py`
- Modify: `server/modules/exposure/models.py`
- Modify: `server/modules/release/models.py`
- Modify: `server/modules/review/models.py`
- Test: `tests/integration/test_alembic_metadata.py`

**Steps:**
1. Add a failing isolated test running `alembic upgrade head` and `alembic check`.
2. Declare the migration-head composite indexes in ORM metadata and remove unintended implicit single-column indexes.
3. Mark the release-to-artifact constraints for deferred sorting to remove the metadata cycle warning.
4. Re-run `alembic check` and migration upgrade/downgrade boundary tests.

### Task 5: Repair Pagination and Test Isolation

**Files:**
- Modify: `tests/performance/test_pagination.py`
- Modify: `tests/conftest.py`
- Modify: `Makefile`
- Modify: `.github/workflows/validate.yml`

**Steps:**
1. Replace the deleted pagination helper assertion with a real FastAPI validation contract test.
2. Add environment restoration to shared test fixtures.
3. Run unit, integration, security, and performance suites as independent processes.
4. Change CI targets to collect maintained groups rather than relying on import order.
5. Add Alembic metadata validation to CI.

### Task 6: Make OpenAPI Generation Deterministic

**Files:**
- Modify: `scripts/generate-openapi.py`
- Modify: `server/app.py`
- Modify: `.gitignore`
- Test: `tests/unit/server_ops/test_openapi_generation.py`

**Steps:**
1. Add failing tests for `--check`, no-write behavior, and hostile inherited environment.
2. Add a schema-only application construction path without database startup effects.
3. Generate in memory, compare for `--check`, and write only in generation mode.
4. Make the tracked/ignored OpenAPI policy consistent and add the check to CI.

### Task 7: Reduce Build and Lint Debt

**Files:**
- Modify: `package.json`
- Modify: `.gitignore`
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: focused files reported by Ruff

**Steps:**
1. Move PurgeCSS intermediate output under ignored `build/` state.
2. Verify `npm run build` no longer changes the intermediate tracked file.
3. Split Ruff gates by maintained code, migrations, scripts, and tests with non-growing baselines.
4. Fix functional Ruff findings (`F`, unsafe `S`) before formatting-only debt.
5. Run final Ruff, Mypy, migration, test, and frontend build verification.

### Task 8: Update Audit Status

**Files:**
- Modify: `docs/audits/2026-07-13-project-refactor-audit.md`

**Steps:**
1. Mark resolved findings with exact verification evidence.
2. Leave environment-blocked E2E and vulnerability database checks explicitly unverified.
3. Record any intentionally deferred visual redesign or bulk formatting debt.
