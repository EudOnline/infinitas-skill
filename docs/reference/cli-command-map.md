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
| `python3 scripts/check-release-state.py <skill> --mode <mode> [--json] [--debug-policy]` | `uv run infinitas release check-state <skill> --mode <mode> [--json] [--debug-policy]` | live shim | 2026-06-30 |

## Planned families

The target CLI layout for later slices is:

- `infinitas compatibility ...`
- `infinitas release ...`
- `infinitas install ...`
- `infinitas registry ...`
- `infinitas policy ...`
- `infinitas server ...`

The current migrated surfaces are `infinitas compatibility check-platform-contracts` and `infinitas release check-state`. Remaining families should move behind `infinitas` rather than adding fresh one-off scripts.
