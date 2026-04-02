# Complete Structural Cleanup Roadmap

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the maintainability reset by migrating the remaining reusable script logic into `src/infinitas_skill`, shrinking redundant entrypoints, and leaving the repository with one clear package-owned architecture plus a small, explicit set of repository-only scripts.

**Architecture:** Treat the current repository as already past the breaking-change point: deleted legacy shims stay deleted, maintained business logic belongs in `src/infinitas_skill`, and `scripts/` should converge toward thin wrappers, shell automation, or repo-only regression drivers. Execute the cleanup in four passes: freeze boundaries with guards, migrate the remaining reusable script-lib clusters into package-native modules, collapse redundant command surfaces into maintained CLI or thin wrappers, then finish with a compact verification and documentation pass.

**Tech Stack:** Python 3.11, package-native modules under `src/infinitas_skill`, `scripts/test-*.py` regression flows, `pytest` integration guards, Bash wrappers under `scripts/`, and maintainability/reference docs under `docs/`.

---

## Preconditions

- Work in the current dirty repository state; do not reset unrelated changes.
- Preserve the hard-cut posture: no legacy CLI restoration and no new logic added back into deleted shim entrypoints.
- Use `@superpowers:test-driven-development` before each behavior change.
- Use `@superpowers:verification-before-completion` before each completion claim or commit.
- Keep the current release-readiness scorecard valid throughout the cleanup.

## Current Baseline

Already completed and should be treated as fixed architecture:

- discovery / recommendation / install explanation chain is package-native under `src/infinitas_skill/discovery/...`
- installed-integrity, release, policy, distribution, registry-source, review-evidence, team-policy, and several related libs are already thin wrappers
- temp-repo release tests now share one package-native interpreter/PATH helper under `src/infinitas_skill/testing/env.py`
- `./scripts/check-all.sh release-long` passes fresh
- release-readiness scorecard is published in `docs/ops/2026-04-01-release-readiness-scorecard.md`

Remaining non-thin reusable script libs at the time of writing:

- `scripts/canonical_skill_lib.py`
- `scripts/decision_metadata_lib.py`
- `scripts/openclaw_bridge_lib.py`
- `scripts/provenance_payload_lib.py`
- `scripts/registry_refresh_state_lib.py`
- `scripts/registry_snapshot_lib.py`
- `scripts/render_skill_lib.py`
- `scripts/result_schema_lib.py`
- `scripts/reviewer_rotation_lib.py`
- `scripts/schema_version_lib.py`
- `scripts/search_inspect_lib.py`
- `scripts/signing_bootstrap_lib.py`

## Recommended Execution Order

1. Task 1: Freeze remaining boundaries with guards
2. Task 2: Move discovery search/inspect result-contract helpers into `src/infinitas_skill/discovery`
3. Task 3: Move canonical skill / render / export bridge logic into `src/infinitas_skill/skills`
4. Task 4: Move registry refresh/snapshot logic into `src/infinitas_skill/registry`
5. Task 5: Move signing / provenance / reviewer recommendation helpers into `src/infinitas_skill/release` and `src/infinitas_skill/policy`
6. Task 6: Collapse redundant command surfaces and shrink `scripts/` to wrappers or repo-only automation
7. Task 7: Publish final architecture docs and re-run the verification matrix

### Task 1: Freeze the remaining architecture boundaries

**Why first:** The biggest remaining risk is reintroducing duplicated logic while we continue migrating. Add guards before any more code moves.

**Files:**
- Modify: `tests/integration/test_dev_workflow.py`
- Modify: `docs/reference/testing.md`
- Test: `tests/integration/test_dev_workflow.py`

**Target guard clusters:**

- discovery search and result contracts:
  - `scripts/decision_metadata_lib.py`
  - `scripts/search_inspect_lib.py`
  - `scripts/result_schema_lib.py`
- canonical/render/export cluster:
  - `scripts/schema_version_lib.py`
  - `scripts/canonical_skill_lib.py`
  - `scripts/render_skill_lib.py`
  - `scripts/openclaw_bridge_lib.py`
- registry refresh/snapshot cluster:
  - `scripts/registry_refresh_state_lib.py`
  - `scripts/registry_snapshot_lib.py`
- signing/reviewer cluster:
  - `scripts/signing_bootstrap_lib.py`
  - `scripts/provenance_payload_lib.py`
  - `scripts/reviewer_rotation_lib.py`

**Steps:**

1. Add failing wrapper/ownership guards in `tests/integration/test_dev_workflow.py`.
2. Make the new test fail intentionally:

