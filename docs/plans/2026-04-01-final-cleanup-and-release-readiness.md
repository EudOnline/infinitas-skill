# Final Cleanup And Release Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the last release-readiness evidence gaps, finish the next high-value package migration chain, and end with a defensible production-readiness score for the current hard-cut architecture.

**Architecture:** Treat the repository as already committed to a breaking maintainability reset: no legacy CLI compatibility layer, no new logic in deleted shim entrypoints, and no effort spent preserving old script names. Execute the remaining work in three passes: first make the two heavy release tests sliceable and green, then migrate the discovery/recommend/install-explanation chain into `src/infinitas_skill`, then run one final verification and scoring pass on the new steady-state structure.

**Tech Stack:** Python 3.11, package-native modules under `src/infinitas_skill`, thin `scripts/*_lib.py` wrappers, existing `scripts/test-*.py` regression style, `pytest` integration guards, Bash release scripts, and Markdown release/reference docs.

---

## Preconditions

- Work in the current repository state; do not try to clean or reset unrelated dirty files.
- Preserve the user's hard-cut decision: deleted shim commands stay deleted.
- Use `@superpowers:test-driven-development` before each behavior change.
- Use `@superpowers:verification-before-completion` before each completion claim or commit.
- Prefer completing one vertical chain fully before starting the next.

### Task 1: Make the two long release tests sliceable and measurable

**Files:**
- Create: `tests/integration/test_long_release_script_selection.py`
- Modify: `scripts/test-transparency-log.py`
- Modify: `scripts/test-release-invariants.py`
- Modify: `scripts/check-all.sh`
- Modify: `docs/reference/testing.md`

**Step 1: Write the failing selector regression**

Create `tests/integration/test_long_release_script_selection.py` with focused subprocess coverage that proves each long script can run a named scenario instead of always running the full suite.

Example test shape:

```python
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run_script(path: str, scenario: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["INFINITAS_SKIP_RELEASE_TESTS"] = "1"
    env["INFINITAS_SKIP_ATTESTATION_TESTS"] = "1"
    env["INFINITAS_SKIP_DISTRIBUTION_TESTS"] = "1"
    env["INFINITAS_SKIP_BOOTSTRAP_TESTS"] = "1"
    env["INFINITAS_SKIP_AI_WRAPPER_TESTS"] = "1"
    env["INFINITAS_SKIP_COMPAT_PIPELINE_TESTS"] = "1"
    env["INFINITAS_SKIP_INSTALLED_INTEGRITY_TESTS"] = "1"
    return subprocess.run(
        [sys.executable, str(ROOT / path), scenario],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )


def test_transparency_log_script_accepts_named_scenario():
    result = run_script(
        "scripts/test-transparency-log.py",
        "scenario_required_mode_requires_endpoint",
    )
    assert result.returncode == 0, result.stderr


def test_release_invariants_script_accepts_named_scenario():
    result = run_script(
        "scripts/test-release-invariants.py",
        "scenario_missing_signers_blocks_tag_creation",
    )
    assert result.returncode == 0, result.stderr
```

**Step 2: Run the new test to verify it fails**

Run:

```bash
uv run python3 -m pytest tests/integration/test_long_release_script_selection.py -q
```

Expected: FAIL because both scripts currently ignore scenario selection and always execute every scenario in `main()`.

**Step 3: Implement named-scenario selection in both long scripts**

Update `scripts/test-transparency-log.py` and `scripts/test-release-invariants.py` so they expose a `SCENARIOS` mapping and a `main(argv: list[str] | None = None)` that runs either all scenarios or only the names passed on the command line.

Implementation shape:

```python
SCENARIOS = {
    "scenario_missing_signers_blocks_tag_creation": scenario_missing_signers_blocks_tag_creation,
}


def main(argv: list[str] | None = None):
    selected = argv if argv is not None else sys.argv[1:]
    names = selected or list(SCENARIOS)
    for name in names:
        try:
            scenario = SCENARIOS[name]
        except KeyError as exc:
            available = ", ".join(sorted(SCENARIOS))
            raise SystemExit(f"unknown scenario {name!r}; available: {available}") from exc
        scenario()
    print("OK")
```

Use script-specific success text such as `OK: transparency log checks passed`.

