# Release Commit Split Plan

## Goal

Split the current hard-cut cleanup into a small number of reviewable commits without
reintroducing legacy compatibility shims. The repository is already in a release-ready
state on April 2, 2026; this document only describes how to package the current dirty
worktree into safe, auditable commits.

## Verified Baseline

The following checks passed before writing this plan:

- `make lint-maintained`
- `make test-fast`
- `make test-full`
- `make doctor`
- `./scripts/check-all.sh release-long`
- `python3 scripts/test-infinitas-cli-reference-docs.py`
- `python3 scripts/test-doc-governance.py`
- `python3 scripts/test-signing-readiness-report.py`

## Commit Order

### Commit 1: Package Foundation And Hard-Cut Reset

**Purpose:** land the package-native foundation that everything else depends on.

**Stage these paths first:**

```bash
git add -- \
  README.md \
  pyproject.toml \
  docs/guide/README.md \
  docs/guide/maintainability-reset-policy.md \
  docs/reference/README.md \
  src/infinitas_skill/root.py \
  src/infinitas_skill/compatibility/checks.py \
  src/infinitas_skill/compatibility/evidence.py \
  src/infinitas_skill/skills \
  src/infinitas_skill/testing \
  src/infinitas_skill/legacy.py \
  scripts/canonical_skill_lib.py \
  scripts/openclaw_bridge_lib.py \
  scripts/render_skill_lib.py \
  scripts/schema_version_lib.py \
  scripts/test-namespace-identity.py \
  scripts/test-openclaw-export.py \
  scripts/test-operate-infinitas-skill.py \
  skills/active/operate-infinitas-skill/SKILL.md \
  skills/active/operate-infinitas-skill/tests/smoke.md \
  skills/active/release-infinitas-skill/SKILL.md \
  skills/active/release-infinitas-skill/tests/smoke.md
```

**Minimum verification before commit:**

```bash
python3 scripts/test-namespace-identity.py
python3 scripts/test-openclaw-export.py
python3 scripts/test-operate-infinitas-skill.py
```

**Suggested commit message:**

```text
refactor: establish package-native hard-cut foundation
```

### Commit 2: Discovery And Install Package Migration

**Purpose:** land the full discovery, resolve, recommend, install, distribution, and
installed-integrity chain under `src/infinitas_skill`.

**Stage these paths second:**

```bash
git add -- \
  docs/ai/publish.md \
  docs/reference/distribution-manifests.md \
  docs/reference/multi-registry.md \
  docs/reference/testing.md \
  src/infinitas_skill/discovery \
  src/infinitas_skill/install \
  scripts/ai_index_lib.py \
  scripts/decision_metadata_lib.py \
  scripts/discovery_index_lib.py \
  scripts/discovery_resolver_lib.py \
  scripts/distribution_lib.py \
  scripts/explain_install_lib.py \
  scripts/http_registry_lib.py \
  scripts/install_manifest_lib.py \
  scripts/install_integrity_policy_lib.py \
  scripts/installed_integrity_lib.py \
  scripts/installed_skill_lib.py \
  scripts/recommend_skill_lib.py \
  scripts/registry_source_lib.py \
  scripts/result_schema_lib.py \
  scripts/search_inspect_lib.py \
  scripts/install-skill.sh \
  scripts/switch-installed-skill.sh \
  scripts/sync-skill.sh \
  scripts/test-ai-index.py \
  scripts/test-discovery-index.py \
  scripts/test-distribution-install.py \
  scripts/test-explain-install.py \
  scripts/test-install-by-name.py \
  scripts/test-install-manifest-compat.py \
  scripts/test-installed-integrity-history-retention.py \
  scripts/test-installed-integrity-report.py \
  scripts/test-record-verified-support.py \
  scripts/test-skill-update.py \
  scripts/resolve-install-plan.py \
  scripts/check-install-target.py \
  tests/integration/test_cli_install_planning.py
```

**Minimum verification before commit:**

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
python3 scripts/test-distribution-install.py
python3 scripts/test-explain-install.py
python3 scripts/test-install-by-name.py
uv run python3 -m pytest tests/integration/test_cli_install_planning.py -q
```

**Suggested commit message:**

```text
refactor: migrate discovery and install flows into src package
```

### Commit 3: Policy, Registry, And Governance Migration

**Purpose:** land policy-pack, review evidence, reviewer rotation, registry refresh,
snapshot, and governance state under package-native modules.

**Stage these paths third:**

```bash
git add -- \
  docs/ops/federation-operations.md \
  docs/reference/policy-packs.md \
  docs/reference/promotion-policy.md \
  src/infinitas_skill/policy/exception_policy.py \
  src/infinitas_skill/policy/policy_pack.py \
  src/infinitas_skill/policy/review_commands.py \
  src/infinitas_skill/policy/review_evidence.py \
  src/infinitas_skill/policy/reviewer_rotation.py \
  src/infinitas_skill/policy/reviews.py \
  src/infinitas_skill/policy/skill_identity.py \
  src/infinitas_skill/policy/team_policy.py \
  src/infinitas_skill/policy/service.py \
  src/infinitas_skill/registry \
  scripts/exception_policy_lib.py \
  scripts/policy_pack_lib.py \
  scripts/review_evidence_lib.py \
  scripts/review_lib.py \
  scripts/reviewer_rotation_lib.py \
  scripts/skill_identity_lib.py \
  scripts/team_policy_lib.py \
  scripts/registry_refresh_state_lib.py \
  scripts/registry_snapshot_lib.py \
  scripts/check-policy-packs.py \
  scripts/registryctl.py \
  scripts/test-break-glass-exceptions.py \
  scripts/test-check-policy-packs.py \
  scripts/test-platform-review-evidence.py \
  scripts/test-policy-evaluation-traces.py \
  scripts/test-policy-pack-docs.py \
  scripts/test-team-governance-scopes.py
