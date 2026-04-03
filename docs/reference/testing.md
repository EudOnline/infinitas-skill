# Testing

## Preferred command layer

Use the repo-native `make` targets first:

```bash
make bootstrap
make test-fast
make test-full
make lint-maintained
```

`make test-fast` is the preferred everyday verification entrypoint. It should stay aligned with the maintained
fast pytest tier, promoted regression flows, and maintainability budget enforcement.

Raw `uv` and script commands remain available below as fallback detail.

```bash
uv sync
uv run pytest tests/integration/test_cli_release_state.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_ui.py -q
uv run pytest tests/integration/test_maintainability_budgets.py -q
uv run pytest tests/integration/test_cli_policy.py tests/integration/test_signing_bootstrap.py tests/integration/test_installed_integrity.py -q
uv run ruff check src/infinitas_skill server/ui server/app.py tests/integration tests/unit
./scripts/check-all.sh
./scripts/check-all.sh release-long
```

`make lint-maintained` keeps the maintained-surface `E/F/I` baseline active, but it temporarily defers `E501` only
in the current debt-heavy maintained files, plus a few legacy path-bootstrap `E402` cases, until the larger service
and UI splits land.

`./scripts/check-all.sh release-long` is the canonical opt-in long-running release gate. Run it when a change touches
release packaging, provenance, transparency-log behavior, or temp-repo release fixtures.

Temp-repo regression scripts should share `src/infinitas_skill/testing/env.py` for interpreter selection and common
`INFINITAS_SKIP_*` test gating instead of rebuilding that environment inline per script.

## Focused maintained-surface checks

Run the fast `pytest` tier first when touching the maintained CLI or hosted UI surfaces:

```bash
uv run pytest tests/integration/test_cli_release_state.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_ui.py -q
uv run pytest tests/integration/test_maintainability_budgets.py -q
```

These files cover the maintained release CLI, the maintained server CLI surface, and the private-registry HTML route assembly without booting the full compatibility matrix.

`tests/integration/test_maintainability_budgets.py` now enforces the hard line budgets for maintained modules plus the temporary ceiling on top-level `scripts/` files.
`tests/integration/test_dev_workflow.py` is the architecture guard for the hard-cut reset: it now enforces deleted shim permanence plus thin-wrapper ownership for the discovery consumer, skill surface, registry, and signing/review script-lib clusters.

Promoted high-value regression flows now live in first-class pytest modules as well:

```bash
uv run pytest tests/integration/test_cli_policy.py tests/integration/test_signing_bootstrap.py tests/integration/test_installed_integrity.py -q
uv run pytest tests/integration/test_memory_evaluation_matrix.py -q
```

These cover the maintained policy CLI parity surface, signing bootstrap rehearsal, and installed-integrity guardrails.
`tests/integration/test_memory_evaluation_matrix.py` adds a fixture-backed recommendation/inspect quality gate for the advisory memory layer.
The matrix now also checks retrieval curation behavior, including duplicate suppression, short-lived low-signal noise suppression, and winner stability under noisy memory input.

## Script-Level Regression Checks

Some focused regression checks still live under `scripts/test-*.py` for repository-specific flows:

```bash
uv run python3 scripts/test-infinitas-cli-release-state.py
uv run python3 scripts/test-infinitas-cli-server.py
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-infinitas-cli-policy.py
uv run python3 scripts/test-signing-bootstrap.py
uv run python3 scripts/test-installed-skill-integrity.py
uv run python3 -m pytest tests/integration/test_long_release_script_selection.py -q
python3 scripts/test-transparency-log.py scenario_selector_smoke_test
python3 scripts/test-release-invariants.py scenario_missing_signers_blocks_tag_creation
```

Use these when you need repo-native regression coverage beyond the fast `tests/integration/` tier.
`scenario_selector_smoke_test` only verifies named-scenario selection for the transparency-log script; it is not a substitute for the full transparency release flow.

## Named `check-all` blocks

`scripts/check-all.sh` accepts named blocks so you can choose a narrow or broad sweep:

```bash
scripts/check-all.sh focused-integration
scripts/check-all.sh hosted-ui
scripts/check-all.sh release-long
scripts/check-all.sh full-regression
scripts/check-all.sh focused-integration hosted-ui release-long full-regression
```

Block intent:

- `focused-integration`: the fast maintained-surface `pytest` tier under `tests/integration/`, including hard maintainability budgets
- `hosted-ui`: homepage/private-registry HTML coverage plus optional browser runtime checks
- `release-long`: the full transparency-log and release-invariants long-running release checks
- `full-regression`: the broader compatibility, policy, catalog, install, and hosted-e2e matrix

Running `scripts/check-all.sh` with no arguments still executes the default three blocks in order; `release-long` is opt-in.

For formal release readiness, use this compact matrix:

```bash
make test-fast
uv run python3 -m pytest tests/integration/test_dev_workflow.py tests/integration/test_cli_policy.py tests/integration/test_cli_release_state.py tests/integration/test_cli_install_planning.py -q
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

When these pass together, the repository has covered:

- maintained CLI and workflow guards
- package-owned discovery, skills, registry, and signing/review migrations
- temp-repo release fixtures, provenance, and OpenClaw export/import flows
- long-running release invariants and transparency-log verification
