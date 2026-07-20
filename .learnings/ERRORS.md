# Errors

## [ERR-20260719-006] concurrency-hardening-migration-context

**Logged**: 2026-07-19T14:30:00+00:00
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

A combined concurrency-hardening patch failed because the initial migration table order did
not match the assumed context.

### Error

```text
apply_patch verification failed: Failed to find expected lines in alembic/versions/0001_initial.py
```

### Context

- The patch combined ORM models, services, and migration edits.
- The migration defines review policies near the beginning and review cases later.
- The patch was rejected atomically; no partial concurrency change was applied.

### Suggested Fix

Apply model, service, and migration changes as separate exact-context patches.

### Metadata

- Reproducible: yes
- Related Files: alembic/versions/0001_initial.py
- See Also: ERR-20260719-002

### Resolution

- **Resolved**: 2026-07-19T14:30:00+00:00
- **Notes**: Re-read exact migration sections and split the patch by concern.

---

## [ERR-20260720-001] coolify-runtime-smoke-image-build

**Logged**: 2026-07-20T10:58:00+00:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary

The optional local Coolify topology smoke test could not reach container startup because the
runtime image build stalled while downloading Debian package indexes.

### Error

```text
[runtime 2/6] RUN apt-get ...
Get:4 http://deb.debian.org/debian trixie/main amd64 Packages [9673 kB]
ERROR: failed to build: failed to solve: Canceled: context canceled
```

### Context

- Command: `docker build -t infinitas-coolify-audit:local .`
- The build was manually canceled after the Debian package-index download made no progress for
  more than four minutes.
- The Compose file had already passed `docker compose config`, all deployment/documentation
  governance tests, and the complete repository quality gate.
- No test containers or named volumes were created.

### Suggested Fix

Retry the image smoke test when the Debian mirror is responsive, or rely on the existing CI
multi-architecture image build and container health smoke for publication. Consider a controlled
APT mirror only if this becomes recurrent in CI.

### Metadata

- Reproducible: unknown
- Related Files: Dockerfile, docker-compose.coolify.yml

### Resolution

- **Resolved**: 2026-07-20T14:07:00+00:00
- **Notes**: Built a current-code audit image on the published dependency-complete runtime
  base, then completed app, worker, registry, login, backup, and restore-rehearsal smoke tests.
  The normal Dockerfile build remains covered by the required CI image publication job.

---

## [ERR-20260720-002] hosted-compose-runtime-boundaries

**Logged**: 2026-07-20T14:07:00+00:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary

The first Coolify topology smoke exposed bootstrap import, production health-probe, and hosted
registry path drift that static Compose validation did not detect.

### Error

```text
ModuleNotFoundError: No module named 'server'
ssl.SSLError: [SSL: WRONG_VERSION_NUMBER] wrong version number
HTTP Error 400: Bad Request
GET /registry/ai-index.json -> 404
```

### Context

- Compose changes the working directory from the image bundle to the writable runtime repo.
- Production enables HTTPS redirect and trusted-host validation, while the original internal
  readiness probe sent plain HTTP with `Host: 127.0.0.1`.
- Maintained docs described `/registry/*`, but the current router is
  `/api/v1/registry/*`.
- App and worker did not share one explicit runtime-repo-first Python module path.

### Suggested Fix

Keep runtime smoke coverage for new deployment templates. The smoke must use production mode,
a real allowed hostname, a registry read token, fresh named volumes, app readiness, worker
heartbeat, browser login, hosted index fetch, backup, and restore rehearsal.

### Metadata

- Reproducible: yes
- Related Files: docker/entrypoint-hosted.sh, docker-compose.yml,
  docker-compose.coolify.yml, docs/ops/coolify-deployment.md

### Resolution

- **Resolved**: 2026-07-20T14:07:00+00:00
- **Notes**: Unified PYTHONPATH across bootstrap/app/worker, made readiness proxy- and
  trusted-host-aware, corrected hosted registry URLs to `/api/v1/registry`, added regression
  assertions, and completed the full fresh-volume runtime smoke successfully.

---

## [ERR-20260720-003] ci-local-only-registry-origin-drift

**Logged**: 2026-07-20T14:23:00+00:00
**Priority**: high
**Status**: resolved
**Area**: tests

### Summary

The first post-push CI run failed because generated local-only registry exports depended on the
checkout's Git remote transport.

### Error

```text
FAILED tests/integration/test_cli_registry_local_ops.py::test_registry_catalog_build_check_is_stable
changed: ["registries.json", "inventory-export.json"]
```

### Context

- Developer checkout origin: SSH alias URL.
- GitHub Actions checkout origin: HTTPS URL.
- `stable_catalog_identity` removed commit, tag, and branch for `local-only`, but retained the
  environment-derived origin URL.

### Suggested Fix

Generated artifacts for a local-only self registry must use the URL declared in
`config/registry-sources.json`, never checkout-specific Git remote state.

### Metadata

- Reproducible: yes
- Related Files: src/infinitas_skill/registry/catalog_entries.py,
  catalog/registries.json, catalog/inventory-export.json

### Resolution

- **Resolved**: 2026-07-20T14:23:00+00:00
- **Notes**: Canonicalized `registry_origin_url` from registry configuration, regenerated both
  exports, and added a transport-independent unit regression test.

---

## [ERR-20260719-007] full-quality-gate-architecture-budgets

**Logged**: 2026-07-19T12:00:00Z
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary

The full quality gate found a domain package facade import and a 109-line production function after the hardening changes.

### Error

```text
server/worker.py: from server.modules.release import service
server/modules/exposure/service.py create_exposure: 109 lines
```

### Context

- Focused Ruff, mypy, and regression tests passed before the repository-wide architecture and maintainability contracts ran.
- Project hard gates require direct domain submodule imports and production functions no longer than 100 lines.

### Suggested Fix

Run repository governance and maintainability tests before the full suite, and extract focused helpers as soon as lifecycle hardening expands a boundary function.

### Metadata

- Reproducible: yes
- Related Files: server/worker.py, server/modules/exposure/service.py

