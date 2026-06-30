# Discovery Memory Structural Cleanup And Evaluation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the newly added Memo0-backed discovery memory layer into a smaller, more testable, and more observable subsystem without changing the private-first source-of-truth boundary.

**Architecture:** Keep recommendation and inspect behavior stable at the public API level, but split memory retrieval, ranking, and explanation logic out of the current large orchestration modules. Add a fixture-backed evaluation matrix so recommendation and inspect quality become regression-tested behavior, then expose a small operator-facing memory health surface backed only by local audit data. All memory effects must remain advisory-only and must never bypass compatibility, review, access, or immutable release rules.

**Tech Stack:** Python 3.11, `src/infinitas_skill/discovery`, `src/infinitas_skill/memory`, `src/infinitas_skill/server`, FastAPI/argparse maintained CLI surface, pytest, existing script regressions, Markdown docs

---

## Optimization Priorities

1. Reduce complexity in the largest new memory-aware orchestration file: `src/infinitas_skill/discovery/recommendation.py`.
2. Give inspect the same decomposition so recommendation and inspect use parallel, understandable memory seams.
3. Convert memory quality from “it seems better” into repeatable evaluation fixtures and regression checks.
4. Give operators a supported way to inspect memory writeback health without needing Memo0 access or raw SQL spelunking.

### Task 1: Split recommendation memory orchestration by responsibility

**Files:**
- Create: `src/infinitas_skill/discovery/recommendation_memory.py`
- Create: `src/infinitas_skill/discovery/recommendation_ranking.py`
- Create: `src/infinitas_skill/discovery/recommendation_explanation.py`
- Create: `tests/unit/discovery/test_recommendation_memory.py`
- Create: `tests/unit/discovery/test_recommendation_explanation.py`
- Modify: `src/infinitas_skill/discovery/recommendation.py`
- Modify: `tests/unit/discovery/test_memory_recommendation.py`
- Modify: `scripts/test-recommend-skill.py`

**Step 1: Write focused failing tests for the extracted seams**

Create `tests/unit/discovery/test_recommendation_memory.py` with coverage for:

```python
def test_load_recommendation_memory_context_reports_error_without_changing_results():
    ...


def test_calculate_memory_signals_uses_effective_memory_quality_for_boost_order():
    ...
```

Create `tests/unit/discovery/test_recommendation_explanation.py` with coverage for:

```python
def test_build_recommendation_explanation_includes_memory_summary_and_winner_confidence():
    ...
```

Keep `tests/unit/discovery/test_memory_recommendation.py` as the public-behavior regression suite.

**Step 2: Run the new tests to verify RED**

Run:

```bash
uv run pytest tests/unit/discovery/test_recommendation_memory.py tests/unit/discovery/test_recommendation_explanation.py -q
```

Expected: FAIL because the extracted modules and public helpers do not exist yet.

**Step 3: Extract memory retrieval, ranking, and explanation helpers**

Move logic out of `src/infinitas_skill/discovery/recommendation.py` into:

- `recommendation_memory.py`
  - provider reads
  - payload normalization
  - memory summary state construction
- `recommendation_ranking.py`
  - memory-signal matching
  - bounded boost calculation
  - candidate score enrichment helpers
- `recommendation_explanation.py`
  - comparison summary
  - winner confidence view
  - top-level explanation assembly

Keep `recommend_skills(...)` in `recommendation.py` as the maintained composition boundary.

**Step 4: Re-run focused and public regressions**

Run:

```bash
uv run pytest tests/unit/discovery/test_recommendation_memory.py tests/unit/discovery/test_recommendation_explanation.py tests/unit/discovery/test_memory_recommendation.py -q
python3 scripts/test-recommend-skill.py
```

Expected: PASS.

**Step 5: Measure the structural outcome**

Run:

```bash
wc -l src/infinitas_skill/discovery/recommendation.py
```

Expected: `recommendation.py` is materially smaller than the current ~730-line file and mostly acts as composition glue.

**Step 6: Commit**

