# Project Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raise the repository from a solid production-oriented baseline to a more durable, easier-to-evolve maintained surface without changing the supported product model.

**Architecture:** Keep the current private-first runtime and maintained CLI surface intact, but reduce coordination cost around the heaviest orchestration files, local environment hygiene, and documentation drift. Optimize by shrinking orchestration modules, increasing test precision around extracted seams, and making the fast verification path the obvious default everywhere.

**Tech Stack:** Python 3.11, setuptools, argparse CLI, FastAPI, SQLAlchemy, pytest, ruff, GitHub Actions, uv

---

## Optimization Priorities

1. Stabilize the source of truth so docs, scorecards, and current verification status agree.
2. Reduce maintainability risk in files already near budget ceilings.
3. Improve local development hygiene without expanding the top-level `scripts/` surface.
4. Increase confidence with smaller, more targeted tests around extracted orchestration seams.
5. Keep CI aligned with the maintained fast path so future cleanup work stays cheap.

### Task 1: Refresh The Project Baseline

**Files:**
- Create: `docs/ops/2026-04-02-project-health-scorecard.md`
- Modify: `README.md`
- Modify: `docs/ops/README.md`

**Step 1: Capture the current maintained baseline**

Run:

```bash
uv run pytest tests/integration/test_cli_release_state.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_ui.py -q
uv run ruff check src/infinitas_skill server/ui server/app.py tests/integration tests/unit
```

Expected:
- pytest passes
- ruff passes

**Step 2: Write the new scorecard**

Document:
- current overall score
- current strengths
- current risks
- exact verification evidence with dates
- the gap between architectural cleanup and remaining module-size pressure

**Step 3: Link the scorecard from maintained entry docs**

Update:
- `README.md`
- `docs/ops/README.md`

So the freshest operational assessment is easy to find.

**Step 4: Run doc governance checks**

Run:

```bash
make doctor
```

Expected:
- documentation governance passes

**Step 5: Commit**

```bash
git add docs/ops/2026-04-02-project-health-scorecard.md README.md docs/ops/README.md
git commit -m "docs: refresh project health baseline"
```

### Task 2: Add A Supported Local Hygiene Path

**Files:**
- Modify: `Makefile`
- Modify: `.gitignore`
- Modify: `README.md`

**Step 1: Write the failing expectation as a docs-level contract**

Add a short section in `README.md` describing a supported local cleanup path for:
- `__pycache__`
- `.pytest_cache`
- `.ruff_cache`
- local build metadata such as `*.egg-info`

**Step 2: Add the minimal supported command surface**

Add a `make clean-local` or `make clean-dev` target that removes local generated artifacts without touching tracked files and without adding a new top-level script under `scripts/`.

Suggested command shape:

```bash
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
find . -type f -name '*.pyc' -delete
rm -rf .pytest_cache .ruff_cache build infinitas_hosted_registry.egg-info
```

**Step 3: Verify the command is safe**

Run:

```bash
make clean-local
git status --short
```

Expected:
- generated artifacts are removed
- no tracked source files are changed

**Step 4: Re-run the maintained fast checks**

Run:

```bash
uv run ruff check src/infinitas_skill server/ui server/app.py tests/integration tests/unit
uv run pytest tests/integration/test_cli_release_state.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_ui.py -q
```

Expected:
- both commands still pass after cleanup

**Step 5: Commit**

```bash
git add Makefile .gitignore README.md
git commit -m "chore: add supported local cleanup path"
```

### Task 3: Split `src/infinitas_skill/server/ops.py` By Responsibility

**Files:**
- Create: `src/infinitas_skill/server/inspection_summary.py`
- Create: `src/infinitas_skill/server/inspection_notifications.py`
- Create: `tests/unit/server_ops/test_inspection_summary.py`
- Create: `tests/unit/server_ops/test_inspection_notifications.py`
- Modify: `src/infinitas_skill/server/ops.py`
- Modify: `tests/integration/test_cli_server_ops.py`

**Step 1: Write focused failing unit tests**

Cover:
- job summary aggregation
- release audience summary aggregation
- alert threshold generation
- webhook delivery result handling
- fallback file writing behavior

Example shape:

