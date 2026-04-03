# Executable Memory Curation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current read-only memory curation planner into a guarded execution workflow that can archive candidates locally and prune provider-side memories only when explicitly requested.

**Architecture:** Keep the source-of-truth boundary unchanged: local audit remains authoritative, and provider mutation stays optional and explicit. Extend the memory provider contract with an optional delete operation, teach the Memo0 adapter to use it when available, and add curation execution helpers that choose duplicate or expired candidates from local audit history. The CLI will default to planning mode and require `--apply` before any prune/archive action is executed.

**Tech Stack:** Python 3.11, `src/infinitas_skill/memory`, `src/infinitas_skill/server`, `server/modules/audit`, argparse CLI, pytest, Markdown docs

---

## Status

Completed on 2026-04-03.

## Outcome Summary

- Added guarded provider delete support to the memory abstraction and Memo0 adapter.
- Upgraded `infinitas server memory-curation` to support `plan`, `archive`, and `prune`.
- Kept default behavior read-only, with provider mutation requiring explicit `--action prune --apply`.
- Kept archive execution local-audit-only through `memory_curation` audit events.
- Updated operator and architecture docs to reflect the new execution contract.

### Task 1: Add guarded execution capabilities to the memory provider layer

**Files:**
- Modify: `src/infinitas_skill/memory/contracts.py`
- Modify: `src/infinitas_skill/memory/provider.py`
- Modify: `src/infinitas_skill/memory/memo0_provider.py`
- Modify: `tests/unit/memory/test_provider.py`

**Step 1: Write failing tests**

Add tests for:

- noop provider reports delete as skipped
- Memo0 provider deletes a memory by `memory_id` when the client supports delete
- unsupported delete capability stays sanitized and non-fatal

**Step 2: Run the focused test to verify RED**

Run:

```bash
uv run pytest tests/unit/memory/test_provider.py -q
```

**Step 3: Implement minimal provider delete support**

Add:

- `MemoryDeleteResult`
- optional `delete(memory_id=...)` provider method
- noop delete behavior
- Memo0 delete adapter using `delete(...)` or `delete_memory(...)` when present

Keep provider errors sanitized and bounded.

**Step 4: Re-run the focused test**

Run:

```bash
uv run pytest tests/unit/memory/test_provider.py -q
```

### Task 2: Add executable archive/prune flow to server memory curation

**Files:**
- Modify: `src/infinitas_skill/server/memory_curation.py`
- Modify: `src/infinitas_skill/server/ops.py`
- Create: `tests/unit/server_ops/test_memory_curation_execution.py`
- Modify: `tests/unit/server_ops/test_memory_curation.py`
- Modify: `tests/integration/test_cli_server_ops.py`
- Modify: `docs/ai/memory.md`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`

**Step 1: Write failing tests**

Add tests for:

- prune dry-run returns actionable duplicate/expired candidates without mutating provider state
- prune apply deletes only guarded candidates with `memory_id`
- archive apply appends a local audit event and does not mutate provider state
- CLI supports `--action`, `--apply`, and `--max-actions` for `infinitas server memory-curation`

**Step 2: Run focused tests to verify RED**

Run:

```bash
uv run pytest tests/unit/server_ops/test_memory_curation.py tests/unit/server_ops/test_memory_curation_execution.py tests/integration/test_cli_server_ops.py -q
```

**Step 3: Implement execution helpers**

Add a small execution layer that:

- builds actionable candidates from recent `memory_writeback` audit rows
- supports `plan`, `archive`, and `prune`
- defaults to dry-run unless `--apply` is present
- keeps the newest record in duplicate groups
- only prunes `stored` events with non-empty `memory_id`
- appends local `memory_curation` audit events for dry-run, archived, pruned, skipped, or failed outcomes

**Step 4: Re-run focused verification**

Run:

```bash
uv run pytest tests/unit/server_ops/test_memory_curation.py tests/unit/server_ops/test_memory_curation_execution.py tests/integration/test_cli_server_ops.py -q
```

### Task 3: Run closeout verification and record outcomes

**Files:**
- Modify: `docs/ops/2026-04-02-project-health-scorecard.md`
- Modify: `docs/plans/2026-04-03-executable-memory-curation.md`

**Step 1: Run verification**

Run:

```bash
uv run pytest tests/unit/memory/test_provider.py tests/unit/server_ops/test_memory_curation.py tests/unit/server_ops/test_memory_curation_execution.py tests/integration/test_cli_server_ops.py tests/integration/test_memory_evaluation_matrix.py tests/integration/test_private_registry_memory_flow.py -q
python3 scripts/test-ai-index.py
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
make doctor
make ci-fast
git status --short
```

**Step 2: Record outcomes and commit**

```bash
git add src/infinitas_skill/memory/contracts.py src/infinitas_skill/memory/provider.py src/infinitas_skill/memory/memo0_provider.py src/infinitas_skill/server/memory_curation.py src/infinitas_skill/server/ops.py tests/unit/memory/test_provider.py tests/unit/server_ops/test_memory_curation.py tests/unit/server_ops/test_memory_curation_execution.py tests/integration/test_cli_server_ops.py docs/ai/memory.md docs/ops/server-deployment.md README.md docs/ops/2026-04-02-project-health-scorecard.md docs/plans/2026-04-03-executable-memory-curation.md
git commit -m "feat: add executable memory curation"
```

## Verification Results

- `uv run pytest tests/unit/memory/test_provider.py -q`
  - PASS (`8 passed in 0.34s`)
- `uv run pytest tests/unit/server_ops/test_memory_curation.py tests/unit/server_ops/test_memory_curation_execution.py tests/integration/test_cli_server_ops.py -q`
  - PASS (`10 passed in 1.88s`)
- `uv run pytest tests/unit/memory/test_provider.py tests/unit/server_ops/test_memory_curation.py tests/unit/server_ops/test_memory_curation_execution.py tests/integration/test_cli_server_ops.py tests/integration/test_memory_evaluation_matrix.py tests/integration/test_private_registry_memory_flow.py -q`
  - PASS (`21 passed in 2.28s`)
- `python3 scripts/test-ai-index.py`
  - PASS
- `python3 scripts/test-recommend-skill.py`
  - PASS
- `python3 scripts/test-search-inspect.py`
  - PASS
- `make doctor`
  - PASS
- `make ci-fast`
  - PASS (`15 passed in 23.51s`)
