# Maintained Surface Convergence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce long-term maintenance cost by shrinking the legacy `scripts/` surface, splitting the heaviest remaining orchestration modules, and adding one stronger quality gate without changing the supported product model.

**Architecture:** Keep `uv run infinitas ...` as the maintained command surface and treat top-level `scripts/` as either compatibility shims or long-tail regression helpers. Attack the next round of cleanup in this order: remove redundant script wrappers first, then extract pure logic from heavy modules under `src/infinitas_skill/`, then ratchet budgets and CI so the repo cannot drift back.

**Tech Stack:** Python 3.11, setuptools, argparse CLI, FastAPI, SQLAlchemy, pytest, ruff, mypy, GitHub Actions, uv

---

## Convergence Priorities

1. Retire redundant script-based smoke tests that only proxy to pytest coverage.
2. Split the heaviest maintained modules that still concentrate too much policy or release logic.
3. Add one small but durable type-checking gate for the maintained package surface.
4. Ratchet maintainability budgets immediately after each cleanup so the reduction sticks.
5. Refresh the operator-facing scorecard once the repository shape actually improves.

### Task 1: Retire Redundant CLI Wrapper Scripts

**Files:**
- Delete: `scripts/test-infinitas-cli-policy.py`
- Delete: `scripts/test-infinitas-cli-install-planning.py`
- Delete: `scripts/test-infinitas-cli-release-state.py`
- Delete: `scripts/test-infinitas-cli-server-inspect.py`
- Modify: `README.md`
- Modify: `docs/reference/testing.md`
- Modify: `tests/integration/test_maintainability_budgets.py`
- Test: `tests/integration/test_cli_policy.py`
- Test: `tests/integration/test_cli_install_planning.py`
- Test: `tests/integration/test_cli_release_state.py`
- Test: `tests/integration/test_cli_server_ops.py`

**Step 1: Write the failing budget change**

Lower the script ceiling in `tests/integration/test_maintainability_budgets.py` from `231` to `221`.

Expected effect:
- the budget test fails while the four redundant wrapper scripts still exist

**Step 2: Run the budget test to verify it fails**

Run:

```bash
uv run pytest tests/integration/test_maintainability_budgets.py -q
```

Expected:
- FAIL with a message like `top-level script count exceeded reset ceiling`

**Step 3: Remove the redundant wrappers and update maintained docs**

Delete the four wrapper scripts that only proxy into existing pytest integration coverage:

- `scripts/test-infinitas-cli-policy.py`
- `scripts/test-infinitas-cli-install-planning.py`
- `scripts/test-infinitas-cli-release-state.py`
- `scripts/test-infinitas-cli-server-inspect.py`

Update maintained docs so they point at the supported verification entrypoints instead of those wrappers:

- `README.md`
- `docs/reference/testing.md`

Replace references with maintained commands such as:

```bash
uv run pytest tests/integration/test_cli_release_state.py -q
uv run pytest tests/integration/test_cli_install_planning.py -q
uv run pytest tests/integration/test_cli_policy.py -q
uv run pytest tests/integration/test_cli_server_ops.py -q
make test-fast
```

**Step 4: Re-run the focused tests and budget guard**

Run:

```bash
uv run pytest \
  tests/integration/test_cli_policy.py \
  tests/integration/test_cli_install_planning.py \
  tests/integration/test_cli_release_state.py \
  tests/integration/test_cli_server_ops.py \
  tests/integration/test_maintainability_budgets.py -q
```

Expected:
- all tests pass
- the repository script count is now at or below `221`

**Step 5: Commit**

```bash
git add README.md docs/reference/testing.md tests/integration/test_maintainability_budgets.py
git add -u scripts
git commit -m "chore: retire redundant cli wrapper scripts"
```

### Task 2: Split `src/infinitas_skill/install/distribution.py`

**Files:**
- Create: `src/infinitas_skill/install/distribution_bundle.py`
- Create: `src/infinitas_skill/install/distribution_verification.py`
- Create: `tests/unit/install/test_distribution_bundle.py`
- Create: `tests/unit/install/test_distribution_verification.py`
- Modify: `src/infinitas_skill/install/distribution.py`
- Modify: `tests/integration/test_maintainability_budgets.py`
- Test: `scripts/test-distribution-install.py`

**Step 1: Write the failing budget and new unit tests**

Add a new line budget for `src/infinitas_skill/install/distribution.py` to `<= 500` in `tests/integration/test_maintainability_budgets.py`.

Create focused unit tests with shapes like:

```python
def test_inspect_distribution_bundle_collects_sorted_file_manifest(tmp_path: Path) -> None:
    payload = inspect_distribution_bundle(tmp_path / "bundle.tar.gz", expected_root="demo")
    assert payload["build"]["archive_format"] == "tar.gz"


def test_installed_integrity_capability_summary_requires_signed_manifest() -> None:
    summary = installed_integrity_capability_summary({})
    assert summary["installed_integrity_capability"] == "unknown"
```

**Step 2: Run the new checks to verify they fail**

Run:

```bash
uv run pytest tests/unit/install/test_distribution_bundle.py tests/unit/install/test_distribution_verification.py tests/integration/test_maintainability_budgets.py -q
```

Expected:
- unit tests fail because the extracted modules do not exist yet
- or the budget test fails because `distribution.py` is still over the limit

**Step 3: Extract pure helpers out of the monolith**

Move code by responsibility:

- `distribution_bundle.py`
  - `sha256_file`
  - `_sha256_bytes`
  - `_gzip_mtime`
  - `inspect_distribution_bundle`
  - normalization helpers used only for bundle/reproducibility inspection
- `distribution_verification.py`
  - `reproducibility_summary`
  - `installed_integrity_capability_summary`
  - attestation/distribution verification helpers that do not belong in bundle assembly

Leave `distribution.py` as the high-level façade that imports and re-exports the extracted functions needed by callers.

**Step 4: Run unit, regression, and budget coverage**

Run:

```bash
uv run pytest tests/unit/install/test_distribution_bundle.py tests/unit/install/test_distribution_verification.py tests/integration/test_maintainability_budgets.py -q
uv run python3 scripts/test-distribution-install.py
```

Expected:
- new unit tests pass
- existing distribution regression script still passes
- `src/infinitas_skill/install/distribution.py` is at or under `500` lines

**Step 5: Commit**

```bash
git add src/infinitas_skill/install/distribution.py src/infinitas_skill/install/distribution_bundle.py src/infinitas_skill/install/distribution_verification.py tests/unit/install/test_distribution_bundle.py tests/unit/install/test_distribution_verification.py tests/integration/test_maintainability_budgets.py
git commit -m "refactor: split install distribution helpers"
```

### Task 3: Split `src/infinitas_skill/policy/reviews.py`

**Files:**
- Create: `src/infinitas_skill/policy/review_requirements.py`
- Create: `src/infinitas_skill/policy/review_results.py`
- Create: `tests/unit/policy/test_review_requirements.py`
- Create: `tests/unit/policy/test_review_results.py`
- Modify: `src/infinitas_skill/policy/reviews.py`
- Modify: `src/infinitas_skill/policy/service.py`
- Modify: `tests/integration/test_maintainability_budgets.py`
- Test: `tests/integration/test_cli_policy.py`

**Step 1: Write the failing budget and extraction tests**

Add a new line budget for `src/infinitas_skill/policy/reviews.py` to `<= 450`.

Create focused tests around:

- required approval counting
- required reviewer-group coverage
- blocking rejection handling
- normalized review decision summaries

Example shapes:

```python
def test_missing_groups_are_reported_when_required_group_has_no_approval() -> None:
    evaluation = evaluate_review_requirements(policy=policy, reviews=reviews, stage="active")
    assert evaluation["missing_groups"] == ["security"]


def test_blocking_rejection_count_only_counts_active_rejections() -> None:
    summary = summarize_review_results(reviews)
    assert summary["blocking_rejection_count"] == 1
```

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/policy/test_review_requirements.py tests/unit/policy/test_review_results.py tests/integration/test_maintainability_budgets.py -q
```

Expected:
- FAIL because the extracted modules do not exist yet
- or FAIL because `reviews.py` still exceeds the new budget

**Step 3: Extract policy logic by concern**

Split responsibilities this way:

- `review_requirements.py`
  - approval thresholds
  - reviewer-group requirements
  - stage-aware requirement evaluation
- `review_results.py`
  - decision normalization
  - rejection counting
  - aggregate review summaries used by service and CLI layers

Keep `reviews.py` as a compatibility façade or thin coordinator for callers that already import it.

Update `src/infinitas_skill/policy/service.py` so it consumes the extracted helpers directly where that makes the dependency graph clearer.

**Step 4: Re-run policy coverage**

Run:

```bash
uv run pytest tests/unit/policy/test_review_requirements.py tests/unit/policy/test_review_results.py tests/integration/test_cli_policy.py tests/integration/test_maintainability_budgets.py -q
```

Expected:
- new unit tests pass
- policy CLI integration coverage still passes
- `reviews.py` is at or under `450` lines

**Step 5: Commit**

```bash
git add src/infinitas_skill/policy/reviews.py src/infinitas_skill/policy/review_requirements.py src/infinitas_skill/policy/review_results.py src/infinitas_skill/policy/service.py tests/unit/policy/test_review_requirements.py tests/unit/policy/test_review_results.py tests/integration/test_maintainability_budgets.py
git commit -m "refactor: split policy review evaluation helpers"
```

### Task 4: Add A Maintained Type Gate

**Files:**
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: `.github/workflows/validate.yml`
- Test: `src/infinitas_skill/cli/main.py`
- Test: `src/infinitas_skill/install/planning.py`
- Test: `src/infinitas_skill/policy/cli.py`
- Test: `src/infinitas_skill/release/cli.py`
- Test: `src/infinitas_skill/root.py`

**Step 1: Write the failing type-check contract**

Add `mypy` to the dev dependency group and define a narrow maintained target list in `pyproject.toml`.

Suggested first-pass target set:

```toml
[dependency-groups]
dev = [
  "pytest>=8,<9",
  "ruff>=0.11,<1",
  "mypy>=1.11,<2",
]
```

Suggested command:

```bash
uv run mypy \
  src/infinitas_skill/cli/main.py \
  src/infinitas_skill/install/planning.py \
  src/infinitas_skill/policy/cli.py \
  src/infinitas_skill/release/cli.py \
  src/infinitas_skill/root.py