### Resolution

- **Resolved**: 2026-07-19T12:05:00Z
- **Notes**: Imported `get_release_snapshot` directly and extracted Exposure policy/persistence helpers; the focused hard gates now pass.

---

## [ERR-20260719-005] lifecycle-audit-import-order

**Logged**: 2026-07-19T14:20:00+00:00
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

The first lifecycle audit-event patch introduced three Ruff import-order violations.

### Error

```text
I001 Import block is un-sorted or un-formatted
```

### Context

- Direct domain-module imports were added beside existing imports.
- No runtime behavior or repository state was affected.

### Suggested Fix

Keep direct module imports alphabetically ordered and run focused Ruff checks immediately
after cross-domain instrumentation changes.

### Metadata

- Reproducible: yes
- Related Files: server/modules/authoring/service.py, server/modules/exposure/service.py,
  server/modules/review/service.py

### Resolution

- **Resolved**: 2026-07-19T14:20:00+00:00
- **Notes**: Reordered direct module imports before continuing the implementation.

---

## [ERR-20260717-002] pip-audit-corrupt-http-cache

**Logged**: 2026-07-17T00:10:00Z
**Priority**: medium
**Status**: resolved
**Area**: supply-chain

### Summary

The post-merge quality gate reached `pip-audit` after all code and browser tests
passed, then failed while deserializing a stale HTTP cache entry and parsing a
non-JSON PyPI response.

### Error

```text
WARNING: cache entry deserialization failed, entry ignored
requests.exceptions.JSONDecodeError: Expecting value: line 1 column 1
```

### Suggested Fix

Run release audits with a fresh temporary HTTP cache so host-level cache corruption
cannot make the repository gate nondeterministic.

### Resolution

- **Resolved**: 2026-07-17T00:10:00Z
- **Notes**: `check-all.sh` now creates and removes an isolated pip-audit cache.

---

## [ERR-20260719-004] profile-exclude-none-and-rate-limit-boundary-regressions

**Logged**: 2026-07-19T11:15:00+00:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary

The full test suite exposed an over-broad response exclusion and a minute-boundary gap in
the database login rate limiter.

### Error

```text
4 failed, 1231 passed
```

### Context

- Route-level `response_model_exclude_none=True` removed contractually present null fields
  from the entire profile response instead of only omitting unset policy members.
- Database rate-limit records were rounded to minute buckets, so a sliding-window query
  could forget attempts made immediately before the next minute.

### Suggested Fix

Apply null omission at the nested policy serializer and store login limiter records in
one-second buckets for accurate sliding-window checks.

### Metadata

- Reproducible: boundary-dependent
- Related Files: server/modules/identity/profile_schemas.py, server/rate_limit.py

### Resolution

- **Resolved**: 2026-07-19T11:15:00+00:00
- **Notes**: Preserved top-level nullable API fields, added a focused policy serializer,
  and added a regression test spanning a minute boundary.

---

## [ERR-20260719-001] unavailable-jsonschema-test-dependency

**Logged**: 2026-07-19T09:41:33+00:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

A new schema syntax test imported `jsonschema`, which is not a project dependency.

### Error

```text
ModuleNotFoundError: No module named 'jsonschema'
```

### Context

- The test only needed to catch invalid JSON syntax and assert two contract shapes.
- Adding a runtime or test dependency for that narrow check would unnecessarily expand the lockfile.

### Suggested Fix

Use the standard-library JSON parser and explicit contract assertions unless full JSON Schema validation is already part of the dependency set.

### Metadata

- Reproducible: yes
- Related Files: tests/unit/discovery/test_ai_index_schema.py, schemas/ai-index.schema.json

### Resolution

- **Resolved**: 2026-07-19T09:41:33+00:00
- **Notes**: Replaced the unavailable dependency with `json.loads` plus focused schema-shape assertions.

---

## [ERR-20260717-007] apply-patch-font-config-context

**Logged**: 2026-07-17T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: config

### Summary

A Tailwind font configuration patch failed because it was built from search output instead of the exact current file context.

### Error

```text
apply_patch verification failed: Failed to find expected lines in tailwind.config.js
```

### Context

- The intended change was correct, but the patch omitted the existing `mono` entry and did not first read the exact block.
- No repository content was changed by the failed patch.

### Suggested Fix

Read the exact target block before applying a contextual patch, especially in configuration files with adjacent entries.

### Metadata

- Reproducible: yes
- Related Files: tailwind.config.js
- See Also: exact-context patch guidance already recorded in this file

### Resolution

- **Resolved**: 2026-07-17T00:00:00Z
- **Notes**: Re-read the exact block and applied a context-accurate patch.

---

## [ERR-20260717-008] tailwind-bundled-browserslist-warning

**Logged**: 2026-07-17T07:35:00Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

Updating `caniuse-lite` succeeded, but Tailwind 3.4 still emitted an outdated-data warning from its bundled fallback dependency snapshot.

### Error

```text
Browserslist: caniuse-lite is outdated. Please run:
  npx update-browserslist-db@latest
```

### Context

- The lockfile and local external dependency both resolved to `caniuse-lite@1.0.30001806`.
- Browserslist's latest recorded browser release was only 15 days old.
- The stale warning string came from `tailwindcss/peers/index.js`; the CLI still resolved the project's current external Autoprefixer for CSS processing.

### Suggested Fix

Keep the external Browserslist data current and suppress only Tailwind 3's stale bundled fallback warning during its build/watch commands.

### Metadata

- Reproducible: yes
- Related Files: package.json, package-lock.json

### Resolution

- **Resolved**: 2026-07-17T07:35:00Z
- **Notes**: Updated the lockfile and set `BROWSERSLIST_IGNORE_OLD_DATA=1` only around Tailwind CLI commands.

---

## [ERR-20260717-009] system-python314-missing-test-dependencies

**Logged**: 2026-07-17T07:40:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The first Python 3.14 compatibility test used the system interpreter, whose distro packages lacked `httpx` required by the repository test bootstrap.