```python
def test_maybe_add_alert_emits_alert_when_actual_exceeds_threshold():
    alerts = []
    maybe_add_alert(alerts, kind="failed_jobs", label="failed jobs", actual=3, maximum=1)
    assert alerts[0]["kind"] == "failed_jobs"
```

**Step 2: Run the new unit tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/server_ops/test_inspection_summary.py tests/unit/server_ops/test_inspection_notifications.py -q
```

Expected:
- tests fail because the extracted modules do not exist yet

**Step 3: Extract pure helpers first**

Move pure logic from `src/infinitas_skill/server/ops.py` into:
- `inspection_summary.py` for aggregation and alert generation
- `inspection_notifications.py` for webhook and fallback delivery

Keep CLI parser wiring in `ops.py`.

**Step 4: Re-run unit and integration coverage**

Run:

```bash
uv run pytest tests/unit/server_ops/test_inspection_summary.py tests/unit/server_ops/test_inspection_notifications.py tests/integration/test_cli_server_ops.py -q
```

Expected:
- new unit tests pass
- existing CLI integration tests still pass

**Step 5: Check the line budget outcome**

Run:

```bash
wc -l src/infinitas_skill/server/ops.py
uv run pytest tests/integration/test_maintainability_budgets.py -q
```

Expected:
- `ops.py` moves farther away from the 550-line ceiling
- maintainability budget test passes

**Step 6: Commit**

```bash
git add src/infinitas_skill/server/ops.py src/infinitas_skill/server/inspection_summary.py src/infinitas_skill/server/inspection_notifications.py tests/unit/server_ops/test_inspection_summary.py tests/unit/server_ops/test_inspection_notifications.py tests/integration/test_cli_server_ops.py
git commit -m "refactor: split server inspection orchestration"
```

### Task 4: Split `src/infinitas_skill/release/service.py` Into Smaller Decision Layers

**Files:**
- Create: `src/infinitas_skill/release/release_resolution.py`
- Create: `src/infinitas_skill/release/release_issues.py`
- Create: `tests/unit/release/test_release_resolution.py`
- Create: `tests/unit/release/test_release_issues.py`
- Modify: `src/infinitas_skill/release/service.py`
- Modify: `tests/integration/test_cli_release_state.py`

**Step 1: Write failing tests around extracted decision seams**

Cover:
- skill path resolution
- tag expectation generation
- issue generation for dirty worktree and upstream drift
- warning behavior for missing releaser identity and signer mismatches

Example shape:

```python
def test_expected_skill_tag_uses_meta_name_and_version(tmp_path):
    skill_dir = tmp_path / "skill"
    ...
    meta, tag = expected_skill_tag(skill_dir)
    assert tag == "skill/demo/v1.2.3"
