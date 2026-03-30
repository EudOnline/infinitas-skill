---
audience: contributors and operators
owner: repository maintainers
source_of_truth: maintained CLI migration map
last_reviewed: 2026-03-30
status: maintained
---

# CLI Command Map

The maintainability reset is consolidating maintained commands behind one CLI: `infinitas`.

## Live mappings

| Legacy surface | Maintained surface | Status | Alias removal date |
| --- | --- | --- | --- |
| `python3 scripts/check-platform-contracts.py [--max-age-days N] [--stale-policy warn|fail]` | `uv run infinitas compatibility check-platform-contracts [--max-age-days N] [--stale-policy warn|fail]` | live shim | 2026-06-30 |
| `python3 scripts/resolve-install-plan.py --skill-dir PATH [--target-dir PATH] [--source-registry NAME] [--source-json JSON] [--mode install|sync] [--json]` | `uv run infinitas install resolve-plan --skill-dir PATH [--target-dir PATH] [--source-registry NAME] [--source-json JSON] [--mode install|sync] [--json]` | live shim | 2026-06-30 |
| `python3 scripts/check-install-target.py SKILL_DIR TARGET_DIR [--source-registry NAME] [--source-json JSON] [--mode install|sync] [--json]` | `uv run infinitas install check-target SKILL_DIR TARGET_DIR [--source-registry NAME] [--source-json JSON] [--mode install|sync] [--json]` | live shim | 2026-06-30 |
| `python3 scripts/check-policy-packs.py` | `uv run infinitas policy check-packs` | live shim | 2026-06-30 |
| `python3 scripts/check-promotion-policy.py [TARGET ...] [--as-active] [--json] [--debug-policy]` | `uv run infinitas policy check-promotion [TARGET ...] [--as-active] [--json] [--debug-policy]` | live shim | 2026-06-30 |
| `python3 scripts/registryctl.py ...` | `uv run infinitas registry ...` | live shim | 2026-06-30 |
| `python3 scripts/check-release-state.py <skill> --mode <mode> [--json] [--debug-policy]` | `uv run infinitas release check-state <skill> --mode <mode> [--json] [--debug-policy]` | live shim | 2026-06-30 |

## Planned families

The target CLI layout for later slices is:

- `infinitas server ...`

The current migrated surfaces are `infinitas compatibility check-platform-contracts`, `infinitas install resolve-plan`, `infinitas install check-target`, `infinitas policy check-packs`, `infinitas policy check-promotion`, `infinitas registry ...`, and `infinitas release check-state`. Remaining families should move behind `infinitas` rather than adding fresh one-off scripts.
