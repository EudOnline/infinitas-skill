---
audience: operators, release maintainers, contributors
owner: repository maintainers
source_of_truth: 2026-04-01 release-readiness scorecard
last_reviewed: 2026-04-01
status: maintained
---

# 2026-04-01 Release Readiness Scorecard

## Verdict

Go for a controlled production rollout.

The repository is now in a release-capable state after the hard-cut maintainability cleanup:
the maintained CLI surface is package-owned, the discovery/recommend/install-explanation chain now
lives under `src/infinitas_skill/discovery`, the remaining reusable skill/registry/signing helpers
now live under `src/infinitas_skill/skills`, `src/infinitas_skill/registry`, `src/infinitas_skill/release`,
and `src/infinitas_skill/policy`, and the signing/review command surface has been collapsed into
`uv run infinitas ...`.

The main caveat is no longer architectural confusion; it is broad maintained-surface lint debt in
discovery, skills, release attestation, and integration guard files. That debt does not invalidate
the passing release and regression gates, but it does keep the maintainability score below an
unqualified production 10.

## Scores

| Category | Score | Evidence |
| --- | --- | --- |
| Release readiness | 9.4/10 | `./scripts/check-all.sh release-long`, `make test-fast`, `python3 scripts/test-signing-bootstrap.py`, `python3 scripts/test-signing-readiness-report.py`, `python3 scripts/test-infinitas-cli-release-state.py`, `python3 scripts/test-infinitas-cli-policy.py` |
| Maintainability | 8.5/10 | package-owned CLI and shared logic now live under `src/infinitas_skill/...`, but `make lint-maintained` still fails on broad pre-existing F403/E501 debt outside the just-collapsed command surface |
| Cleanup completion | 9.8/10 | deleted legacy shim surface, reusable script-lib clusters migrated into `src/`, signing/review commands folded into `infinitas`, temp-repo interpreter and nested release-helper verification centralized |

## Evidence Matrix

