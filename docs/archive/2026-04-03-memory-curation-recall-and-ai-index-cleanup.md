# Memory Curation, Recall Evaluation, And AI Index Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve memory quality in three ordered steps: add safe memory curation primitives and operator visibility, expand recall-quality evaluation coverage, then continue structural cleanup on the next discovery-heavy maintained module.

**Architecture:** Keep Memo0 advisory-only and avoid provider-side destructive mutation. Add retrieval-time curation plus a local-audit-backed curation planning surface, extend the fixture matrix to cover recall noise and stale-memory cases, then split `ai_index.py` into smaller builder/validation seams while keeping public behavior stable.

**Tech Stack:** Python 3.11, `src/infinitas_skill/memory`, `src/infinitas_skill/discovery`, `src/infinitas_skill/server`, argparse CLI, pytest, maintained regression scripts, Markdown docs

---

### Task 1: Add memory curation primitives and operator curation planning

**Files:**
- Create: `src/infinitas_skill/memory/curation.py`
- Modify: `src/infinitas_skill/memory/__init__.py`
- Modify: `src/infinitas_skill/discovery/recommendation_memory.py`
- Modify: `src/infinitas_skill/discovery/inspect_memory.py`
- Create: `src/infinitas_skill/server/memory_curation.py`
- Modify: `src/infinitas_skill/server/ops.py`
- Create: `tests/unit/memory/test_curation.py`
- Modify: `tests/unit/discovery/test_recommendation_memory.py`
- Modify: `tests/unit/discovery/test_inspect_memory.py`
- Create: `tests/unit/server_ops/test_memory_curation.py`
- Modify: `tests/integration/test_cli_server_ops.py`
- Modify: `docs/ai/memory.md`
- Modify: `docs/ops/server-deployment.md`

**Step 1: Write failing tests**

Add focused tests for:

- curation dedupes near-identical memory records and preserves the strongest survivor
- stale low-quality records are suppressed before recommendation/inspect rendering
- `infinitas server memory-curation --database-url ... --json` returns duplicate and stale writeback candidate summaries from local audit data

**Step 2: Run the focused tests to verify RED**

Run:

```bash
uv run pytest tests/unit/memory/test_curation.py tests/unit/discovery/test_recommendation_memory.py tests/unit/discovery/test_inspect_memory.py tests/unit/server_ops/test_memory_curation.py tests/integration/test_cli_server_ops.py -q
```

**Step 3: Implement minimal curation logic**

Add a small curation layer that:

- computes a normalized fingerprint for retrieved memories
- suppresses duplicate and stale low-signal records while keeping the strongest representative
- returns a compact curation summary with kept/suppressed counts

Then add a read-only server helper and CLI command that inspect recent `memory_writeback` audit rows and report:

- top duplicate writeback candidates
- stale or low-signal candidate counts
- lifecycle events most likely to benefit from future archive or compaction work

Hard rules:

- no provider-side delete/write mutation
- no Memo0/provider truth dependency
- no secrets or raw payload leakage

**Step 4: Re-run focused verification**

Run:

```bash
uv run pytest tests/unit/memory/test_curation.py tests/unit/discovery/test_recommendation_memory.py tests/unit/discovery/test_inspect_memory.py tests/unit/server_ops/test_memory_curation.py tests/integration/test_cli_server_ops.py -q
```

**Step 5: Commit**

```bash
git add src/infinitas_skill/memory/curation.py src/infinitas_skill/memory/__init__.py src/infinitas_skill/discovery/recommendation_memory.py src/infinitas_skill/discovery/inspect_memory.py src/infinitas_skill/server/memory_curation.py src/infinitas_skill/server/ops.py tests/unit/memory/test_curation.py tests/unit/discovery/test_recommendation_memory.py tests/unit/discovery/test_inspect_memory.py tests/unit/server_ops/test_memory_curation.py tests/integration/test_cli_server_ops.py docs/ai/memory.md docs/ops/server-deployment.md
git commit -m "feat: add memory curation planning"
```

### Task 2: Expand recall-quality evaluation coverage

**Files:**
- Modify: `tests/fixtures/memory_eval/recommendation_cases.json`
- Modify: `tests/fixtures/memory_eval/inspect_cases.json`
- Modify: `tests/integration/test_memory_evaluation_matrix.py`
- Modify: `tests/unit/memory/test_context.py`
- Modify: `docs/ai/memory.md`
- Modify: `docs/reference/testing.md`
- Modify: `README.md`

**Step 1: Write failing evaluation cases**

Add cases that prove:

- duplicate noisy memories do not swamp a better memory signal
- stale low-confidence memories do not outrank fresher stronger memories
- negative or irrelevant memories do not create false-positive lift
- inspect recall surfaces keep the strongest representative after curation

**Step 2: Run the focused evaluation tests to verify RED**

Run:

```bash
uv run pytest tests/unit/memory/test_context.py tests/integration/test_memory_evaluation_matrix.py -q
```

**Step 3: Implement the minimal harness changes**

Extend the matrix loader/assertions so fixtures can declare:

- expected matched counts before/after curation
- expected winner stability under noisy memory
- expected top inspect hint after curation