### Error

```text
RuntimeError: The starlette.testclient module requires the httpx package to be installed.
```

### Context

- The failure occurred while importing `tests/conftest.py`, before the tar extraction test ran.
- The project environment remained unchanged.

### Suggested Fix

Run cross-version checks in an isolated environment populated from the project lockfile instead of relying on system Python packages.

### Metadata

- Reproducible: yes
- Related Files: tests/unit/install/test_distribution_materialization.py, uv.lock

### Resolution

- **Resolved**: 2026-07-17T07:40:00Z
- **Notes**: Switched the compatibility check to a temporary uv-managed Python 3.14 environment.

---

## [ERR-20260717-006] skill-creator-validator-missing-pyyaml-in-project-venv

**Logged**: 2026-07-17T06:00:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The external `skill-creator` quick validator could not start in the project venv because PyYAML
is not a project dependency.

### Error

```text
ModuleNotFoundError: No module named 'yaml'
```

### Context

- Command: `.venv/bin/python .../skill-creator/scripts/quick_validate.py skills/active/...`
- The validator is environment-owned and imports PyYAML; the project runtime does not need that
  dependency.

### Suggested Fix

Run the environment-owned validator with an interpreter that already provides its dependencies,
without adding an unrelated dependency to the project lockfile.

### Metadata

