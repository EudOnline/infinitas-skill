# Errors

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
