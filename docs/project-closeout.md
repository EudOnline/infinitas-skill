# Project Closeout

This document defines the final verification matrix and merge gates for declaring the current `infinitas-skill` closeout milestone complete.

## Scope

The closeout milestone is v20:

- make `never-verified` installs policy-governed through `freshness.never_verified_policy`
- reuse one shared mutation-readiness contract across report, update, explain, and overwrite-style mutation flows
- make hosted-registry e2e deterministic in CI
- define one stable branch-merge checklist for project completion

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
- Local minimal environments may still skip `scripts/test-hosted-registry-e2e.py` unless the same dependency set is installed explicitly.
- When local full hosted e2e coverage is desired, run `python3 -m pip install .` first, then run `python3 scripts/test-hosted-registry-e2e.py`.

## Merge Gates

The branch is ready to merge only when all of the following are true:

1. The full verification matrix above has been rerun with fresh output for the current branch tip.
2. `scripts/check-all.sh` passes from the branch tip.
3. The closeout docs and `.planning` state agree on v20 completion and the final operator decision matrix.
4. CI validation still enforces hosted-registry e2e dependency installation and `INFINITAS_REQUIRE_HOSTED_E2E_TESTS=1`.
5. Any remaining compatibility quirks are documented and accepted as non-blocking.
6. The merge back to `main` does not introduce unrelated unreviewed workspace changes.

## Accepted Compatibility Notes

The following are documented closeout notes, not release blockers for this milestone:

- Legacy installed-integrity reports may derive `freshness_state` from `integrity.last_verified_at` while leaving top-level `last_checked_at = null` until an explicit refresh rewrites the canonical field.
- Some older hosted distribution manifests may remain compatibility-only `unknown` when the repository lacks enough immutable historical evidence to backfill them deterministically.

## Project Complete Criteria

The current project phase can be treated as complete when:

1. v20 requirements `INST-09`, `INST-10`, `OPS-03`, and `OPS-04` are all complete on the branch.
2. The verification matrix has fresh passing evidence.
3. The branch has been merged back to `main`.
4. No new blocker is discovered during merge or CI validation.

After that point, any further work should be planned as a new milestone or follow-up cleanup, not as unfinished v20 scope.
