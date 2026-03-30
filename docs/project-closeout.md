# Project Closeout

This document records the final verification matrix and steady-state guidance for the completed `infinitas-skill` project.

The current `infinitas-skill` project is complete on `main`.

## Scope

The closeout milestone is v20:

- make `never-verified` installs policy-governed through `freshness.never_verified_policy`
- reuse one shared mutation-readiness contract across report, update, explain, and overwrite-style mutation flows
- make hosted-registry e2e deterministic in CI
- define one stable steady-state verification guide for project completion

## 90+ Hardening Status

The final hardening slice is now part of steady-state project truth:

- browser auth uses server-owned session cookies, with authenticated UI state hydrated from `/api/auth/me` instead of client-side cookie parsing
- production startup requires an explicit secret and explicit bootstrap operators whenever `INFINITAS_SERVER_ENV=production`
- personal token authentication resolves through hashed credential records instead of plaintext `users.token` lookups
- the maintained regression matrix in `scripts/check-all.sh` enforces these guardrails alongside the existing hosted-registry contract
- The old `scripts/server-healthcheck.py`, `scripts/backup-hosted-registry.py`, `scripts/inspect-hosted-state.py`, `scripts/render-hosted-systemd.py`, `scripts/prune-hosted-backups.py`, and `scripts/run-hosted-worker.py` wrappers are retired.

## Final Readiness Matrix

Overwrite-style mutation now follows one precedence order:

1. `drifted` blocks first
2. `stale` consults `freshness.stale_policy`
3. `never-verified` consults `freshness.never_verified_policy`
4. `--force` bypasses the local readiness guardrails deliberately

Use this operator matrix when interpreting mutation output:

| Condition | Typical readiness | Recovery path |
| --- | --- | --- |
| `integrity.state = drifted` | `blocked` | `scripts/repair-installed-skill.sh` or explicit drift inspection |
| `freshness_state = stale` | `warning` or `blocked`, depending on policy | `python3 scripts/report-installed-integrity.py <target-dir> --refresh` |
| `freshness_state = never-verified` with refreshable immutable source metadata | `warning` or `blocked`, depending on policy | `python3 scripts/report-installed-integrity.py <target-dir> --refresh` |
| `freshness_state = never-verified` with compatibility-only immutable evidence | `warning` or `blocked`, depending on policy | backfill the signed distribution manifest or reinstall from a trusted immutable source |
| explicit `--force` | bypass | use only when intentionally overriding local readiness checks |

## Verification Matrix

Fresh closeout verification should run these commands:

```bash
uv run pytest tests/integration/test_cli_release_state.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_ui.py -q
uv run python3 scripts/test-settings-hardening.py
uv run python3 scripts/test-private-first-cutover-schema.py
uv run python3 scripts/test-private-registry-access-api.py
uv run python3 scripts/test-home-kawaii-theme.py
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-home-auth-session-runtime.py
python3 scripts/test-project-complete-state.py
python3 scripts/test-installed-integrity-never-verified-guardrails.py
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
python3 scripts/test-distribution-install.py
./scripts/check-all.sh
```

Hosted-registry end-to-end expectations:

- CI is authoritative for the fully supported hosted-registry path.
- `.github/workflows/validate.yml` installs dependencies with `python3 -m pip install .`.
- CI then runs `scripts/check-all.sh` with `INFINITAS_REQUIRE_HOSTED_E2E_TESTS=1`, so hosted e2e cannot silently skip there.
- `scripts/check-all.sh` now defaults to `focused-integration`, `hosted-ui`, and `full-regression` as the closeout gate.
- That default includes the maintained fast tier plus the broader matrix.
- `scripts/check-all.sh` also includes the settings hardening, private access cutover, and private UI regression checks from the 90+ upgrade slice.
- `scripts/test-home-auth-session-runtime.py` remains part of the maintained matrix, but it depends on the Codex Playwright wrapper under `$CODEX_HOME`; when that wrapper is unavailable, `scripts/check-all.sh` reports a skip instead of pretending the browser runtime check passed.
- Local minimal environments may still skip `scripts/test-hosted-registry-e2e.py` unless the same dependency set is installed explicitly.
- Local minimal environments may also skip `scripts/test-home-auth-session-runtime.py` unless the Codex Playwright skill wrapper is installed explicitly.
- When local full hosted e2e coverage is desired, run `python3 -m pip install .` first, then run `python3 scripts/test-hosted-registry-e2e.py`.
- Fresh local verification was rerun on 2026-03-29 for the upgraded regression matrix; hosted-registry e2e remained CI-authoritative because the full optional dependency set was not installed in the local environment.

## Steady-State Guidance

For future maintenance, keep all of the following true:

1. The full verification matrix above is rerun whenever installed-integrity or hosted-registry behavior changes.
2. `scripts/check-all.sh` passes from the current `main` truth.
3. The closeout docs and `.planning` state continue to agree that v20 is complete on `main` and that the operator decision matrix remains current.
4. CI validation still enforces hosted-registry e2e dependency installation and `INFINITAS_REQUIRE_HOSTED_E2E_TESTS=1`.
5. Any remaining compatibility quirks stay documented and accepted as non-blocking unless a concrete user-facing defect appears.

## Accepted Compatibility Notes

The following are documented closeout notes, not release blockers for this milestone:

- Legacy installed-integrity reports may derive `freshness_state` from `integrity.last_verified_at` while leaving top-level `last_checked_at = null` until an explicit refresh rewrites the canonical field.
- Some older hosted distribution manifests may remain compatibility-only `unknown` when the repository lacks enough immutable historical evidence to backfill them deterministically.

## Completion Record

This repository is complete because:

1. v20 requirements `INST-09`, `INST-10`, `OPS-03`, and `OPS-04` are all complete on `main`.
2. The verification matrix defines the maintained regression baseline for ongoing steady-state work.
3. CI still enforces the supported hosted-registry dependency path and the authoritative `scripts/check-all.sh` run.
4. The remaining compatibility notes are documented and accepted as non-blocking.

Future work belongs to a new milestone or maintenance slice, not unfinished v20 scope.
