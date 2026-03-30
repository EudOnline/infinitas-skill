---
audience: contributors and maintainers
owner: repository maintainers
source_of_truth: temporary reset policy
last_reviewed: 2026-03-30
status: maintained
---

# Maintainability Reset Policy

This repository is in a breaking maintainability reset. Backward compatibility is not the primary constraint for repository shape, command layout, or document placement during this migration.

## Target top-level structure

The reset is converging on these primary homes:

- `src/infinitas_skill/`
- `tests/`
- `docs/guide/`
- `docs/reference/`
- `docs/ops/`
- `docs/archive/`
- `docs/adr/`

## Temporary contributor rules

- Treat `scripts/` as a legacy surface. Do not add a new top-level script there unless architecture review explicitly approves it.
- Put new shared Python logic under `src/infinitas_skill/`.
- Put new long-lived docs only under `docs/guide/`, `docs/reference/`, `docs/ops/`, `docs/archive/`, or `docs/adr/`.
- If a top-level legacy doc is still needed, link it from one of the maintained landing pages instead of creating a parallel new entrypoint.

## Compatibility shim policy

Thin wrappers may exist for one migration window when they materially reduce rollout risk. They are not permanent API promises.

The current cutoff for removing maintainability-reset aliases is `2026-06-30`. Any wrapper still required after that date should be justified by a new ADR instead of silently persisting forever.

## What is maintained today

- `infinitas compatibility check-platform-contracts` is the maintained CLI path for platform contract freshness checks.
- `infinitas install resolve-plan` and `infinitas install check-target` are the maintained CLI paths for install dependency planning.
- `infinitas release check-state` is the maintained CLI path for release state checks.
- `python3 scripts/check-platform-contracts.py ...` remains a compatibility shim during the migration window.
- `python3 scripts/resolve-install-plan.py ...` and `python3 scripts/check-install-target.py ...` remain compatibility shims during the migration window.
- `python3 scripts/check-release-state.py ...` remains a compatibility shim during the migration window.
- `scripts/release_lib.py`, `scripts/platform_contract_lib.py`, and `scripts/compatibility_policy_lib.py` remain temporary compatibility modules because other legacy scripts still import them.