```

**Step 2: Run the new command and capture the first failure**

Run:

```bash
uv run mypy \
  src/infinitas_skill/cli/main.py \
  src/infinitas_skill/install/planning.py \
  src/infinitas_skill/policy/cli.py \
  src/infinitas_skill/release/cli.py \
  src/infinitas_skill/root.py
```

Expected:
- FAIL with the initial type issues for the maintained target set

**Step 3: Fix the narrow target set and wire it into local commands**

Add a `type-maintained` target to `Makefile` and make `ci-fast` run:

```bash
ci-fast: lint-maintained type-maintained test-fast
```

Keep the scope intentionally narrow for the first pass so the gate is stable and cheap.

**Step 4: Wire the same gate into CI**

Update `.github/workflows/validate.yml` so the maintained fast gate continues to run through `make ci-fast`.

Re-run:

```bash
make ci-fast
```

Expected:
- ruff passes
- mypy passes for the narrow maintained set
- fast tests pass

**Step 5: Commit**

```bash
git add pyproject.toml Makefile .github/workflows/validate.yml
git commit -m "ci: add maintained type gate"
```

### Task 5: Refresh The Maintained-Surface Scorecard

**Files:**
- Create: `docs/ops/2026-04-05-maintained-surface-convergence-scorecard.md`
- Modify: `README.md`
- Modify: `docs/ops/README.md`

**Step 1: Capture the post-cleanup evidence**

Run:

```bash
make ci-fast
uv run pytest tests/integration/test_maintainability_budgets.py -q
python3 - <<'PY'
from pathlib import Path
print(len([p for p in Path("scripts").iterdir() if p.is_file()]))
for rel in [
    "src/infinitas_skill/install/distribution.py",
    "src/infinitas_skill/policy/reviews.py",
]:
    print(rel, len(Path(rel).read_text(encoding="utf-8").splitlines()))
PY
```

Expected:
- maintained fast gate passes
- budget test passes
- script count is lower than the pre-plan baseline
- target modules are under their new ceilings

**Step 2: Write the scorecard**

Document:

- before/after script count
- before/after line counts for `distribution.py` and `reviews.py`
- current strengths
- remaining risks
- exact verification evidence and dates

**Step 3: Link the new scorecard from entry docs**

Update:

- `README.md`
- `docs/ops/README.md`

So the newest project-health snapshot is easy to find.

**Step 4: Run doc governance**

Run:

```bash
make doctor
```

Expected:
- documentation governance passes

**Step 5: Commit**

```bash
git add docs/ops/2026-04-05-maintained-surface-convergence-scorecard.md README.md docs/ops/README.md
git commit -m "docs: publish maintained surface convergence scorecard"
```

## Exit Criteria

- top-level script count is reduced from `225` to `221` or lower
- `src/infinitas_skill/install/distribution.py` is at or below `500` lines
- `src/infinitas_skill/policy/reviews.py` is at or below `450` lines
- `make ci-fast` includes a stable `mypy` pass for a narrow maintained target set
- maintained docs reference pytest and `make` entrypoints instead of redundant wrapper scripts
- the new scorecard captures the post-cleanup baseline

## Execution Notes

- Do not add any new top-level script under `scripts/` during this work.
- Prefer pure-function extraction before touching CLI wiring.
- Keep legacy import compatibility where existing callers still import `distribution.py` or `reviews.py`.
- Commit after each task so each reduction step can be reverted independently if needed.
