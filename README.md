---
audience: contributors, operators, integrators
owner: repository maintainers
source_of_truth: repo entry page
last_reviewed: 2026-04-03
status: maintained
---

# infinitas-skill

Private-first skill registry and hosted control plane.

This repository is production-oriented and in an active maintainability hardening phase. The runtime model remains private-first, while the code and docs continue consolidating around one Python package, one maintained CLI, and one role-based documentation tree.

## Start here

- [Documentation map](docs/README.md)
- [Reference docs](docs/reference/README.md)
- [Operator runbooks](docs/ops/README.md)
- [2026-04-02 project health scorecard](docs/ops/2026-04-02-project-health-scorecard.md)
- [Architecture decision 0001: Maintainability reset](docs/adr/0001-maintainability-reset.md)
- [Architecture decision 0002: Maintained surface cutover](docs/adr/0002-maintained-surface-cutover.md)

## Repository shape

- `src/infinitas_skill/`: maintained Python package and future home for shared runtime logic
- `scripts/`: repository automation, validation, packaging, and compatibility-era helpers that are being actively reduced
- `server/`: hosted control-plane runtime
- `docs/`: role-based documentation during the reset

## Maintained surfaces

- package-owned: `src/infinitas_skill/install/...`, `src/infinitas_skill/policy/...`, `src/infinitas_skill/release/...`, and `src/infinitas_skill/server/...` own maintained CLI logic.
- runtime-owned: `server/modules/...` and `server/ui/...` own hosted API, UI, and presentation logic, while `server/app.py` stays focused on app assembly.
- automation-owned: remaining top-level scripts exist for repository automation, catalog generation, release packaging, and targeted regression coverage; canonical user-facing command surfaces live under `infinitas`.

## Maintained CLI surface

Maintained entrypoints introduced so far:

```bash
uv run infinitas compatibility check-platform-contracts --max-age-days 30 --stale-policy fail
uv run infinitas install resolve-plan --skill-dir templates/basic-skill --target-dir .tmp-installed-skills --json
uv run infinitas policy check-packs
uv run infinitas policy recommend-reviewers <skill> --as-active --json
uv run infinitas policy review-status <skill> --as-active --require-pass --json
uv run infinitas registry --help
uv run infinitas release check-state <skill> --mode local-preflight --json
uv run infinitas release signing-readiness --skill <skill> --json
uv run infinitas release doctor-signing <skill> --json
uv run infinitas release bootstrap-signing --help
uv run infinitas server healthcheck --api-url http://127.0.0.1:8000 --repo-path /srv/infinitas/repo --artifact-path /srv/infinitas/artifacts --database-url sqlite:////srv/infinitas/data/server.db --json
uv run infinitas server memory-curation --database-url sqlite:////srv/infinitas/data/server.db --action plan --limit 50 --json
uv run infinitas server memory-curation --database-url sqlite:////srv/infinitas/data/server.db --action archive --apply --max-actions 10 --json
uv run infinitas server memory-curation --database-url sqlite:////srv/infinitas/data/server.db --action prune --apply --max-actions 5 --json
uv run infinitas server memory-health --database-url sqlite:////srv/infinitas/data/server.db --limit 20 --json
uv run infinitas server prune-backups --backup-root /srv/infinitas/backups --keep-last 7 --json
```

`uv run infinitas ...` is the maintained CLI surface. New command surfaces should land under `infinitas`, not as new top-level scripts.

## Local verification

Preferred maintained-surface entrypoints:

```bash
make bootstrap
make clean-local
make ci-fast
make test-fast
make test-full
make lint-maintained
uv run pytest tests/integration/test_memory_evaluation_matrix.py -q
```

`make clean-local` is the supported local hygiene path for generated artifacts and local automation
output (`__pycache__`, `*.pyc`, test/lint caches, local `*.egg-info` metadata, and
`output/playwright`). It intentionally preserves tracked files, including placeholders such as
`build/.gitkeep`.

`make ci-fast` mirrors the maintained CI fast gate by running `make lint-maintained` and then
`make test-fast` before the repository drops to the broader closeout matrix.

`make test-fast` is now the default fast path for maintained work. It covers the focused integration tier,
the promoted high-value pytest regressions, and the maintainability budget gate before you drop to raw
fallback commands.

Raw commands remain available as fallback detail:

```bash
uv sync
uv run pytest tests/integration/test_cli_release_state.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_ui.py -q
uv run ruff check src/infinitas_skill server/ui server/app.py tests/integration tests/unit
uv run python3 scripts/test-platform-contracts.py
uv run python3 scripts/test-install-manifest-compat.py
uv run python3 scripts/test-release-invariants.py
uv run python3 scripts/test-infinitas-cli-release-state.py
uv run python3 scripts/test-infinitas-cli-platform-contracts.py
uv run python3 scripts/test-infinitas-cli-install-planning.py
uv run python3 scripts/test-infinitas-cli-policy.py
uv run python3 scripts/test-infinitas-cli-registry.py
uv run python3 scripts/test-infinitas-cli-server.py
uv run python3 scripts/test-infinitas-cli-reference-docs.py
uv run python3 scripts/test-doc-governance.py
./scripts/check-all.sh
./scripts/check-all.sh release-long
```

