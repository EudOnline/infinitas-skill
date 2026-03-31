---
audience: contributors and operators
owner: repository maintainers
source_of_truth: maintained CLI migration map
last_reviewed: 2026-03-30
status: maintained
---

# CLI Command Map

The maintainability reset is consolidating maintained commands behind one CLI: `infinitas`.

For contributor verification, prefer the repo-native `make bootstrap`, `make test-fast`, `make test-full`,
and `make lint-maintained` entrypoints before dropping to raw `uv run infinitas ...` or `python3 scripts/...`
commands.

Status terms in this map:

- `maintained`: canonical `infinitas ...` entrypoint
- `shim`: compatibility wrapper still available during the reset
- `legacy-only`: surface has no canonical maintained entrypoint yet and should not be treated as the preferred path

## Live mappings

| Family | Canonical entrypoint | Canonical status | Compatibility surface | Compatibility status | Alias removal date |
| --- | --- | --- | --- | --- | --- |
| compatibility | `uv run infinitas compatibility check-platform-contracts [--max-age-days N] [--stale-policy warn|fail]` | maintained | `python3 scripts/check-platform-contracts.py [--max-age-days N] [--stale-policy warn|fail]` | shim | 2026-06-30 |
| install | `uv run infinitas install resolve-plan --skill-dir PATH [--target-dir PATH] [--source-registry NAME] [--source-json JSON] [--mode install|sync] [--json]` | maintained | `python3 scripts/resolve-install-plan.py --skill-dir PATH [--target-dir PATH] [--source-registry NAME] [--source-json JSON] [--mode install|sync] [--json]` | shim | 2026-06-30 |
| install | `uv run infinitas install check-target SKILL_DIR TARGET_DIR [--source-registry NAME] [--source-json JSON] [--mode install|sync] [--json]` | maintained | `python3 scripts/check-install-target.py SKILL_DIR TARGET_DIR [--source-registry NAME] [--source-json JSON] [--mode install|sync] [--json]` | shim | 2026-06-30 |
| policy | `uv run infinitas policy check-packs` | maintained | `python3 scripts/check-policy-packs.py` | shim | 2026-06-30 |
| policy | `uv run infinitas policy check-promotion [TARGET ...] [--as-active] [--json] [--debug-policy]` | maintained | `python3 scripts/check-promotion-policy.py [TARGET ...] [--as-active] [--json] [--debug-policy]` | shim | 2026-06-30 |
| registry | `uv run infinitas registry ...` | maintained | `python3 scripts/registryctl.py ...` | shim | 2026-06-30 |
| release | `uv run infinitas release check-state <skill> --mode <mode> [--json] [--debug-policy]` | maintained | `python3 scripts/check-release-state.py <skill> --mode <mode> [--json] [--debug-policy]` | shim | 2026-06-30 |
| server | `uv run infinitas server healthcheck --api-url URL --repo-path PATH --artifact-path PATH --database-url URL [--token TOKEN] [--json]` | maintained | none; use the canonical CLI directly | retired | completed 2026-03-30 |
| server | `uv run infinitas server backup --repo-path PATH --database-url URL --artifact-path PATH --output-dir PATH [--label LABEL] [--json]` | maintained | none; use the canonical CLI directly | retired | completed 2026-03-30 |
| server | `uv run infinitas server inspect-state --database-url URL [--limit N] [--max-queued-jobs N] [--max-running-jobs N] [--max-failed-jobs N] [--max-warning-jobs N] [--alert-webhook-url URL] [--alert-fallback-file PATH] [--json]` | maintained | none; use the canonical CLI directly | retired | completed 2026-03-30 |
| server | `uv run infinitas server render-systemd --output-dir PATH --repo-root PATH --python-bin PATH --env-file PATH --backup-output-dir PATH ...` | maintained | none; use the canonical CLI directly | retired | completed 2026-03-30 |
| server | `uv run infinitas server prune-backups --backup-root PATH --keep-last N [--json]` | maintained | none; use the canonical CLI directly | retired | completed 2026-03-30 |
| server | `uv run infinitas server worker [--poll-interval SECONDS] [--once] [--limit N]` | maintained | none; use the canonical CLI directly | retired | completed 2026-03-30 |

## Planned families

The planned top-level families from the maintainability reset are now present and maintained:

- `infinitas compatibility ...`
- `infinitas release ...`
- `infinitas install ...`
- `infinitas policy ...`
- `infinitas registry ...`
- `infinitas server ...`

Legacy-only commands should migrate behind one of these maintained families instead of adding fresh one-off scripts.