```

**Step 2: Run the new tests and verify failure**

Run:

```bash
uv run pytest tests/unit/release/test_release_resolution.py tests/unit/release/test_release_issues.py -q
```

Expected:
- tests fail before extraction

**Step 3: Extract deterministic logic**

Move deterministic logic out of `service.py` first:
- resolution helpers into `release_resolution.py`
- issue and warning assembly helpers into `release_issues.py`

Keep `collect_release_state()` as the composition boundary.

**Step 4: Re-run release tests**

Run:

```bash
uv run pytest tests/unit/release/test_release_resolution.py tests/unit/release/test_release_issues.py tests/integration/test_cli_release_state.py -q
```

Expected:
- unit tests pass
- release CLI integration remains green

**Step 5: Re-check maintainability budget**

Run:

```bash
wc -l src/infinitas_skill/release/service.py
uv run pytest tests/integration/test_maintainability_budgets.py -q
```

Expected:
- `service.py` is comfortably below the 650-line ceiling
- budget test passes

**Step 6: Commit**

```bash
git add src/infinitas_skill/release/service.py src/infinitas_skill/release/release_resolution.py src/infinitas_skill/release/release_issues.py tests/unit/release/test_release_resolution.py tests/unit/release/test_release_issues.py tests/integration/test_cli_release_state.py
git commit -m "refactor: split release state decision layers"
```

### Task 5: Split `server/ui/lifecycle.py` Before It Crosses The Ceiling

**Files:**
- Create: `server/ui/lifecycle_state.py`
- Create: `server/ui/lifecycle_actions.py`
- Create: `tests/unit/server_ui/test_lifecycle_state.py`
- Modify: `server/ui/lifecycle.py`
- Modify: `tests/unit/server_ui/test_session_bootstrap.py`

**Step 1: Identify the stable UI seams**

Split the file by responsibility:
- state derivation
- action selection
- final rendering assembly

**Step 2: Write failing state-focused tests**

Cover:
- empty state derivation
- session/bootstrap status mapping
- action availability rules

Run:

```bash
uv run pytest tests/unit/server_ui/test_lifecycle_state.py -q
```

Expected:
- tests fail before the extraction lands

**Step 3: Extract pure state helpers**

Move pure state and action-selection logic out first. Keep HTML assembly close to the current template path until the state layer is stable.

**Step 4: Run UI-focused tests**

Run:

```bash
uv run pytest tests/unit/server_ui/test_lifecycle_state.py tests/unit/server_ui/test_session_bootstrap.py -q
```

Expected:
- state tests pass
- session bootstrap tests still pass

**Step 5: Re-run maintainability budget gate**

Run:

```bash
uv run pytest tests/integration/test_maintainability_budgets.py -q
wc -l server/ui/lifecycle.py
```

Expected:
- lifecycle budget remains green with more headroom

**Step 6: Commit**

```bash
git add server/ui/lifecycle.py server/ui/lifecycle_state.py server/ui/lifecycle_actions.py tests/unit/server_ui/test_lifecycle_state.py tests/unit/server_ui/test_session_bootstrap.py
git commit -m "refactor: separate lifecycle UI state from rendering"
```

### Task 6: Align CI With The Maintained Fast Path

**Files:**
- Modify: `.github/workflows/validate.yml`
- Modify: `Makefile`
- Modify: `README.md`

**Step 1: Define the desired CI contract**

The repository already has:
- `make test-fast`
- `make test-full`
- `make lint-maintained`

The CI workflow should make it obvious which of these is the default contributor path versus the heavier release path.

**Step 2: Add or reorder explicit fast-path steps**

Preferred order:
- install dependencies
- `make lint-maintained`
- `make test-fast`
- full `scripts/check-all.sh` only where release-grade coverage is intended

**Step 3: Verify workflow and docs stay aligned**

Run:

```bash
make doctor
uv run pytest tests/integration/test_maintainability_budgets.py -q
```

Expected:
- governance checks pass
- maintainability budget tests pass

**Step 4: Commit**

```bash
git add .github/workflows/validate.yml Makefile README.md
git commit -m "ci: align workflow with maintained fast path"
```

### Task 7: Close With A Fresh Optimization Score

**Files:**
- Modify: `docs/ops/2026-04-02-project-health-scorecard.md`
- Modify: `README.md`

**Step 1: Re-run the final verification set**

Run:

```bash
make lint-maintained
make test-fast
uv run pytest tests/integration/test_maintainability_budgets.py -q
```

Expected:
- all commands pass

**Step 2: Update the scorecard with after-state evidence**

Record:
- line counts before vs after
- tests added
- workflow changes
- new score by category

**Step 3: Commit**

```bash
git add docs/ops/2026-04-02-project-health-scorecard.md README.md
git commit -m "docs: publish optimization closeout score"
```

## Suggested Execution Order

1. Task 1 and Task 2 first because they are low-risk and improve local clarity immediately.
2. Task 3 and Task 4 next because `server/ops.py` and `release/service.py` are the most meaningful maintainability pressure points.
3. Task 5 after the backend orchestration splits, so UI cleanup happens with the new baseline already established.
4. Task 6 near the end, once the fast path truly reflects the cleaned-up project.
5. Task 7 last as the closeout record.

## Success Criteria

- `make lint-maintained` remains green.
- `make test-fast` remains green.
- `tests/integration/test_maintainability_budgets.py` remains green.
- `src/infinitas_skill/server/ops.py`, `src/infinitas_skill/release/service.py`, and `server/ui/lifecycle.py` all have visible margin below their current budgets.
- The freshest project scorecard matches the real repository state on the day it is written.
- Contributors have a documented, supported way to clean local generated artifacts.

Plan complete and saved to `docs/plans/2026-04-02-project-optimization-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