**Step 4: Add a named long-suite entrypoint to `scripts/check-all.sh`**

Introduce a narrow suite mode so the heavy release checks can be run intentionally instead of being hidden inside ad hoc manual commands.

Expected shell shape:

```bash
if [[ "${1:-}" == "--suite" && "${2:-}" == "release-long" ]]; then
  python3 scripts/test-transparency-log.py
  python3 scripts/test-release-invariants.py
  exit 0
fi
```

Do not disturb the existing fast/default path.

**Step 5: Document the focused commands**

Update `docs/reference/testing.md` with the new targeted commands:

```bash
uv run python3 -m pytest tests/integration/test_long_release_script_selection.py -q
python3 scripts/test-transparency-log.py scenario_required_mode_requires_endpoint
python3 scripts/test-release-invariants.py scenario_missing_signers_blocks_tag_creation
./scripts/check-all.sh --suite release-long
```

**Step 6: Run the focused selector checks**

Run:

```bash
uv run python3 -m pytest tests/integration/test_long_release_script_selection.py -q
python3 scripts/test-transparency-log.py scenario_required_mode_requires_endpoint
python3 scripts/test-release-invariants.py scenario_missing_signers_blocks_tag_creation
```

Expected: PASS.

**Step 7: Commit**

```bash
git add tests/integration/test_long_release_script_selection.py scripts/test-transparency-log.py scripts/test-release-invariants.py scripts/check-all.sh docs/reference/testing.md
git commit -m "test: add selectable long release scenarios"
```

### Task 2: Close the transparency-log release evidence gap

**Files:**
- Modify: `scripts/test-transparency-log.py`
- Modify: `src/infinitas_skill/release/attestation.py`
- Modify: `src/infinitas_skill/release/transparency_log.py`
- Modify: `scripts/attestation_lib.py`
- Modify: `scripts/transparency_log_lib.py`
- Modify: `docs/reference/testing.md`

**Step 1: Run the transparency scenarios one by one and capture the first failure**

Run:

```bash
python3 scripts/test-transparency-log.py scenario_attestation_can_publish_to_transparency_log
python3 scripts/test-transparency-log.py scenario_release_flow_persists_transparency_proof_summary
python3 scripts/test-transparency-log.py scenario_verify_attestation_rejects_tampered_transparency_entry
python3 scripts/test-transparency-log.py scenario_required_transparency_mode_blocks_release_output
```

Expected: at least one scenario may fail or hang if `release-skill.sh` or proof normalization still has hidden regressions.

**Step 2: Convert the first failure into a tighter regression if needed**

If the failure is inside package code rather than script orchestration, add or tighten the nearest focused assertion in `scripts/test-transparency-log.py` before changing implementation.

Preferred assertion shape:

```python
entry = result.get("entry") or {}
if entry.get("attestation_sha256") != expected_digest:
    fail(f"expected attestation digest {expected_digest}, got {entry!r}")
```

**Step 3: Apply the minimal package-native fix**

Touch only the module that owns the failure:

- `src/infinitas_skill/release/transparency_log.py` for request/response normalization, proof validation, endpoint handling, and digest mismatch checks.
- `src/infinitas_skill/release/attestation.py` for release-flow persistence, provenance shaping, and required-vs-advisory gating.
- Keep `scripts/attestation_lib.py` and `scripts/transparency_log_lib.py` as import-only thin wrappers.

Wrapper shape must remain thin:

```python
from infinitas_skill.release.attestation import publish_attestation_to_transparency_log
```

**Step 4: Re-run the full transparency script**

Run:

```bash
python3 scripts/test-transparency-log.py
```

Expected: PASS with `OK: transparency log checks passed`.

**Step 5: Record the exact command in docs**

Append one short subsection to `docs/reference/testing.md` documenting that this is now a required pre-release gate:

```bash
python3 scripts/test-transparency-log.py
```

**Step 6: Commit**

```bash
git add scripts/test-transparency-log.py src/infinitas_skill/release/attestation.py src/infinitas_skill/release/transparency_log.py scripts/attestation_lib.py scripts/transparency_log_lib.py docs/reference/testing.md
git commit -m "fix: close transparency log release gap"
```

### Task 3: Close the release-invariants evidence gap