Keep all expectations advisory-only.

**Step 4: Re-run evaluation verification**

Run:

```bash
uv run pytest tests/unit/memory/test_context.py tests/integration/test_memory_evaluation_matrix.py tests/unit/discovery/test_memory_recommendation.py tests/unit/discovery/test_memory_inspect.py -q
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
```

**Step 5: Commit**

```bash
git add tests/fixtures/memory_eval/recommendation_cases.json tests/fixtures/memory_eval/inspect_cases.json tests/integration/test_memory_evaluation_matrix.py tests/unit/memory/test_context.py docs/ai/memory.md docs/reference/testing.md README.md
git commit -m "test: expand memory recall evaluation"
```

### Task 3: Split AI index orchestration by responsibility

**Files:**
- Create: `src/infinitas_skill/discovery/ai_index_builder.py`
- Create: `src/infinitas_skill/discovery/ai_index_validation.py`
- Modify: `src/infinitas_skill/discovery/ai_index.py`
- Create: `tests/unit/discovery/test_ai_index_builder.py`
- Create: `tests/unit/discovery/test_ai_index_validation.py`
- Modify: `tests/integration/test_dev_workflow.py`
- Modify: `docs/ops/2026-04-02-project-health-scorecard.md`
- Modify: `docs/plans/2026-04-03-memory-curation-recall-and-ai-index-cleanup.md`

**Step 1: Write failing seam tests**

Add tests for:

- builder chooses the newest version entry and preserves trust/install metadata
- validation reports the key schema contract failures without depending on builder flow

**Step 2: Run the focused tests to verify RED**

Run:

```bash
uv run pytest tests/unit/discovery/test_ai_index_builder.py tests/unit/discovery/test_ai_index_validation.py -q
```

**Step 3: Extract builder and validation helpers**

Move:

- payload assembly and per-skill shaping into `ai_index_builder.py`
- schema/error checking into `ai_index_validation.py`

Keep `src/infinitas_skill/discovery/ai_index.py` as the maintained composition/export boundary.

**Step 4: Re-run focused and public verification**

Run:

```bash
uv run pytest tests/unit/discovery/test_ai_index_builder.py tests/unit/discovery/test_ai_index_validation.py tests/integration/test_dev_workflow.py -q
make doctor
```

**Step 5: Measure structural outcome**

Run:

```bash
wc -l src/infinitas_skill/discovery/ai_index.py
```

**Step 6: Run final closeout matrix**

Run:

```bash
uv run pytest tests/unit/memory/test_curation.py tests/unit/memory/test_context.py tests/unit/memory/test_experience.py tests/unit/memory/test_provider.py tests/unit/discovery/test_recommendation_memory.py tests/unit/discovery/test_inspect_memory.py tests/unit/discovery/test_ai_index_builder.py tests/unit/discovery/test_ai_index_validation.py tests/unit/server_memory/test_writeback.py tests/unit/server_ops/test_memory_health.py tests/unit/server_ops/test_memory_curation.py tests/integration/test_memory_evaluation_matrix.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_memory_flow.py tests/integration/test_private_registry_ui.py tests/integration/test_dev_workflow.py -q
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
make doctor
make ci-fast
git status --short
```

**Step 7: Commit**

```bash
git add src/infinitas_skill/discovery/ai_index.py src/infinitas_skill/discovery/ai_index_builder.py src/infinitas_skill/discovery/ai_index_validation.py tests/unit/discovery/test_ai_index_builder.py tests/unit/discovery/test_ai_index_validation.py tests/integration/test_dev_workflow.py docs/ops/2026-04-02-project-health-scorecard.md docs/plans/2026-04-03-memory-curation-recall-and-ai-index-cleanup.md
git commit -m "refactor: split ai index orchestration"
```

## Execution Outcomes

Completed on 2026-04-03 in the `codex/memo0-memory` worktree.

Delivered commits before the final `ai_index` closeout:

- `dc093b3` `feat: add memory curation planning`
- `ff37b50` `test: expand memory recall evaluation`

Structural outcome:

- `src/infinitas_skill/discovery/ai_index.py`: `534 -> 12` lines
- `src/infinitas_skill/discovery/ai_index_builder.py`: `269` lines
- `src/infinitas_skill/discovery/ai_index_validation.py`: `167` lines

Verification outcome before the final commit:

- Task 1 focused curation slice: `14 passed in 1.69s`
- Task 2 recall evaluation slice: `13 passed in 0.28s`
- Task 3 focused `ai_index` slice: `15 passed in 0.28s`
- expanded closeout pytest matrix: `58 passed in 2.39s`
- `python3 scripts/test-ai-index.py`: PASS
- `python3 scripts/test-recommend-skill.py`: PASS
- `python3 scripts/test-search-inspect.py`: PASS
- `make doctor`: PASS
- `make ci-fast`: PASS (`14 passed in 23.43s`)

Follow-on optimization direction:

- turn local curation planning into optional provider-side prune/archive execution with explicit safeguards
- expand recall-quality evaluation from discovery ranking into longer-horizon usefulness and decay metrics
- keep attacking large maintained modules in install and policy surfaces with the same seam-first extraction style