```bash
git add src/infinitas_skill/discovery/recommendation.py src/infinitas_skill/discovery/recommendation_memory.py src/infinitas_skill/discovery/recommendation_ranking.py src/infinitas_skill/discovery/recommendation_explanation.py tests/unit/discovery/test_recommendation_memory.py tests/unit/discovery/test_recommendation_explanation.py tests/unit/discovery/test_memory_recommendation.py scripts/test-recommend-skill.py
git commit -m "refactor: split recommendation memory orchestration"
```

### Task 2: Split inspect memory orchestration by responsibility

**Files:**
- Create: `src/infinitas_skill/discovery/inspect_memory.py`
- Create: `src/infinitas_skill/discovery/inspect_view.py`
- Create: `tests/unit/discovery/test_inspect_memory.py`
- Create: `tests/unit/discovery/test_inspect_view.py`
- Modify: `src/infinitas_skill/discovery/inspect.py`
- Modify: `tests/unit/discovery/test_memory_inspect.py`
- Modify: `scripts/test-search-inspect.py`

**Step 1: Write focused failing tests for inspect seams**

Create `tests/unit/discovery/test_inspect_memory.py` with cases like:

```python
def test_load_inspect_memory_hints_returns_advisory_error_state():
    ...


def test_load_inspect_memory_hints_orders_items_by_effective_quality():
    ...
```

Create `tests/unit/discovery/test_inspect_view.py` with cases like:

```python
def test_build_inspect_payload_keeps_trust_fields_authoritative_when_memory_is_present():
    ...
```

**Step 2: Run the new tests to verify RED**

Run:

```bash
uv run pytest tests/unit/discovery/test_inspect_memory.py tests/unit/discovery/test_inspect_view.py -q
```

Expected: FAIL because the extracted inspect modules do not exist yet.

**Step 3: Extract inspect memory and payload assembly**

Move logic out of `src/infinitas_skill/discovery/inspect.py` into:

- `inspect_memory.py`
  - provider reads
  - advisory status handling
  - memory hint item shaping
- `inspect_view.py`
  - payload assembly helpers
  - trust/memory coexistence rendering

Keep `inspect_skill(...)` in `inspect.py` as the maintained public composition entrypoint.

**Step 4: Re-run focused and public regressions**

Run:

```bash
uv run pytest tests/unit/discovery/test_inspect_memory.py tests/unit/discovery/test_inspect_view.py tests/unit/discovery/test_memory_inspect.py -q
python3 scripts/test-search-inspect.py
```

Expected: PASS.

**Step 5: Measure the structural outcome**

Run:

```bash
wc -l src/infinitas_skill/discovery/inspect.py
```

Expected: `inspect.py` becomes mostly composition logic and shrinks from the current ~412 lines.

**Step 6: Commit**

```bash
git add src/infinitas_skill/discovery/inspect.py src/infinitas_skill/discovery/inspect_memory.py src/infinitas_skill/discovery/inspect_view.py tests/unit/discovery/test_inspect_memory.py tests/unit/discovery/test_inspect_view.py tests/unit/discovery/test_memory_inspect.py scripts/test-search-inspect.py
git commit -m "refactor: split inspect memory orchestration"
```

### Task 3: Add a fixture-backed memory evaluation matrix

**Files:**
- Create: `tests/fixtures/memory_eval/recommendation_cases.json`
- Create: `tests/fixtures/memory_eval/inspect_cases.json`
- Create: `tests/integration/test_memory_evaluation_matrix.py`
- Modify: `tests/unit/discovery/test_memory_recommendation.py`
- Modify: `tests/unit/discovery/test_memory_inspect.py`
- Modify: `docs/ai/memory.md`
- Modify: `docs/reference/testing.md`

**Step 1: Write the failing evaluation matrix**

Create `tests/integration/test_memory_evaluation_matrix.py` that loads fixture cases and asserts:

- baseline winner without memory
- winner after memory for close ties
- incompatible candidate never lifted above compatible candidate
- negative experience memory does not create positive boost
- inspect hint ordering prefers stronger experience memory
- inspect trust state remains unchanged when memory is present

Fixture schema should be explicit and reviewable, for example:

```json
{
  "name": "beta_preferred_for_neptune_when_memory_enabled",
  "task": "Need codex helper for workflows",
  "target_agent": "codex",
  "expected_winner": "team/beta-preferred",
  "expected_memory_used": true
}
```

**Step 2: Run the evaluation test to verify RED**

Run:

```bash
uv run pytest tests/integration/test_memory_evaluation_matrix.py -q
```

Expected: FAIL because the fixture-backed evaluation harness does not exist yet.

**Step 3: Implement the fixture loader and evaluation helpers**

Add the minimal test-only support needed so the evaluation matrix can:

- load fixture-defined discovery catalogs
- load fixture-defined memory records
- invoke existing recommendation and inspect public APIs
- compare outcomes against expected winner/order/state fields

Do not add a new top-level script under `scripts/`; keep this inside pytest and existing maintained surfaces.

**Step 4: Re-run evaluation plus public script regressions**

Run:

```bash
uv run pytest tests/integration/test_memory_evaluation_matrix.py tests/unit/discovery/test_memory_recommendation.py tests/unit/discovery/test_memory_inspect.py -q
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
```

Expected: PASS.

**Step 5: Document the evaluation path**

Update:

- `docs/ai/memory.md`
- `docs/reference/testing.md`

Document:

- where the evaluation fixtures live
- which command replays the memory evaluation matrix
- which behaviors are expected to stay advisory-only forever

**Step 6: Commit**

```bash
git add tests/fixtures/memory_eval/recommendation_cases.json tests/fixtures/memory_eval/inspect_cases.json tests/integration/test_memory_evaluation_matrix.py tests/unit/discovery/test_memory_recommendation.py tests/unit/discovery/test_memory_inspect.py docs/ai/memory.md docs/reference/testing.md
git commit -m "test: add memory evaluation matrix"
```

### Task 4: Add operator-facing memory writeback health diagnostics

**Files:**
- Create: `src/infinitas_skill/server/memory_health.py`
- Create: `tests/unit/server_ops/test_memory_health.py`
- Modify: `src/infinitas_skill/server/ops.py`
- Modify: `tests/integration/test_cli_server_ops.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `docs/ai/memory.md`

**Step 1: Write failing unit and CLI integration tests**

Create `tests/unit/server_ops/test_memory_health.py` with cases like:

```python
def test_summarize_memory_writeback_groups_recent_statuses_and_failures():
    ...
```

Extend `tests/integration/test_cli_server_ops.py` with a CLI case like:

```python
def test_server_memory_health_command_returns_status_counts(tmp_path):
    result = run_cli(
        "server",
        "memory-health",
        "--database-url",
        database_url,
        "--json",
    )
    assert result["writeback_status_counts"]["failed"] == 1