**Files:**
- Modify: `scripts/test-release-invariants.py`
- Modify: `src/infinitas_skill/release/state.py`
- Modify: `src/infinitas_skill/release/service.py`
- Modify: `src/infinitas_skill/release/git_state.py`
- Modify: `src/infinitas_skill/release/platform_state.py`
- Modify: `src/infinitas_skill/release/policy_state.py`
- Modify: `src/infinitas_skill/release/attestation_state.py`
- Modify: `docs/reference/testing.md`

**Step 1: Run the heaviest release invariant scenarios first**

Run:

```bash
python3 scripts/test-release-invariants.py scenario_release_succeeds_when_check_all_env_is_empty
python3 scripts/test-release-invariants.py scenario_signed_pushed_release_succeeds
python3 scripts/test-release-invariants.py scenario_existing_signed_tag_can_resume_release
```

Expected: any remaining regression should now surface in one of the real release-flow scenarios instead of being hidden inside the full script.

**Step 2: Add or tighten the nearest failing assertion before implementation**

If a scenario fails, keep the regression local to `scripts/test-release-invariants.py` and assert the exact output contract.

Example assertion shapes:

```python
assert_contains(combined, "verified attestation:", "release attestation summary")
assert_contains(combined, "expected release tag is missing", "missing tag error")
```

**Step 3: Fix only the owning release module**

Use the current release package boundaries:

- `src/infinitas_skill/release/git_state.py` for dirty worktree, ahead-of-upstream, and tag state.
- `src/infinitas_skill/release/platform_state.py` for compatibility freshness.
- `src/infinitas_skill/release/policy_state.py` for review, quorum, and exception application.
- `src/infinitas_skill/release/attestation_state.py` for signer and provenance checks.
- `src/infinitas_skill/release/service.py` or `src/infinitas_skill/release/state.py` only for orchestration.

Do not reintroduce logic into deleted shim commands.

**Step 4: Re-run the full release invariants script**

Run:

```bash
python3 scripts/test-release-invariants.py
```

Expected: PASS with `OK: release invariant checks passed`.

**Step 5: Wire the long release suite through the named orchestrator**

Run:

```bash
./scripts/check-all.sh --suite release-long
```

Expected: PASS and no dependency on removed shim command names.

**Step 6: Commit**

```bash
git add scripts/test-release-invariants.py src/infinitas_skill/release/state.py src/infinitas_skill/release/service.py src/infinitas_skill/release/git_state.py src/infinitas_skill/release/platform_state.py src/infinitas_skill/release/policy_state.py src/infinitas_skill/release/attestation_state.py docs/reference/testing.md
git commit -m "fix: close release invariant evidence gap"
```

### Task 4: Migrate the discovery and recommendation chain into the package

**Files:**
- Create: `src/infinitas_skill/discovery/__init__.py`
- Create: `src/infinitas_skill/discovery/ai_index.py`
- Create: `src/infinitas_skill/discovery/index.py`
- Create: `src/infinitas_skill/discovery/resolver.py`
- Create: `src/infinitas_skill/discovery/recommendation.py`
- Create: `src/infinitas_skill/discovery/install_explanation.py`
- Modify: `scripts/ai_index_lib.py`
- Modify: `scripts/discovery_index_lib.py`
- Modify: `scripts/discovery_resolver_lib.py`
- Modify: `scripts/recommend_skill_lib.py`
- Modify: `scripts/explain_install_lib.py`
- Modify: `scripts/test-ai-index.py`
- Modify: `scripts/test-discovery-index.py`
- Modify: `scripts/test-recommend-skill.py`
- Modify: `scripts/test-explain-install.py`
- Modify: `tests/integration/test_dev_workflow.py`

**Step 1: Add a failing wrapper-thinness guard**

Extend `tests/integration/test_dev_workflow.py` with a guard that fails if the five script libs above regain real logic instead of delegating into `src/infinitas_skill/discovery/...`.

Guard shape:

```python
def test_discovery_script_libs_stay_thin_wrappers():
    assert_wrapper_module("scripts/ai_index_lib.py", "infinitas_skill.discovery.ai_index")
    assert_wrapper_module("scripts/discovery_index_lib.py", "infinitas_skill.discovery.index")
    assert_wrapper_module("scripts/discovery_resolver_lib.py", "infinitas_skill.discovery.resolver")
    assert_wrapper_module("scripts/recommend_skill_lib.py", "infinitas_skill.discovery.recommendation")
    assert_wrapper_module("scripts/explain_install_lib.py", "infinitas_skill.discovery.install_explanation")
```