- Reproducible: yes
- Related Files: skills/active/*/SKILL.md

### Resolution

- **Resolved**: 2026-07-17T06:01:00Z
- **Notes**: Re-ran the validator with `/usr/bin/python3`, which provides PyYAML 6.0.3.

---

## [ERR-20260717-003] ad-hoc-testclient-missed-lifespan

**Logged**: 2026-07-17T01:32:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

An ad-hoc audit reproduction instantiated the integration client without entering the repository's lifespan-aware test wrapper, so the temporary database was not migrated.

### Error

```text
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: credentials
```

### Context

- The diagnostic reused integration helpers outside pytest.
- The repository patches `fastapi.testclient.TestClient` through `tests/conftest.py`; importing helpers alone does not reproduce pytest fixture and lifespan setup.
- No repository runtime state was changed because the script used a temporary directory.

### Suggested Fix

For ad-hoc API diagnostics, either run a temporary pytest case under the repository test harness or explicitly enter the lifespan-aware client as a context manager after applying the same cache/environment setup.

### Metadata

- Reproducible: yes
- Related Files: tests/conftest.py, tests/helpers/test_client.py, tests/integration/conftest.py

### Resolution

- **Resolved**: 2026-07-17T01:32:00Z
- **Notes**: Stopped using the incomplete reproduction path and switched to transaction-level and test-harness-backed evidence.

---

## [ERR-20260717-004] zsh-backtick-regex-expansion

**Logged**: 2026-07-17T01:37:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

A shell diagnostic embedded a backtick in a double-quoted regular expression, causing zsh command-substitution parsing before `rg` could run.

### Error

```text
zsh:1: unmatched '
zsh:1: parse error in command substitution
```

### Context

- The intended read-only command searched JavaScript string literals for API paths.
- No repository state was changed.

### Suggested Fix

Avoid backticks in shell command strings passed through the command runner; use simpler single-purpose `rg` patterns or escape via a file-backed pattern when matching JavaScript template literals is necessary.

### Metadata

- Reproducible: yes
- Related Files: server/static/js/

### Resolution

- **Resolved**: 2026-07-17T01:37:00Z
- **Notes**: Replaced the combined expression with safe literal searches.

---

## [ERR-20260717-005] artifact-list-response-wrapper

**Logged**: 2026-07-17T01:43:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

An ad-hoc artifact audit treated the release artifact response object as a bare list instead of reading its `items` field.

### Error

```text
TypeError: string indices must be integers, not 'str'
```

### Context

- Release materialization completed successfully.
- The temporary diagnostic diverged from the endpoint's `ArtifactListView` response model.

### Suggested Fix

Inspect or reuse the endpoint response model before writing one-off API diagnostics, especially for list endpoints that return pagination wrappers.

### Metadata

- Reproducible: yes
- Related Files: server/modules/release/schemas.py, server/modules/release/router.py

### Resolution

- **Resolved**: 2026-07-17T01:43:00Z
- **Notes**: Updated the temporary diagnostic to read `response.json()["items"]`.

---

## [ERR-20260717-001] staged-diff-check-did-not-gate-commit

**Logged**: 2026-07-17T00:00:00Z
**Priority**: medium
**Status**: resolved
**Area**: git

### Summary

A multi-line commit command ran `git commit` after `git diff --cached --check`
reported Markdown whitespace because the commands were separated by newlines rather
than chained with `&&`.

### Error

```text
trailing whitespace
new blank line at EOF
```

### Suggested Fix

Chain pre-commit verification and commit with `&&`, or run them as separate tool calls
and inspect the first result before committing.

### Resolution

- **Resolved**: 2026-07-17T00:00:00Z
- **Notes**: Removed the whitespace and added a dedicated hygiene follow-up commit.

---

## [ERR-20260716-004] nullable-release-object-scope

**Logged**: 2026-07-16T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

Mypy rejected passing nullable `Release.skill_id` into a strict product-token scope guard.

### Error

```text
Argument 2 to "_require_product_object_scope" has incompatible type "int | None";
expected "int"
```

### Context

- Current releases should carry a skill ID, but the ORM annotation remains nullable.
- Authorization code must fail closed if malformed release metadata reaches the boundary.

### Suggested Fix

Accept `int | None` in the guard and treat `None` as a scope mismatch.

### Metadata

- Reproducible: yes
- Related Files: server/modules/release/router.py

### Resolution

- **Resolved**: 2026-07-16T00:00:00Z
- **Notes**: The product-token object guard now fails closed for null object IDs.

---
## [ERR-20260716-012] global-coverage-floor-breaks-e2e-process

**Logged**: 2026-07-16T00:35:00Z
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary

Putting `fail_under` in the global coverage configuration caused the independent
browser E2E process to fail despite all 22 tests passing.

### Error

```text
22 passed
FAIL Required test coverage of 64.0% not reached. Total coverage: 16.70%
```

### Suggested Fix

Enforce the floor only on the authoritative combined non-E2E command; keep E2E as
an independent behavior gate.

### Resolution

- **Resolved**: 2026-07-16T00:35:00Z
- **Notes**: Moved `--cov-fail-under=64` to the non-E2E command in `check-all.sh`.

---
## [ERR-20260716-011] full-gate-router-format-drift

**Logged**: 2026-07-16T00:30:00Z
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

The repository-wide format gate found two router files changed during the earlier
publisher-token remediation that had not received a final formatting pass.

### Error

```text
Would reformat: server/modules/exposure/router.py
Would reformat: server/modules/review/router.py
```

### Resolution

- **Resolved**: 2026-07-16T00:30:00Z
- **Notes**: Formatted both routers and restarted the repository-wide static gate.

---
## [ERR-20260716-010] tomllib-import-order

**Logged**: 2026-07-16T00:25:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The package-metadata governance test introduced an unsorted standard-library import.

### Error

```text
I001 Import block is un-sorted or un-formatted
```

### Resolution

- **Resolved**: 2026-07-16T00:25:00Z
- **Notes**: Applied Ruff's mechanical import fix before rerunning the gate.

---
## [ERR-20260716-009] publisher-token-function-budget

**Logged**: 2026-07-16T00:20:00Z
**Priority**: medium
**Status**: resolved
**Area**: maintainability

### Summary

The maintainability gate found the expanded product-token creation function above
the 100-line production limit.

### Error

```text
server/modules/access/token_service.py:122 create_product_token: 108
```

### Suggested Fix

Extract product-token validation and scope resolution into typed helpers without
changing transaction ownership.

### Resolution

- **Resolved**: 2026-07-16T00:22:00Z
- **Notes**: Extracted typed grant and credential construction helpers; service still flushes without committing.

---
## [ERR-20260716-008] npm-mirror-missing-audit-endpoint

**Logged**: 2026-07-16T00:15:00Z
**Priority**: medium
**Status**: resolved
**Area**: supply-chain

### Summary

The configured npm mirror does not implement the security audit endpoint.

### Error

```text
404 Not Found - POST https://registry.npmmirror.com/-/npm/v1/security/audits/quick
```

### Suggested Fix

Pin audit commands to the official npm registry while leaving package installation
registry choice unchanged.

### Resolution

- **Resolved**: 2026-07-16T00:15:00Z
- **Notes**: Release-gate audit uses `--registry=https://registry.npmjs.org`.

---
## [ERR-20260716-007] focused-test-format-drift

**Logged**: 2026-07-16T00:10:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The focused static gate stopped because the new integration test needed Ruff formatting.

### Error

```text
Would reformat: tests/integration/test_library_pages.py
```

### Resolution

- **Resolved**: 2026-07-16T00:10:00Z
- **Notes**: Formatted the test before resuming Mypy and focused integration tests.

---
## [ERR-20260716-006] cross-file-hunk-target-mismatch

**Logged**: 2026-07-16T00:05:00Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

A combined read-model patch placed a function-signature hunk under the TypedDict
file instead of the projection implementation file.

### Error

```text
apply_patch verification failed: Failed to find expected lines in server/modules/library/read_models.py
```

### Resolution

- **Resolved**: 2026-07-16T00:05:00Z
- **Notes**: Split schema, projection, template, JavaScript, and locale edits by file.

---
## [ERR-20260716-005] broad-patch-context-drift

**Logged**: 2026-07-16T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: documentation

### Summary

A multi-file patch failed atomically because the quickstart wording differed from
the audit summary.

### Error

```text
apply_patch verification failed: Failed to find expected lines in docs/guide/quickstart.md
```

### Suggested Fix

Inspect exact maintained-document context and split broad patches into smaller,
independently verifiable edits.

### Resolution

- **Resolved**: 2026-07-16T00:00:00Z
- **Notes**: Re-read the affected sections and applied narrower patches.

---

## [ERR-20260716-003] ruff-publisher-enum-secret-false-positive

**Logged**: 2026-07-16T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

Ruff S105 treated the product-token enum value `publisher` as a hardcoded password.

### Error

```text
S105 Possible hardcoded password assigned to: token_type / product_token_type
```

### Context

- The value is a public authorization enum, not a credential secret.
- Expanding global per-file ignores would hide real secret findings.

### Suggested Fix

Use local `# noqa: S105` annotations on the enum comparisons only.

### Metadata

- Reproducible: yes
- Related Files: server/modules/access/token_service.py, server/modules/authoring/router.py,
  server/modules/release/router.py

### Resolution

- **Resolved**: 2026-07-16T00:00:00Z
- **Notes**: Added narrow local suppressions and sorted imports.

---

## [ERR-20260716-002] e2e-database-rate-limit-isolation

**Logged**: 2026-07-16T00:00:00Z
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary

The full E2E suite exhausted database-backed login limits because its authenticated-page
fixture reset only the retired in-memory HTTP bucket.

### Error

```text
AssertionError: assert 429 == 200
```

### Context

- HTTP routes now use `DBRateLimiter` so limits work across worker processes.
- The E2E fixture still called only `get_rate_limiter().reset_all()` without a session.
- Targeted E2E files stayed below the login threshold, while the complete suite exposed
  the stale isolation assumption.

### Suggested Fix

Reset both memory and database limiter backends in shared test fixtures.

### Metadata

- Reproducible: yes
- Related Files: tests/e2e/conftest.py, server/rate_limit.py

### Resolution

- **Resolved**: 2026-07-16T00:00:00Z
- **Notes**: The fixture now clears `DBRateLimiter` through the shared session factory.

---

## [ERR-20260716-001] embedded-browser-js-line-length

**Logged**: 2026-07-16T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

Ruff applied the Python line-length rule to JavaScript embedded in a Playwright evaluate string.

### Error

```text
E501 Line too long (106-122 > 100)
```

### Context

- The new E2E test calculates WCAG contrast ratios inside the browser.
- Four JavaScript expressions exceeded the repository's 100-character source limit.

### Suggested Fix

Format embedded scripts to the host file's line-length standard before running targeted checks.

### Metadata

- Reproducible: yes
- Related Files: tests/e2e/test_navigation.py

### Resolution

- **Resolved**: 2026-07-16T00:00:00Z
- **Notes**: Split the embedded JavaScript expressions across lines.

---

## [ERR-20260715-010] comparator-union-ordering-type

**Logged**: 2026-07-15T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

A comparator helper used a union of individually sortable types that mypy correctly rejected as cross-type comparable.

### Error

```text
Unsupported operand types for < ("int" and "str")
```

### Context

- Each call site supplies a same-type pair, but the union annotation cannot encode that relationship.
- Candidate ordering behavior tests remained green.

### Suggested Fix

Keep the dynamic comparison localized and type the boundary as `Any` when same-type pairing is guaranteed by construction.

### Metadata

- Reproducible: yes
- Related Files: src/infinitas_skill/install/target_validation.py

### Resolution

- **Resolved**: 2026-07-15T00:00:00Z
- **Notes**: Localized dynamic ordering to one comparator helper.

---

## [ERR-20260715-009] browser-esm-and-source-contract

**Logged**: 2026-07-15T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

CommonJS package metadata made direct Node syntax checks misclassify browser ESM, and a source-slicing test depended on the old nested-function layout.

### Error

```text
SyntaxError: Cannot use import statement outside a module
ValueError: substring not found
```

### Context

- Browser modules remain ESM and the production build completed successfully.
- Auth controller behavior was preserved, but class methods replaced nested function declarations.

### Suggested Fix

Pipe browser modules through `node --input-type=module --check` and slice contract tests by stable class method markers.

### Metadata

- Reproducible: yes
- Related Files: server/static/js/modules/auth-modal.js, tests/integration/test_private_registry_ui.py
- Recurrence-Count: 2
- Last-Seen: 2026-07-16

### Resolution

- **Resolved**: 2026-07-15T00:00:00Z
- **Notes**: Adopted ESM-aware syntax checks and retained semantic redirect/session assertions.

---

## [ERR-20260715-008] stale-targeted-test-path

**Logged**: 2026-07-15T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

A targeted regression command referenced a test file removed by the architecture reset.

### Error

```text
ERROR: file or directory not found: tests/integration/test_review_governance.py
```

### Context

- Static checks and C901 validation completed successfully before pytest parsed the stale path.
- Pytest did not run any tests from that command.

### Suggested Fix

Build targeted test lists from `rg --files tests` after large test-layout resets.

### Metadata

- Reproducible: yes
- Related Files: tests

### Resolution

- **Resolved**: 2026-07-15T00:00:00Z
- **Notes**: Replaced the stale path with current policy, review, and canonical test files.

---

## [ERR-20260715-007] shared-formatting-import-cleanup

**Logged**: 2026-07-15T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

Moving shared formatting helpers removed a `json` import still required by `load_json_list`.

### Error

```text
F821 Undefined name `json`
```

### Context

- Targeted tests passed, while Ruff and mypy caught the missing import.
- Three library modules also needed import reordering after ownership changes.

### Suggested Fix

Check all remaining symbols in a module before removing imports during helper extraction.

### Metadata

- Reproducible: yes
- Related Files: server/ui/formatting.py

### Resolution

- **Resolved**: 2026-07-15T00:00:00Z
- **Notes**: Restored the import and normalized import order.

---

## [ERR-20260715-006] oversized-cleanup-patch-context

**Logged**: 2026-07-15T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

An oversized cleanup patch was rejected because one function body differed from the audit summary.

### Error

```text
apply_patch verification failed: Failed to find expected lines in distribution_core.py
```

### Context

- The patch grouped unrelated dead-code removals across many domains.
- Patch application was atomic, so no partial repository changes occurred.

### Suggested Fix

Apply cleanup in domain-sized patches using current file context.

### Metadata

- Reproducible: no
- Related Files: src/infinitas_skill/install/distribution_core.py, src/infinitas_skill/install/distribution_index.py
- Recurrence-Count: 2

### Resolution

- **Resolved**: 2026-07-15T00:00:00Z
- **Notes**: Switched to domain-sized patches after two atomic rejections caused by stale context.

---

## [ERR-20260715-005] zsh-nested-quote-search

**Logged**: 2026-07-15T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

A repository search command used nested single-quote fragments that zsh could not parse.

### Error

```text
zsh:7: unmatched '
```

### Context

- The command attempted to search for Python `__main__` guards and helper entrypoints.
- The failure occurred before any repository file was modified.

### Suggested Fix

Use separate fixed-string `rg` calls instead of embedding both quote styles in one shell expression.

### Metadata

- Reproducible: yes
- Related Files: tests/helpers, tests/integration

### Resolution

- **Resolved**: 2026-07-15T00:00:00Z
- **Notes**: Replaced the command with simple fixed-string searches.

---

## [ERR-20260715-002] npm-audit-registry-endpoint

**Logged**: 2026-07-15T00:00:00Z
**Priority**: medium
**Status**: unresolved
**Area**: infra

### Summary

`npm audit` could not query the configured npm mirror's security endpoint.

### Error

```text
npm WARN audit 404 Not Found - POST https://registry.npmmirror.com/-/npm/v1/security/audits/quick - [NOT_IMPLEMENTED]
npm ERR! audit endpoint returned an error
```

### Context

- Command: `npm audit --audit-level=moderate`
- The failure is in the registry service, so no JavaScript vulnerability conclusion is justified.

### Suggested Fix

Run the audit against a registry that implements the npm security audit API or use an exported lockfile scanner.

### Metadata

- Reproducible: yes
- Related Files: package-lock.json

### Follow-up

- The same audit against `https://registry.npmjs.org` completed and reported `postcss <8.5.10` (GHSA-qx2v-qp2m-jg93, moderate); the mirror failure did not prevent alternate-registry auditing.

---

## [ERR-20260715-004] zsh-readonly-status-variable

**Logged**: 2026-07-15T08:18:00Z
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary

A diagnostic command assigned an exit code to `status`, which is a read-only special parameter in zsh.

### Error

```text
zsh:1: read-only variable: status
```

### Suggested Fix

Use a shell-neutral name such as `exit_code` when preserving command status in repository diagnostics.

### Resolution

- **Resolved**: 2026-07-15T08:19:00Z
- **Notes**: Re-ran the read-only coverage probe with `exit_code`; no repository files were affected by the failed command.

---

## [ERR-20260715-001] jq-openapi-path-iteration

**Logged**: 2026-07-15T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: config

### Summary

An OpenAPI inventory query lost the operation entry context inside a `jq` array expression.

### Error

```text
jq: error: Cannot index string with string "value"
```

### Context

- The query rebound `.` while uppercasing the HTTP method, then attempted `.value` on that string.
- The failure was limited to a read-only audit command.

### Suggested Fix

Bind both path and operation entries to variables before constructing output arrays.

### Metadata

- Reproducible: yes
- Related Files: openapi.json

### Resolution

- **Resolved**: 2026-07-15T00:00:00Z
- **Notes**: Use explicit `$path_entry` and `$operation_entry` bindings in subsequent queries.

---

## [ERR-20260714-001] codex-skill-path

**Logged**: 2026-07-14T00:00:00Z
**Priority**: low
**Status**: resolved
**Area**: config

### Summary

The advertised Superpowers skill path did not exist in this migrated Codex environment.

### Error

```text
sed: can't read /home/tdcasual/.codex/superpowers/skills/using-superpowers/SKILL.md: No such file or directory
```

### Context

- The skill catalog pointed at `/home/tdcasual/.codex/superpowers/skills/`.
- The active plugin files were under `/home/tdcasual/.codex/.tmp/plugins/plugins/superpowers/skills/`.

### Suggested Fix

Resolve the skill location from the filesystem when a catalog path is stale after migration.

### Metadata

- Reproducible: yes
- Related Files: none

### Resolution

- **Resolved**: 2026-07-14T00:00:00Z
- **Notes**: Located and read the active skill files from the plugin cache.

---

## [ERR-20260714-015] sandbox-denies-test-sockets

**Logged**: 2026-07-14T15:45:00Z
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary

The sandbox denied local socket creation required by server-operation integration tests.

### Error

```text
PermissionError: [Errno 1] Operation not permitted
```

### Context

- `ThreadingHTTPServer(("127.0.0.1", 0), ...)` failed before the test could run.
- The same sandbox restriction likely affected AnyIO's synchronous TestClient portal.

### Suggested Fix

Run socket-dependent integration and TestClient suites with the approved unsandboxed test command; keep application code unchanged.

### Metadata

- Reproducible: yes
- Related Files: tests/integration/test_cli_server_ops.py, tests/helpers/ops_support/server_ops.py

### Resolution

- **Resolved**: 2026-07-14T15:45:00Z
- **Notes**: Re-ran the authoritative Python 3.11 coverage suite outside the filesystem/network sandbox.

---

## [ERR-20260714-014] sandbox-testclient-portal-hang

**Logged**: 2026-07-14T15:40:00Z
**Priority**: medium
**Status**: unresolved
**Area**: tests

### Summary

Synchronous Starlette/FastAPI `TestClient` requests hang in the current container under both Python 3.11 and 3.13.

### Error

```text
Main thread waits in starlette.testclient.handle_request while the AnyIO portal event loop is idle in selectors.select.
```

### Context

- The behavior reproduces with a minimal one-route FastAPI application, independent of project middleware, database, or lifespan.
- Python 3.11 was aligned to `uv.lock`; the same minimal reproduction still hangs.
- App construction and route registration complete successfully.

### Suggested Fix

Run synchronous TestClient suites in CI or a normal host environment; consider migrating tests to `httpx.AsyncClient` with `ASGITransport` if this container behavior becomes a recurring local constraint.

### Metadata

- Reproducible: yes
- Related Files: tests/unit/test_error_handling.py, tests/integration/conftest.py
- Recurrence-Count: 2
- Last-Seen: 2026-07-15

### Resolution

- **Unresolved**: environment-specific AnyIO portal behavior; no application-code change is justified.

---

## [ERR-20260714-013] help-normalizer-nontermination

**Logged**: 2026-07-14T15:30:00Z
**Priority**: medium
**Status**: resolved
**Area**: documentation

### Summary

The first cross-version help normalizer could repeatedly split a line at its indentation boundary without shortening it.

### Error

```text
CLI reference generation produced no output before the command timeout.
```

### Context

- A usage line containing only indentation plus one long option matched the generic split rule.
- Reconstructing the line yielded the same content, so the loop made no progress.

### Suggested Fix

Require every iterative normalization step to move past indentation and strictly shorten the current line; validate generators under a timeout.

### Metadata

- Reproducible: yes
- Related Files: src/infinitas_skill/cli/reference.py

### Resolution

- **Resolved**: 2026-07-14T15:30:00Z
- **Notes**: Added a progress guard and verified Python 3.11/3.13 outputs with bounded commands.

---

## [ERR-20260714-012] argparse-cross-version-doc-drift

**Logged**: 2026-07-14T15:25:00Z
**Priority**: medium
**Status**: resolved
**Area**: documentation

### Summary

Generated CLI reference output differed between Python 3.11 and 3.13 because `argparse` wrapped usage lines differently.

### Error

```text
test_cli_reference_doc_matches_generated_argparse_output failed only under Python 3.11
```

### Context

- Python 3.11 placed the subcommand ellipsis on a separate line and wrapped long option pairs differently.
- The documentation contract should not depend on the interpreter's private formatting implementation.

### Suggested Fix

Normalize the usage paragraph with a fixed-width renderer before embedding parser help in generated documentation.

### Metadata

- Reproducible: yes
- Related Files: src/infinitas_skill/cli/reference.py, docs/reference/cli-reference.md

### Resolution

- **Resolved**: 2026-07-14T15:25:00Z
- **Notes**: Added stable usage rendering and verified identical output under Python 3.11 and 3.13.

---

## [ERR-20260714-011] python311-runtime-typeddict

**Logged**: 2026-07-14T14:35:00Z
**Priority**: high
**Status**: resolved
**Area**: compatibility

### Summary

Python 3.11 could not construct FastAPI response models backed by `typing.TypedDict`.

### Error

```text
PydanticUserError: Please use typing_extensions.TypedDict instead of typing.TypedDict on Python < 3.12.
```

### Context

- CI runs Python 3.11 while the local project environment uses Python 3.13.
- `server/modules/library/read_models.py` types are consumed by FastAPI/Pydantic at runtime.

### Suggested Fix

Use `typing_extensions.TypedDict` for runtime-inspected models while Python 3.11 remains supported, and validate app import under the CI interpreter.

### Metadata

- Reproducible: yes
- Related Files: server/modules/library/read_models.py

### Resolution

- **Resolved**: 2026-07-14T14:35:00Z
- **Notes**: Switched runtime TypedDict imports to `typing_extensions` and reran the Python 3.11 suite.

---

## [ERR-20260714-010] ownership-extraction-missed-import

**Logged**: 2026-07-14T14:25:00Z
**Priority**: low
**Status**: resolved
**Area**: architecture

### Summary

Moving semantic-version ownership left one candidate comparator without its direct `compare_versions` import.

### Error

```text
F821 Undefined name `compare_versions`
```

### Context

- `source_resolution.py` still owns catalog ordering and therefore still consumes the extracted comparator.
- The first extraction patch updated external consumers but missed this same-file usage.

### Suggested Fix

After ownership extraction, scan the old symbol names across the full repository before running the combined gate.

### Metadata

- Reproducible: yes
- Related Files: src/infinitas_skill/install/source_resolution.py, src/infinitas_skill/install/version_constraints.py

### Resolution

- **Resolved**: 2026-07-14T14:25:00Z
- **Notes**: Added the direct canonical import and reran static and install gates.

---

## [ERR-20260714-009] maintainability-budget-after-typing

**Logged**: 2026-07-14T14:15:00Z
**Priority**: medium
**Status**: resolved
**Area**: architecture

### Summary

Strict annotation work pushed two install modules over the 600-line ceiling and exposed a 115-line recursive solver method.

### Error

```text
source_resolution.py: 608
source_resolver_cli.py: 616
service.py _resolve_recursive: 115
```

### Context

- The maintainability gate passed functionally related install tests but failed structural budgets.
- Raising the budgets would hide ownership concentration rather than address it.

### Suggested Fix

Extract version constraints and registry candidate construction into focused owners, and split recursive resolution into grouping and candidate-attempt phases.

### Metadata

- Reproducible: yes
- Related Files: src/infinitas_skill/install/source_resolution.py, src/infinitas_skill/install/source_resolver_cli.py, src/infinitas_skill/install/service.py

### Resolution

- **Resolved**: 2026-07-14T14:20:00Z
- **Notes**: Split focused responsibilities and reran maintainability and install regression tests.

---

## [ERR-20260714-008] post-annotation-import-order

**Logged**: 2026-07-14T14:10:00Z
**Priority**: low
**Status**: resolved
**Area**: typing

### Summary

The repository-wide Ruff gate found three import-order violations after strict typing imports were added.

### Error

```text
I001 Import block is un-sorted or un-formatted
```

### Context

- The affected files were `compatibility/checks.py`, `install/source_resolution.py`, and `server/db_utils.py`.
- Ruff formatting does not sort imports; lint autofix is a separate step.

### Suggested Fix

After broad annotation passes, run `ruff check --fix` before the final lint and format checks.

### Metadata

- Reproducible: yes
- Related Files: src/infinitas_skill/compatibility/checks.py, src/infinitas_skill/install/source_resolution.py, src/infinitas_skill/server/db_utils.py

### Resolution

- **Resolved**: 2026-07-14T14:10:00Z
- **Notes**: Applied Ruff's import-order autofix and reran the complete static gate.

---

## [ERR-20260714-003] zsh-coverage-glob

**Logged**: 2026-07-14T09:30:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The coverage cleanup command used a Bash-style unmatched glob under zsh.

### Error

```text
zsh:1: no matches found: .coverage.*
```

### Context

- The command attempted `rm -f .coverage .coverage.*` before pytest.
- zsh rejects unmatched globs before `rm` can apply `-f`.

### Suggested Fix

Use `find . -maxdepth 1 -type f -name '.coverage*' -delete`, which is safe in both Bash and zsh.

### Metadata

- Reproducible: yes
- Related Files: scripts/check-all.sh

### Resolution

- **Resolved**: 2026-07-14T09:30:00Z
- **Notes**: Updated the repository command to a shell-portable `find` expression.

---

## [ERR-20260714-002] stale-test-path

**Logged**: 2026-07-14T06:00:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

A focused policy regression command referenced test files that no longer exist after test migration.

### Error

```text
ERROR: file or directory not found: tests/integration/test_team_governance.py
```

### Context

- The command combined valid and stale test paths with one pytest invocation.
- The repository has undergone extensive test consolidation and renaming.

### Suggested Fix

Discover current test paths with `rg --files tests` before assembling focused regression commands.

### Metadata

- Reproducible: yes
- Related Files: tests/

### Resolution

- **Resolved**: 2026-07-14T06:00:00Z
- **Notes**: Switched to test paths discovered from the current repository tree.

---

## [ERR-20260714-004] focused-ruff-import-order

**Logged**: 2026-07-14T11:45:00Z
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

A focused Ruff pass found two import blocks left out of canonical order after module ownership changes.

### Error

```text
I001 Import block is un-sorted or un-formatted
```

### Context

- The review-command and signing-doctor modules had just changed import owners.
- Ruff formatting does not apply import sorting; the subsequent lint pass correctly rejected them.

### Suggested Fix

Run the focused Ruff check immediately after ownership refactors and correct import ordering before behavioral tests.

### Metadata

- Reproducible: yes
- Related Files: src/infinitas_skill/policy/review_commands.py, src/infinitas_skill/release/signing_doctor_report.py

### Resolution

- **Resolved**: 2026-07-14T11:45:00Z
- **Notes**: Reordered the affected imports and retained the focused lint gate.

---

## [ERR-20260714-005] zsh-backtick-search-pattern

**Logged**: 2026-07-14T12:35:00Z
**Priority**: low
**Status**: resolved
**Area**: config

### Summary

A read-only ripgrep command used a backtick inside a double-quoted zsh pattern and failed during shell parsing.

### Error

```text
zsh:1: unmatched "
```

### Context

- The intended search included a Markdown heading containing a literal backtick.
- zsh interpreted the backtick before `rg` received the pattern.

### Suggested Fix

Use single-quoted fixed strings or omit Markdown delimiters from shell search patterns.

### Metadata

- Reproducible: yes
- Related Files: docs/reference/cli-reference.md

### Resolution

- **Resolved**: 2026-07-14T12:35:00Z
- **Notes**: Reissued the search with shell-safe single-quoted expressions.

---

## [ERR-20260714-006] stale-doc-context-patch

**Logged**: 2026-07-14T12:50:00Z
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary

A multi-hunk documentation patch assumed command lines that differed from the current file and was rejected before applying.

### Error

```text
apply_patch verification failed: Failed to find expected lines in docs/reference/multi-registry.md
```

### Context

- The document contained an additional canonical CLI line inside the same command block.
- The patch used summarized context rather than the exact current lines.

### Suggested Fix

Read the exact line ranges before applying multi-section rewrites to long, frequently edited documents.

### Metadata

- Reproducible: yes
- Related Files: docs/reference/multi-registry.md
- See Also: discovery signature annotation patch on 2026-07-14
- Recurrence-Count: 2

### Resolution

- **Resolved**: 2026-07-14T12:50:00Z
- **Notes**: Rebuilt patches from exact current-file signatures; the same safeguard was reused when a later discovery annotation patch had keyword-only parameters absent from its summary.

---

## [ERR-20260714-007] full-format-gate-drift

**Logged**: 2026-07-14T13:05:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The full Ruff format gate found one governance test file that had not been reformatted after prior edits.

### Error

```text
Would reformat: tests/unit/governance/test_ci_attestation_docs.py
```

### Context

- The combined command stopped at `ruff format --check` before lint and Mypy ran.
- Focused formatting had not included this previously edited test.

### Suggested Fix

Run the repository-wide format check after documentation-test edits instead of relying only on focused file lists.

### Metadata

- Reproducible: yes
- Related Files: tests/unit/governance/test_ci_attestation_docs.py

### Resolution

- **Resolved**: 2026-07-14T13:05:00Z
- **Notes**: Applied Ruff formatting and resumed the full static gate.

---
## [ERR-20260715-003] duplicate-standalone-login-controller

**Logged**: 2026-07-15T07:35:00Z
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary

An E2E login timeout was initially misdiagnosed as a missing standalone login controller, but `auth-home.js` already initializes the `login-` controller.

### Error

```text
Standalone login remained on /login during a timing-sensitive assertion; adding a second controller caused duplicate form handlers and extra login requests.
```

### Context

- The original test clicked submit and immediately waited for network idle instead of waiting for the login response and target URL.
- `initHomeAuthSession()` already detects the standalone login page and chooses the `login-` prefix.

### Suggested Fix

Search all existing initializers before adding a controller. For navigation initiated by async form handling, wait for the concrete response and URL rather than relying on a generic network-idle wait.

### Metadata

- Reproducible: yes
- Related Files: server/static/js/modules/auth-home.js, server/static/js/auth-session.js, tests/e2e/test_auth_flows.py

### Resolution

- **Resolved**: 2026-07-15T07:38:00Z
- **Notes**: Removed the duplicate initializer, strengthened the login E2E synchronization, and changed authenticated fixtures to reuse one session state.

---

## [ERR-20260719-002] oversized-response-model-patch-context

**Logged**: 2026-07-19T10:13:39+00:00
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary

A multi-file response-model patch failed because one expected import line was absent.

### Error

```text
apply_patch verification failed: Failed to find expected lines in server/modules/discovery/schemas.py
```

### Context

- The patch assumed `from typing import Any` already existed.
- One context mismatch caused the entire large patch to be rejected.

### Suggested Fix

Inspect exact file headers and split cross-domain edits into smaller patches with local context.

### Metadata

- Reproducible: yes
- Related Files: server/modules/discovery/schemas.py
- Recurrence-Count: 2
- See Also: docs/ops/server-deployment.md documentation sync on 2026-07-19

### Resolution

- **Resolved**: 2026-07-19T10:13:39+00:00
- **Notes**: Rebuilt changes as smaller file-specific patches using current file content; the
  same method was reused after a documentation paragraph wrapping mismatch.

---

## [ERR-20260719-003] bootstrap-ignore-created-empty-state-directory

**Logged**: 2026-07-19T10:34:26+00:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary

Runtime bootstrap ignore rules removed files inside `.state` but still created the ignored top-level directory.

### Error

```text
assert not (repo / ".state").exists()
AssertionError: assert not True
```

### Context

- `shutil.copytree(..., ignore=...)` applies ignore matching to children of the copied directory.
- The top-level source child had already been selected for copying, so an empty ignored directory remained.

### Suggested Fix

Filter ignored top-level names before invoking `copytree`, while retaining recursive ignore patterns.

### Metadata

- Reproducible: yes
- Related Files: server/runtime_repo.py, tests/integration/test_runtime_repo.py

### Resolution

- **Resolved**: 2026-07-19T10:34:26+00:00
- **Notes**: Added explicit top-level ignore filtering for runtime state, caches, virtualenvs, coverage output, and node modules.

---