```bash
uv run python3 -m pytest tests/integration/test_dev_workflow.py -q
```

3. Document the new target migration clusters in `docs/reference/testing.md`.
4. Re-run the same test once the guard shape is correct.

**Definition of done:**

- `tests/integration/test_dev_workflow.py` explicitly lists the remaining migration targets.
- The file becomes the canonical “what is still allowed to live in scripts” guardrail.

### Task 2: Finish the discovery-facing consumer layer

**Why second:** This is the highest-value user-facing cluster still carrying reusable logic in scripts, and it already sits adjacent to the now-package-native discovery chain.

**Files:**
- Create: `src/infinitas_skill/discovery/search.py`
- Create: `src/infinitas_skill/discovery/inspect.py`
- Create: `src/infinitas_skill/discovery/result_schema.py`
- Modify: `src/infinitas_skill/discovery/__init__.py`
- Modify: `scripts/decision_metadata_lib.py`
- Modify: `scripts/search_inspect_lib.py`
- Modify: `scripts/result_schema_lib.py`
- Modify: `scripts/search-skills.sh`
- Modify: `scripts/inspect-skill.sh`
- Modify: `scripts/test-ai-pull.py`
- Modify: `scripts/test-search-docs.py`
- Test: `tests/integration/test_dev_workflow.py`

**Architecture notes:**

- `decision_metadata_lib.py` should become a thin wrapper around the already-existing `src/infinitas_skill/discovery/decision_metadata.py`.
- Split `search_inspect_lib.py` into package-native `search.py` and `inspect.py` if that keeps responsibilities clearer.
- Move `validate_pull_result` and related contract checks into `src/infinitas_skill/discovery/result_schema.py`.

**Steps:**

1. Baseline the current discovery consumer scripts:

```bash
python3 scripts/test-recommend-skill.py
python3 scripts/test-explain-install.py
python3 scripts/test-install-by-name.py
python3 scripts/test-skill-update.py
python3 scripts/test-ai-pull.py
```

2. Move `decision_metadata_lib.py` to a thin wrapper.
3. Move search/inspect helpers into package-native modules.
4. Move result-schema validation into package-native modules.
5. Keep shell entrypoints as wrappers only.
6. Re-run:

```bash
uv run python3 -m pytest tests/integration/test_dev_workflow.py -q
python3 scripts/test-ai-pull.py
python3 scripts/test-recommend-skill.py
python3 scripts/test-explain-install.py
python3 scripts/test-install-by-name.py
python3 scripts/test-skill-update.py
```

**Definition of done:**

- `scripts/decision_metadata_lib.py`, `scripts/search_inspect_lib.py`, and `scripts/result_schema_lib.py` are thin wrappers only.
- Search/inspect behavior is package-owned.
- Discovery result contracts no longer live in `scripts/`.

### Task 3: Move canonical skill, rendering, and OpenClaw bridge logic into `src/infinitas_skill/skills`

**Why third:** This cluster is structurally important and widely reused by export/import/check scripts, but it is self-contained enough to migrate as a clean vertical slice.

**Files:**
- Create: `src/infinitas_skill/skills/__init__.py`
- Create: `src/infinitas_skill/skills/schema_version.py`
- Create: `src/infinitas_skill/skills/canonical.py`
- Create: `src/infinitas_skill/skills/render.py`
- Create: `src/infinitas_skill/skills/openclaw.py`
- Modify: `scripts/schema_version_lib.py`
- Modify: `scripts/canonical_skill_lib.py`
- Modify: `scripts/render_skill_lib.py`
- Modify: `scripts/openclaw_bridge_lib.py`
- Modify: `scripts/render-skill.py`
- Modify: `scripts/export-claude-skill.sh`
- Modify: `scripts/export-codex-skill.sh`
- Modify: `scripts/export-openclaw-skill.sh`
- Modify: `scripts/import-openclaw-skill.sh`
- Modify: `scripts/check-openclaw-compat.py`
- Modify: `scripts/check-codex-compat.py`
- Modify: `scripts/check-claude-compat.py`
- Modify: `scripts/validate-registry.py`
- Test: `scripts/test-canonical-skill.py`
- Test: `scripts/test-render-skill.py`
- Test: `scripts/test-openclaw-export.py`
- Test: `scripts/test-openclaw-import.py`

**Architecture notes:**

- `schema_version` is foundational and should migrate first.
- `canonical.py` should own canonical-vs-legacy skill loading and validation.
- `render.py` should own platform profile loading and rendering.
- `openclaw.py` should own OpenClaw import/export validation and conversion helpers.

**Steps:**

1. Baseline:

