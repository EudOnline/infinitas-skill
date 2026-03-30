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

## Maintained surface scoreboard

- package-owned: `src/infinitas_skill/install/...`, `src/infinitas_skill/policy/...`, `src/infinitas_skill/release/...`, and `src/infinitas_skill/server/...` are the maintained home for reusable CLI logic.
- runtime-owned: `server/modules/...` and `server/ui/...` are the maintained home for hosted API and UI behavior; `server/app.py` should shrink toward bootstrap-only assembly.
- compatibility-only: `scripts/*.py` wrappers and leftover helper modules exist only where a bridge is still justified for compatibility, install, policy, registry, or release. The old server-operation wrappers are retired. Do not add new maintained shared logic there.

## Bridge inventory

| Family | Canonical entrypoint | Canonical status | Compatibility shim | Shim status |
| --- | --- | --- | --- | --- |
| compatibility | `infinitas compatibility check-platform-contracts` | maintained | `python3 scripts/check-platform-contracts.py ...` | shim |
| install | `infinitas install resolve-plan`, `infinitas install check-target` | maintained | `python3 scripts/resolve-install-plan.py ...`, `python3 scripts/check-install-target.py ...` | shim |
| policy | `infinitas policy check-packs`, `infinitas policy check-promotion` | maintained | `python3 scripts/check-policy-packs.py`, `python3 scripts/check-promotion-policy.py ...` | shim |
| registry | `infinitas registry ...` | maintained | `python3 scripts/registryctl.py ...` | shim |
| release | `infinitas release check-state` | maintained | `python3 scripts/check-release-state.py ...` | shim |
| server | `infinitas server healthcheck`, `infinitas server backup`, `infinitas server inspect-state`, `infinitas server render-systemd`, `infinitas server prune-backups`, `infinitas server worker` | maintained | none; wrapper scripts deleted after focused integration coverage | retired |

Legacy-only command families should not be introduced into maintained docs. If a surface has no canonical `infinitas ...` path yet, keep it out of the maintained inventory until the cutover decision is explicit.

## Alias cutoff table

| Family | Default shim removal checkpoint | Extension rule |
| --- | --- | --- |
| compatibility | `2026-06-30` | Add or update an ADR before extending the shim window |
| install | `2026-06-30` | Add or update an ADR before extending the shim window |
| policy | `2026-06-30` | Add or update an ADR before extending the shim window |
| registry | `2026-06-30` | Add or update an ADR before extending the shim window |
| release | `2026-06-30` | Add or update an ADR before extending the shim window |
| server | completed on `2026-03-30` | N/A; wrapper scripts already deleted |

Temporary modules such as `scripts/release_lib.py`, `scripts/platform_contract_lib.py`, and `scripts/compatibility_policy_lib.py` remain allowed only while a still-justified shim or package bridge depends on them. Once a family is package-owned end-to-end, remove the wrapper-facing helper too.
