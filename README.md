---
audience: contributors, operators, integrators
owner: repository maintainers
source_of_truth: repo entry page
last_reviewed: 2026-03-30
status: maintained
---

# infinitas-skill

Private-first skill registry and hosted control plane.

This repository is in a breaking maintainability reset. The runtime model remains private-first, while the code and docs are being reorganized around one Python package, one maintained CLI, and one role-based documentation tree.

## Start here

- [Documentation map](docs/README.md)
- [Maintainability reset policy](docs/guide/maintainability-reset-policy.md)
- [Reference docs](docs/reference/README.md)
- [Operator runbooks](docs/ops/README.md)
- [Architecture decisions](docs/adr/0001-maintainability-reset.md)

## Repository shape

- `src/infinitas_skill/`: maintained Python package and future home for shared runtime logic
- `scripts/`: legacy command and library surface; keep only temporary shims or not-yet-migrated tools here
- `server/`: hosted control-plane runtime
- `docs/`: role-based documentation during the reset

## Maintained CLI surface

Maintained entrypoints introduced so far:

```bash
uv run infinitas compatibility check-platform-contracts --max-age-days 30 --stale-policy fail
uv run infinitas install resolve-plan --skill-dir templates/basic-skill --target-dir .tmp-installed-skills --json
uv run infinitas policy check-packs
uv run infinitas registry --help
uv run infinitas release check-state <skill> --mode local-preflight --json
uv run infinitas server healthcheck --api-url http://127.0.0.1:8000 --repo-path /srv/infinitas/repo --artifact-path /srv/infinitas/artifacts --database-url sqlite:////srv/infinitas/data/server.db --json
uv run infinitas server prune-backups --backup-root /srv/infinitas/backups --keep-last 7 --json
```

Legacy wrappers such as `python3 scripts/check-release-state.py ...` remain available only as migration shims. That includes operator-facing shims like `python3 scripts/render-hosted-systemd.py ...` while the maintained CLI surface is still consolidating. New command surfaces should land under `infinitas`, not as new top-level scripts.

## Local verification

```bash
uv sync
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
```

Local runs default to `INFINITAS_SERVER_ENV=development`. Use `INFINITAS_SERVER_ENV=test` when you need fixture-safe automated behavior.

## Maintainability reset rules

- No new top-level script may be added under `scripts/` without explicit architecture approval.
- No new long-lived doc may be added outside `docs/guide/`, `docs/reference/`, `docs/ops/`, `docs/archive/`, or `docs/adr/`.
- New shared Python logic should land under `src/infinitas_skill/`.
- Compatibility aliases introduced during this reset expire on `2026-06-30` unless a later ADR extends them.

## Product and policy context

The supported runtime remains:

`skill -> draft -> sealed version -> release -> exposure -> review case -> grant/credential -> discovery/install`

Use these canonical docs for the current model:

- [Private-first cutover](docs/private-first-cutover.md)
- [Platform drift playbook](docs/platform-drift-playbook.md)
- [Release checklist](docs/release-checklist.md)
- [Hosted registry server deployment](docs/ops/server-deployment.md)

## Policy trace and validation output

Policy-aware commands continue to expose structured diagnostics for operators and automation:

- `scripts/check-promotion-policy.py --json` returns a `policy_trace` payload for promotion decisions.
- `scripts/check-release-state.py operate-infinitas-skill --json` returns the release decision plus `policy_trace` details.
- `scripts/validate-registry.py --json` returns `validation_errors` alongside namespace-level `policy_trace` data.
- `policy/team-policy.json` remains the default team-governance input that keeps review and release checks aligned.