```bash
python3 scripts/test-canonical-skill.py
python3 scripts/test-render-skill.py
python3 scripts/test-openclaw-export.py
python3 scripts/test-openclaw-import.py
```

2. Move `schema_version_lib.py` and `canonical_skill_lib.py` first.
3. Move `render_skill_lib.py` next.
4. Move `openclaw_bridge_lib.py` last in this cluster.
5. Leave shell entrypoints and one-file Python commands as wrappers only.
6. Re-run the baseline commands plus:

```bash
python3 scripts/check-codex-compat.py skills/active/operate-infinitas-skill
python3 scripts/check-claude-compat.py skills/active/operate-infinitas-skill
```

**Definition of done:**

- Canonical skill parsing/validation/render/export logic is package-native.
- OpenClaw bridge logic is package-native.
- Export/import/check scripts only orchestrate I/O and CLI argument handling.

### Task 4: Move registry refresh and snapshot logic into `src/infinitas_skill/registry`

**Why fourth:** This cluster still powers a lot of catalog and registry behavior, and it is the main reason some long tests remain slower and more script-dependent than necessary.

**Files:**
- Create: `src/infinitas_skill/registry/refresh_state.py`
- Create: `src/infinitas_skill/registry/snapshot.py`
- Modify: `src/infinitas_skill/registry/__init__.py`
- Modify: `scripts/registry_refresh_state_lib.py`
- Modify: `scripts/registry_snapshot_lib.py`
- Modify: `scripts/registry-refresh-status.py`
- Modify: `scripts/resolve-skill-source.py`
- Modify: `scripts/sync-registry-source.sh`
- Modify: `scripts/create-registry-snapshot.py`
- Modify: `scripts/list-registry-sources.py`
- Modify: `scripts/build-catalog.sh`
- Test: `scripts/test-registry-refresh-policy.py`
- Test: `scripts/test-registry-snapshot-mirror.py`
- Test: `scripts/test-hosted-registry-source.py`

**Architecture notes:**

- Keep state-file reading/writing and freshness evaluation together.
- Keep snapshot selector logic and catalog-summary helpers together.
- Avoid introducing reverse dependencies from package code back into `scripts/`.

**Steps:**

1. Baseline:

```bash
python3 scripts/test-registry-refresh-policy.py
python3 scripts/test-registry-snapshot-mirror.py
python3 scripts/test-hosted-registry-source.py
```

2. Move `registry_refresh_state_lib.py`.
3. Move `registry_snapshot_lib.py`.
4. Re-point all script and shell consumers.
5. Re-run the baseline commands plus:

```bash
python3 scripts/registry-refresh-status.py self --json
python3 scripts/list-registry-sources.py
```

**Definition of done:**

- Registry freshness/snapshot semantics are package-owned.
- Catalog and resolution scripts no longer depend on script-local reusable logic.

### Task 5: Move signing, provenance, and reviewer recommendation helpers into package modules

**Why fifth:** These are important operational flows, but they are more isolated than the earlier clusters and can be migrated after the discovery and registry surfaces are stable.

**Files:**
- Create: `src/infinitas_skill/release/signing_bootstrap.py`
- Create: `src/infinitas_skill/release/provenance_payload.py`
- Create: `src/infinitas_skill/policy/reviewer_rotation.py`
- Modify: `scripts/signing_bootstrap_lib.py`
- Modify: `scripts/provenance_payload_lib.py`
- Modify: `scripts/reviewer_rotation_lib.py`
- Modify: `scripts/bootstrap-signing.py`
- Modify: `scripts/doctor-signing.py`
- Modify: `scripts/report-signing-readiness.py`
- Modify: `scripts/generate-provenance.py`
- Modify: `scripts/generate-ci-attestation.py`
- Modify: `scripts/recommend-reviewers.py`
- Modify: `scripts/review-status.py`
- Test: `scripts/test-signing-bootstrap.py`
- Test: `scripts/test-signing-readiness-report.py`
- Test: `scripts/test-platform-review-evidence.py`

**Steps:**

1. Baseline:

```bash
python3 scripts/test-signing-bootstrap.py
python3 scripts/test-signing-readiness-report.py
python3 scripts/test-platform-review-evidence.py
```

2. Move signing bootstrap helpers first.
3. Move provenance payload helpers second.
4. Move reviewer recommendation helpers last.
5. Re-run the baseline commands plus:

```bash
python3 scripts/doctor-signing.py --json
python3 scripts/recommend-reviewers.py skills/active/operate-infinitas-skill --json
```

**Definition of done:**