```

**Step 2: Run the tests to verify RED**

Run:

```bash
uv run pytest tests/unit/server_ops/test_memory_health.py tests/integration/test_cli_server_ops.py -q
```

Expected: FAIL because the memory health helper and CLI surface do not exist yet.

**Step 3: Implement local-audit-backed diagnostics**

Add `src/infinitas_skill/server/memory_health.py` with helpers that read only local `audit_events` and summarize:

- counts by `stored/skipped/disabled/failed/deduped`
- latest failures with `lifecycle_event`
- top failing lifecycle events
- backend names seen in recent writeback attempts

Wire a maintained CLI surface through `src/infinitas_skill/server/ops.py`:

```bash
uv run infinitas server memory-health --database-url sqlite:///... --json
```

Hard rules:

- do not require Memo0 access for this command
- do not expose secrets or raw provider errors
- keep the command read-only and audit-backed

**Step 4: Re-run unit and integration coverage**

Run:

```bash
uv run pytest tests/unit/server_ops/test_memory_health.py tests/integration/test_cli_server_ops.py -q
```

Expected: PASS.

**Step 5: Document the operator workflow**

Update:

- `docs/ops/server-deployment.md`
- `docs/ai/memory.md`

Document:

- how to run the command
- how to interpret failed vs disabled writeback counts
- why the command is local-audit truth rather than provider truth

**Step 6: Commit**

```bash
git add src/infinitas_skill/server/memory_health.py src/infinitas_skill/server/ops.py tests/unit/server_ops/test_memory_health.py tests/integration/test_cli_server_ops.py docs/ops/server-deployment.md docs/ai/memory.md
git commit -m "feat: add memory health diagnostics"
```

### Task 5: Run the full verification matrix and close the loop

**Files:**
- Modify: `README.md`
- Modify: `docs/ops/2026-04-02-project-health-scorecard.md`
- Modify: `docs/plans/2026-04-03-discovery-memory-structural-cleanup-and-evaluation.md`

**Step 1: Refresh entry docs with the new preferred paths**

Update `README.md` and the scorecard with:

- the new evaluation command
- the new memory health command
- the updated structural cleanup outcome for discovery modules

**Step 2: Run the full verification matrix**

Run:

```bash
uv run pytest tests/unit/discovery/test_recommendation_memory.py tests/unit/discovery/test_recommendation_explanation.py tests/unit/discovery/test_inspect_memory.py tests/unit/discovery/test_inspect_view.py tests/unit/discovery/test_memory_recommendation.py tests/unit/discovery/test_memory_inspect.py tests/unit/memory/test_provider.py tests/unit/memory/test_context.py tests/unit/memory/test_experience.py tests/unit/server_memory/test_writeback.py tests/unit/server_ops/test_memory_health.py tests/integration/test_memory_evaluation_matrix.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_memory_flow.py tests/integration/test_private_registry_ui.py -q
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
make doctor
make ci-fast
```

Expected:

- new extracted-seam tests pass
- memory evaluation matrix passes
- operator diagnostics command is covered by CLI integration tests
- public recommendation/inspect regressions still pass
- maintained docs and fast baseline remain green

**Step 3: Capture the structural evidence**

Run:

```bash
wc -l src/infinitas_skill/discovery/recommendation.py src/infinitas_skill/discovery/inspect.py
git status --short
```

Expected:

- both discovery composition files are materially smaller than today
- worktree is clean before the final commit

**Step 4: Commit**

```bash
git add README.md docs/ops/2026-04-02-project-health-scorecard.md docs/plans/2026-04-03-discovery-memory-structural-cleanup-and-evaluation.md
git commit -m "docs: record discovery memory cleanup outcomes"
```

## Release Notes For This Slice

When this plan is complete, the repository should have:

- smaller, composable recommendation and inspect modules
- a fixture-backed memory evaluation matrix
- an operator-facing memory health diagnostic command
- docs that make the evaluation and observability paths discoverable

The repository should not yet have:

- memory-driven policy decisions
- provider-side truth replacing local audit truth
- automatic memory pruning or background compaction jobs

## Execution Outcomes

Completed on 2026-04-03 in the `codex/memo0-memory` worktree.

Delivered commits:

- `9c1e2d7` `refactor: split recommendation memory orchestration`
- `6dacbcd` `refactor: split inspect memory orchestration`
- `1906698` `test: add memory evaluation matrix`
- `e122c21` `feat: add memory health diagnostics`

Structural outcome:

- `src/infinitas_skill/discovery/recommendation.py`: `~730 -> 113` lines
- `src/infinitas_skill/discovery/inspect.py`: `~412 -> 182` lines
- `src/infinitas_skill/server/ops.py`: `542 -> 461` lines while gaining the maintained `memory-health` surface

Verification outcome:

- targeted Task 4 coverage: `5 passed in 1.48s`
- closeout pytest matrix: `44 passed in 2.21s`
- `python3 scripts/test-recommend-skill.py`: PASS
- `python3 scripts/test-search-inspect.py`: PASS
- `make doctor`: PASS
- `make ci-fast`: PASS (`13 passed in 22.14s`)

Follow-on optimization direction:

- add memory pruning and summarization controls so long-lived writeback data stays useful
- expand recall-quality evaluation beyond close-tie discovery cases
- keep reducing larger maintained orchestration surfaces outside the newly split discovery modules
