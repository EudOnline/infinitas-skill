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
| `python3 scripts/server-healthcheck.py --api-url URL --repo-path PATH --artifact-path PATH --database-url URL [--token TOKEN] [--json]` | `uv run infinitas server healthcheck --api-url URL --repo-path PATH --artifact-path PATH --database-url URL [--token TOKEN] [--json]` | live shim | 2026-06-30 |
| `python3 scripts/backup-hosted-registry.py --repo-path PATH --database-url URL --artifact-path PATH --output-dir PATH [--label LABEL] [--json]` | `uv run infinitas server backup --repo-path PATH --database-url URL --artifact-path PATH --output-dir PATH [--label LABEL] [--json]` | live shim | 2026-06-30 |
| `python3 scripts/render-hosted-systemd.py --output-dir PATH --repo-root PATH --python-bin PATH --env-file PATH --backup-output-dir PATH ...` | `uv run infinitas server render-systemd --output-dir PATH --repo-root PATH --python-bin PATH --env-file PATH --backup-output-dir PATH ...` | live shim | 2026-06-30 |

## Planned families

The planned top-level families from the maintainability reset are now present:

- `infinitas compatibility ...`
- `infinitas release ...`
- `infinitas install ...`
- `infinitas policy ...`
- `infinitas registry ...`
- `infinitas server ...`

The current migrated surfaces are `infinitas compatibility check-platform-contracts`, `infinitas install resolve-plan`, `infinitas install check-target`, `infinitas policy check-packs`, `infinitas policy check-promotion`, `infinitas registry ...`, `infinitas release check-state`, `infinitas server healthcheck`, `infinitas server backup`, and `infinitas server render-systemd`. Remaining command migrations should move behind these families rather than adding fresh one-off scripts.