```

**Minimum verification before commit:**

```bash
python3 scripts/test-break-glass-exceptions.py
python3 scripts/test-check-policy-packs.py
python3 scripts/test-platform-review-evidence.py
python3 scripts/test-policy-evaluation-traces.py
python3 scripts/test-policy-pack-docs.py
python3 scripts/test-team-governance-scopes.py
```

**Suggested commit message:**

```text
refactor: migrate policy and registry governance modules
```

### Commit 4: CLI Consolidation And Release Signing

**Purpose:** land the maintained `infinitas` CLI surface, review/release command
cutover, signing flows, transparency log support, and long-release orchestration.

**Stage these paths fourth:**

```bash
git add -- \
  docs/ops/README.md \
  docs/ops/release-checklist.md \
  docs/ops/signing-bootstrap.md \
  docs/ops/signing-operations.md \
  docs/reference/cli-command-map.md \
  docs/reference/cli-reference.md \
  docs/release-strategy.md \
  src/infinitas_skill/cli/main.py \
  src/infinitas_skill/cli/reference.py \
  src/infinitas_skill/policy/cli.py \
  src/infinitas_skill/release \
  scripts/attestation_lib.py \
  scripts/bootstrap-signing.py \
  scripts/doctor-signing.py \
  scripts/provenance_payload_lib.py \
  scripts/recommend-reviewers.py \
  scripts/release-skill-tag.sh \
  scripts/release-skill.sh \
  scripts/report-signing-readiness.py \
  scripts/review-status.py \
  scripts/signing_bootstrap_lib.py \
  scripts/transparency_log_lib.py \
  scripts/check-all.sh \
  scripts/check-release-state.py \
  scripts/check-platform-contracts.py \
  scripts/check-promotion-policy.py \
  scripts/test-attestation-verification.py \
  scripts/test-infinitas-cli-platform-contracts.py \
  scripts/test-infinitas-cli-policy.py \
  scripts/test-infinitas-cli-reference-docs.py \
  scripts/test-infinitas-cli-release-state.py \
  scripts/test-platform-contracts.py \
  scripts/test-reference-doc-metadata.py \
  scripts/test-release-invariants.py \
  scripts/test-release-reproducibility.py \
  scripts/test-signing-readiness-report.py \
  scripts/test-transparency-log.py \
  tests/helpers/cli_policy.py \
  tests/helpers/env.py \
  tests/integration/test_cli_policy.py \
  tests/integration/test_cli_release_state.py \
  tests/integration/test_dev_workflow.py \
  tests/integration/test_long_release_script_selection.py
```

**Minimum verification before commit:**

```bash
python3 scripts/test-infinitas-cli-policy.py
python3 scripts/test-infinitas-cli-reference-docs.py
python3 scripts/test-infinitas-cli-release-state.py
python3 scripts/test-signing-readiness-report.py
python3 scripts/test-transparency-log.py
uv run python3 -m pytest tests/integration/test_dev_workflow.py tests/integration/test_cli_policy.py tests/integration/test_cli_release_state.py -q
./scripts/check-all.sh release-long
```

**Suggested commit message:**

```text
refactor: consolidate release and review commands into infinitas cli
```

### Commit 5: Server UI And Hosted Registry Ops Hardening

**Purpose:** land the remaining hosted UI and deployment-side adjustments separately
from the package migration chain.

**Stage these paths fifth:**

```bash
git add -- \
  alembic.ini \
  docs/ops/platform-drift-playbook.md \
  docs/ops/server-deployment.md \
  server/ui/notifications.py \
  server/ui/routes.py \
  tests/integration/test_private_registry_ui.py
```

**Minimum verification before commit:**

```bash
make test-fast
```

**Suggested commit message:**

```text
feat: harden hosted registry ui and deployment ops
```

## Optional Commit

These files are planning and scorecard artifacts. Keep them out of the product commits
unless the branch is explicitly meant to preserve process history:

```bash
docs/ops/2026-04-01-release-readiness-scorecard.md
docs/plans/2026-04-01-complete-structural-cleanup-roadmap.md
docs/plans/2026-04-01-discovery-chain-and-scorecard.md
docs/plans/2026-04-01-final-cleanup-and-release-readiness.md
docs/plans/2026-04-02-release-commit-split.md
```

Suggested message if committed:

```text
docs: record cleanup scorecard and commit split plan
```

## Final Release Gate

After the five product commits are created, run the full release gate once more on the
tip of the branch:

```bash
make lint-maintained
make test-fast
make test-full
./scripts/check-all.sh release-long
```

If all four commands pass again, the branch is ready for final smoke testing and release.