| Command | Status | Notes |
| --- | --- | --- |
| `make test-fast` | PASS | Fresh maintained-surface fast gate on 2026-04-01 after the current cleanup round. |
| `make lint-maintained` | FAIL | Fresh evidence on 2026-04-01 shows broad pre-existing maintained-surface F403/E501 debt in `src/infinitas_skill/discovery/...`, `src/infinitas_skill/skills/...`, `src/infinitas_skill/release/attestation.py`, and `tests/integration/test_dev_workflow.py`; this is a maintainability risk, not a release-path regression introduced by the CLI collapse. |
| `uv run python3 -m pytest tests/integration/test_dev_workflow.py tests/integration/test_cli_policy.py tests/integration/test_cli_release_state.py tests/integration/test_cli_install_planning.py -q` | PASS | Fresh CLI/integration matrix on 2026-04-01 after the current cleanup round. |
| `uv run python3 -m pytest tests/integration/test_dev_workflow.py -q` | PASS | Confirms wrapper guards and development workflow invariants remain green after the discovery, skills, registry, and signing/review moves. |
| `python3 scripts/test-infinitas-cli-policy.py` | PASS | Confirms `infinitas policy` now owns `check-packs`, `check-promotion`, `recommend-reviewers`, and `review-status`. |
| `python3 scripts/test-infinitas-cli-release-state.py` | PASS | Confirms `infinitas release` now owns `check-state`, `signing-readiness`, `doctor-signing`, and `bootstrap-signing`. |
| `python3 scripts/test-infinitas-cli-reference-docs.py` | PASS | Confirms the generated CLI reference matches the maintained argparse surface under the project toolchain. |
| `python3 scripts/test-doc-governance.py` | PASS | Confirms updated docs are linked from the maintained section landing pages after the command-surface collapse. |
| `python3 scripts/test-ai-index.py` | PASS | Confirms package-owned AI index generation still matches expected output. |
| `python3 scripts/test-discovery-index.py` | PASS | Confirms package-owned discovery index generation still matches expected output. |
| `python3 scripts/test-recommend-skill.py` | PASS | Confirms recommendation chain still resolves and ranks skills correctly. |
| `python3 scripts/test-explain-install.py` | PASS | Confirms install explanation flow still renders expected operator guidance. |
| `python3 scripts/test-install-by-name.py` | PASS | Confirms discovery-to-install resolution remains green. |
| `python3 scripts/test-skill-update.py` | PASS | Confirms update flow still works across the migrated discovery helpers. |
| `python3 scripts/test-canonical-skill.py` | PASS | Confirms canonical skill loading is now package-owned under `src/infinitas_skill/skills`. |
| `python3 scripts/test-render-skill.py` | PASS | Confirms skill rendering remains green after the `skills` package migration. |
| `python3 scripts/test-openclaw-export.py` | PASS | Confirms OpenClaw export still works after package-native skill surface and temp-repo env cleanup. |
| `python3 scripts/test-openclaw-import.py` | PASS | Confirms OpenClaw import still works after the `skills.openclaw` move. |
| `python3 scripts/test-registry-refresh-policy.py` | PASS | Confirms registry refresh-state logic now works from `src/infinitas_skill/registry/refresh_state.py`. |
| `python3 scripts/test-registry-snapshot-mirror.py` | PASS | Confirms registry snapshot creation and selection still work after the `registry.snapshot` move. |
| `python3 scripts/test-signing-bootstrap.py` | PASS | Confirms signing bootstrap rehearsal still works after moving helpers into `src/infinitas_skill/release/signing_bootstrap.py`. |
| `python3 scripts/test-signing-readiness-report.py` | PASS | Confirms signing readiness reporting still works after moving provenance/bootstrap helpers package-side. |
| `python3 scripts/test-platform-review-evidence.py` | PASS | Confirms imported review evidence and reviewer recommendation flows still work after the `policy.reviewer_rotation` move. |
| `python3 scripts/test-ai-pull.py` | PASS | Confirms AI pull result validation and temp-repo release flows remain green after the shared interpreter-helper cleanup. |
| `python3 scripts/test-transparency-log.py` | PASS | Full long-running release flow passed fresh on 2026-04-01 after the shared interpreter-helper cleanup. |
| `python3 scripts/test-release-invariants.py` | PASS | Full long-running invariant flow passed fresh on 2026-04-01 after the shared interpreter-helper cleanup. |
| `./scripts/check-all.sh release-long` | PASS | Canonical opt-in long release block; passed fresh on 2026-04-01 after the shared interpreter-helper cleanup. |

## Why The Score Is Not 10

- The maintained lint baseline is not yet green; wildcard-export package `__init__` files and long
  validation modules still create a substantial F403/E501 backlog.
- The repository is still in a dirty migration window, so some supporting scripts remain large and
  repo-specific even though the maintained business logic has moved into `src/`.
- Release evidence still depends on minute-scale script regressions rather than a fully package-native
  test harness for every long-running release scenario.

## Remaining Non-Blocking Risks

- `scripts/check-all.sh full-regression` is still a broad, slow sweep; it is valuable for release prep
  but too expensive to be the default inner-loop path.
- `make lint-maintained` still fails on broader discovery/skills/release-attestation debt, so code-health
  cleanup has not yet caught up with the architectural cleanup.
- Python environment bootstrapping is now centralized for the temp-repo release tests that exercise
  `release-skill.sh`, and nested release-helper check blocks are now forced down to `focused-integration`
  inside regression environments, but the broader script suite still contains other setup patterns that could be consolidated later.
- The repository still contains legacy-era automation wrappers under `scripts/`; they are thin and explicitly guarded now,
  but more wrapper retirement is still possible.

## Recommended Operator Path

Use this order before a formal release:

```bash
make test-fast
uv run python3 -m pytest tests/integration/test_dev_workflow.py tests/integration/test_cli_policy.py tests/integration/test_cli_release_state.py tests/integration/test_cli_install_planning.py -q
./scripts/check-all.sh release-long
```

If all three layers are green, the repository is ready for controlled production release handling.
Treat `make lint-maintained` as the next cleanup priority, not as a prerequisite for the just-verified
release path.