**Step 2: Run the guard to verify it fails**

Run:

```bash
uv run python3 -m pytest tests/integration/test_dev_workflow.py -q
```

Expected: FAIL because these five script libs still hold real logic.

**Step 3: Move the logic one library at a time**

Migration order:

1. `scripts/ai_index_lib.py` -> `src/infinitas_skill/discovery/ai_index.py`
2. `scripts/discovery_index_lib.py` -> `src/infinitas_skill/discovery/index.py`
3. `scripts/discovery_resolver_lib.py` -> `src/infinitas_skill/discovery/resolver.py`
4. `scripts/recommend_skill_lib.py` -> `src/infinitas_skill/discovery/recommendation.py`
5. `scripts/explain_install_lib.py` -> `src/infinitas_skill/discovery/install_explanation.py`

Keep each script lib as a thin compatibility wrapper, for example:

```python
from infinitas_skill.discovery.recommendation import recommend_skills

__all__ = ["recommend_skills"]
```

**Step 4: Re-run only the owning regression after each move**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
python3 scripts/test-recommend-skill.py
python3 scripts/test-explain-install.py
uv run python3 -m pytest tests/integration/test_dev_workflow.py -q
```

Expected: all PASS once the chain is fully migrated.

**Step 5: Commit**

```bash
git add src/infinitas_skill/discovery scripts/ai_index_lib.py scripts/discovery_index_lib.py scripts/discovery_resolver_lib.py scripts/recommend_skill_lib.py scripts/explain_install_lib.py scripts/test-ai-index.py scripts/test-discovery-index.py scripts/test-recommend-skill.py scripts/test-explain-install.py tests/integration/test_dev_workflow.py
git commit -m "refactor: migrate discovery recommendation chain into package"
```

### Task 5: Run the release-readiness closeout and publish the final score

**Files:**
- Modify: `docs/reference/testing.md`
- Modify: `README.md`
- Create: `docs/ops/2026-04-01-release-readiness-scorecard.md`

**Step 1: Run the final focused verification matrix**

Run:

```bash
uv run python3 -m pytest tests/integration/test_dev_workflow.py tests/integration/test_cli_policy.py tests/integration/test_cli_release_state.py tests/integration/test_cli_install_planning.py -q
python3 scripts/test-transparency-log.py
python3 scripts/test-release-invariants.py
python3 scripts/test-policy-pack-loading.py
python3 scripts/test-registry-refresh-policy.py
python3 scripts/test-registry-federation-rules.py
python3 scripts/test-hosted-registry-source.py
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-installed-integrity-never-verified-guardrails.py
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-integrity-history-retention.py
make test-fast
```

Expected: PASS across the full closeout matrix.

**Step 2: Write the scorecard**

Create `docs/ops/2026-04-01-release-readiness-scorecard.md` with:

- current production-readiness score
- maintainability score
- cleanup-completion score
- evidence list with exact commands and pass/fail status
- residual risks, if any
- explicit go/no-go recommendation

Use a compact table shape:

```markdown
| Category | Score | Evidence |
| --- | --- | --- |
| Release readiness | 9.4/10 | `python3 scripts/test-transparency-log.py`, `python3 scripts/test-release-invariants.py` |
```

**Step 3: Add one short repository entrypoint**

Update `README.md` and `docs/reference/testing.md` so a maintainer can find:

- the canonical CLI
- the long release suite
- the scorecard location

**Step 4: Commit**

```bash
git add docs/reference/testing.md README.md docs/ops/2026-04-01-release-readiness-scorecard.md
git commit -m "docs: publish release readiness scorecard"
```

## Recommended execution order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5

## Definition of done

- `scripts/test-transparency-log.py` passes end to end.
- `scripts/test-release-invariants.py` passes end to end.
- The discovery/recommend/install-explanation chain lives in `src/infinitas_skill`.
- Thin-wrapper guards cover the newly migrated script libs.
- The repository has a final release-readiness scorecard backed by exact passing commands.