- Operational signing/provenance/reviewer logic is package-native.
- CLI/report scripts only wrap arguments, formatting, and file output.

### Task 6: Collapse redundant command surfaces

**Why sixth:** Once the reusable logic is package-native, we can finally reduce the number of top-level scripts that maintainers have to think about.

**Files:**
- Modify: `src/infinitas_skill/cli/main.py`
- Modify: `src/infinitas_skill/cli/reference.py`
- Modify: `src/infinitas_skill/registry/cli.py`
- Modify: `src/infinitas_skill/policy/cli.py`
- Create or modify any additional CLI modules needed under `src/infinitas_skill/cli/`
- Modify: `README.md`
- Modify: `docs/reference/cli-reference.md`
- Modify: `docs/reference/testing.md`
- Modify: selected wrapper scripts under `scripts/`

**Candidate command reductions:**

- `scripts/search-skills.sh` -> `uv run infinitas registry search` or `uv run infinitas discovery search`
- `scripts/inspect-skill.sh` -> package CLI
- `scripts/render-skill.py` -> package CLI
- `scripts/bootstrap-signing.py` and `scripts/doctor-signing.py` -> package CLI
- `scripts/recommend-reviewers.py` and `scripts/review-status.py` -> package CLI

**Steps:**

1. Define the maintained CLI targets before deleting or thinning more scripts.
2. Add missing CLI subcommands in package modules.
3. Convert legacy entry scripts into wrappers that call the maintained CLI, or delete them when the repo no longer needs them.
4. Update docs to point to `uv run infinitas ...` first and `scripts/...` only as fallback.

**Definition of done:**

- Human-facing maintained commands are centered on `uv run infinitas ...`.
- `scripts/` is primarily repo automation, shell wrappers, or regression drivers.
- No new long-lived maintained behavior requires readers to discover it through top-level scripts first.

### Task 7: Final architecture consolidation and release of the cleanup

**Why last:** Only after the code moves and surface reduction are done does it make sense to declare the cleanup finished.

**Files:**
- Modify: `docs/ops/2026-04-01-release-readiness-scorecard.md`
- Modify: `README.md`
- Modify: `docs/reference/testing.md`
- Modify: `docs/reference/cli-reference.md`
- Modify: `docs/reference/README.md`
- Modify: `docs/ops/README.md`

**Verification matrix:**

```bash
uv run python3 -m pytest tests/integration/test_dev_workflow.py tests/integration/test_cli_policy.py tests/integration/test_cli_release_state.py tests/integration/test_cli_install_planning.py -q
make test-fast
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
python3 scripts/test-explain-install.py
python3 scripts/test-install-by-name.py
python3 scripts/test-skill-update.py
python3 scripts/test-canonical-skill.py
python3 scripts/test-render-skill.py
python3 scripts/test-openclaw-export.py
python3 scripts/test-openclaw-import.py
python3 scripts/test-registry-refresh-policy.py
python3 scripts/test-registry-snapshot-mirror.py
python3 scripts/test-signing-bootstrap.py
python3 scripts/test-signing-readiness-report.py
./scripts/check-all.sh release-long
```

**Documentation updates:**

- publish the final scorecard delta after cleanup
- update the maintained-surface section in `README.md`
- update CLI and testing docs to reflect the reduced command surface
- explicitly list which `scripts/` files are still intentionally non-thin because they are repo-only automation

**Definition of done:**

- remaining reusable logic lives in `src/infinitas_skill`
- remaining `scripts/*_lib.py` are thin wrappers or intentionally deleted
- maintained human-facing commands are package-native
- release-readiness score remains at least as strong as the current baseline

## Recommended batching

To avoid giant risky diffs, execute the roadmap in these release-sized batches:

1. Batch A: Task 1 + Task 2
2. Batch B: Task 3
3. Batch C: Task 4
4. Batch D: Task 5 + Task 6
5. Batch E: Task 7

Each batch should end with:

```bash
uv run python3 -m pytest tests/integration/test_dev_workflow.py -q
make test-fast
```

Any batch that touches release, registry, or signing paths must also end with:

```bash
./scripts/check-all.sh release-long
```

## Success Criteria

- `scripts/` no longer holds reusable domain logic for discovery, canonical skill parsing, rendering, registry refresh/snapshots, signing bootstrap, provenance payloads, or reviewer recommendation.
- `src/infinitas_skill` is the obvious home for all maintained Python behavior.
- maintainers can navigate the repository by domain instead of by historical script name.
- the number of scripts that require direct maintenance keeps dropping, not growing.
- release readiness stays green throughout the cleanup rather than being rebuilt at the end.