Use `./scripts/check-all.sh release-long` as the canonical opt-in long-running pre-release gate. It is the
smallest named block that proves the transparency-log and release-invariant flows end to end.

`make lint-maintained` currently enforces the maintained-surface `E/F/I` baseline while temporarily deferring
`E501` only in the current debt-heavy maintained files, plus a few legacy path-bootstrap `E402` cases, until the
planned module splits land.

Hard maintainability budgets now backstop the maintained reset:

- `server/app.py` must stay at or below 80 lines
- `src/infinitas_skill/server/ops.py` must stay at or below 550 lines
- `src/infinitas_skill/install/service.py` must stay at or below 650 lines
- `src/infinitas_skill/release/service.py` must stay at or below 650 lines
- `server/ui/lifecycle.py` must stay at or below 500 lines
- top-level files under `scripts/` must stay at or below 231 until a deliberate cleanup changes the ceiling

`tests/integration/test_maintainability_budgets.py` and `scripts/check-all.sh focused-integration` enforce these limits.

Local runs default to `INFINITAS_SERVER_ENV=development`. Use `INFINITAS_SERVER_ENV=test` when you need fixture-safe automated behavior.

## Maintainability reset rules

- No new top-level script may be added under `scripts/` without explicit architecture approval.
- Do not raise maintained-module line budgets or the top-level script ceiling without updating docs and the budget test in the same change.
- No new long-lived doc may be added outside `docs/guide/`, `docs/reference/`, `docs/ops/`, `docs/archive/`, or `docs/adr/`.
- New shared Python logic should land under `src/infinitas_skill/`.
- Do not add or restore compatibility wrapper entrypoints once a canonical `infinitas ...` command exists.

## Product and policy context

The supported runtime remains:

`skill -> draft -> sealed version -> release -> exposure -> review case -> grant/credential -> discovery/install`

Use these canonical docs for the current model:

- [Private-first cutover](docs/guide/private-first-cutover.md)
- [Memory operating model](docs/ai/memory.md)
- [AI workflow drills](docs/ai/workflow-drills.md) explains when to use `scripts/recommend-skill.sh`, `scripts/search-skills.sh`, and `scripts/inspect-skill.sh` for task routing.
- [Platform drift playbook](docs/ops/platform-drift-playbook.md)
- [Release checklist](docs/ops/release-checklist.md)
- [Project health scorecard](docs/ops/2026-04-02-project-health-scorecard.md)
- [CI-native attestation](docs/ai/ci-attestation.md) documents `.github/workflows/release-attestation.yml` and `python3 scripts/verify-ci-attestation.py`
- [Hosted registry server deployment](docs/ops/server-deployment.md)

Compatibility reporting now distinguishes between `declared support` from authored metadata such as `_meta.json.agent_compatible` and `verified support` backed by platform-specific evidence plus freshness checks.

The optional memory layer is additive only:

- recommendation and inspect may include advisory memory fields
- lifecycle events may emit best-effort memory writeback attempts plus traceable audit events
- fixture-backed memory evaluation now lives in `tests/integration/test_memory_evaluation_matrix.py`
- the evaluation matrix now checks duplicate suppression and noisy recall stability
- operator-facing curation planning and guarded archive/prune execution now live behind `uv run infinitas server memory-curation ...`
- operator-facing writeback diagnostics now live behind `uv run infinitas server memory-health ...`
- release, review, access, and install truth still comes from the local database, immutable artifacts, and current policy checks

## Policy trace and validation output

Policy-aware commands continue to expose structured diagnostics for operators and automation:

- `uv run infinitas policy check-promotion <skill> --json` returns a `policy_trace` payload for promotion decisions.
- `uv run infinitas policy review-status <skill> --as-active --show-recommendations --json` returns review gate status plus reviewer guidance.
- `uv run infinitas release signing-readiness --skill operate-infinitas-skill --json` summarizes repo signing trust and per-skill readiness.
- `uv run infinitas release check-state operate-infinitas-skill --json` returns the release decision plus `policy_trace` details.
- `scripts/validate-registry.py --json` returns `validation_errors` alongside namespace-level `policy_trace` data.
- `policy/policy-packs.json` selects ordered shared defaults from `policy/packs/*.json`, while repository-local policy files remain the last override layer.
- `policy/team-policy.json` remains the default team-governance input that keeps review and release checks aligned.
