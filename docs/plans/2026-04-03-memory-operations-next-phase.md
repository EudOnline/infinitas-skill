# Memory Operations Next Phase Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the new Memo0-backed memory foundation with queue-driven curation, longer-horizon evaluation, and operator-grade observability without weakening the local-audit source-of-truth boundary.

**Architecture:** Reuse the existing `jobs` + `worker` runtime for scheduled or deferred memory curation instead of inventing a second execution path. Keep evaluation and observability local-first as well: compute recall/usefulness and health summaries from local fixtures, audit history, and deterministic helper code, while treating Memo0 as an optional advisory backend rather than an authority.

**Tech Stack:** Python 3.11, `src/infinitas_skill/server`, `server/jobs.py`, `server/worker.py`, `server/modules/audit`, pytest, argparse CLI, Markdown docs

---

## Status

Completed on 2026-04-03.

## Outcome Summary

- Added queue-driven memory curation execution through the existing hosted jobs worker.
- Added optional systemd scheduling hooks that enqueue bounded curation jobs on a calendar.
- Added deterministic usefulness summaries to the fixture-backed memory evaluation matrix.
- Added a maintained `memory-observability` command that summarizes writeback, curation, and queued memory jobs from local state.

## Verification Results

- `uv run pytest tests/unit/server_ops/test_memory_curation_queue.py tests/unit/server_ops/test_systemd_memory_curation.py tests/unit/memory/test_evaluation.py tests/unit/server_ops/test_memory_observability.py tests/unit/memory/test_provider.py tests/unit/server_ops/test_memory_curation.py tests/unit/server_ops/test_memory_curation_execution.py tests/integration/test_cli_server_ops.py tests/integration/test_memory_evaluation_matrix.py tests/integration/test_private_registry_memory_flow.py -q`
  - PASS (`29 passed in 2.76s`)
- `make doctor`
  - PASS
- `make ci-fast`
  - PASS (`17 passed in 95.14s`)

### Task 1: Add queue-driven and schedulable memory curation

**Files:**
- Modify: `server/jobs.py`
- Modify: `server/worker.py`
- Modify: `src/infinitas_skill/server/ops.py`
- Modify: `src/infinitas_skill/server/systemd.py`
- Modify: `tests/integration/test_cli_server_ops.py`
- Create: `tests/unit/server_ops/test_memory_curation_queue.py`
- Create: `tests/unit/server_ops/test_systemd_memory_curation.py`

**Step 1: Write the failing tests**

Add tests for:

- queueing a `memory_curation` job through a maintained CLI path
- worker execution of a queued `memory_curation` job with action/apply payload
- rendered systemd bundle including a curation enqueue service and timer when configured

**Step 2: Run focused tests to verify RED**

Run:

```bash
uv run pytest tests/unit/server_ops/test_memory_curation_queue.py tests/unit/server_ops/test_systemd_memory_curation.py tests/integration/test_cli_server_ops.py -q
```

Expected: FAIL because queueing and systemd scheduling do not exist yet.

**Step 3: Implement minimal queue + schedule support**

Add:

- a supported `memory_curation` job kind in the worker
- a queueing helper or CLI entrypoint that stores action/apply/max-actions/actor-ref in `jobs.payload_json`
- optional system-owned enqueue support for scheduled runs
- rendered systemd oneshot service + timer for scheduled curation enqueue

Keep direct `infinitas server memory-curation ...` execution intact.

**Step 4: Re-run focused tests to verify GREEN**

Run:

```bash
uv run pytest tests/unit/server_ops/test_memory_curation_queue.py tests/unit/server_ops/test_systemd_memory_curation.py tests/integration/test_cli_server_ops.py -q
```

### Task 2: Add longer-horizon memory usefulness evaluation

**Files:**
- Create: `src/infinitas_skill/memory/evaluation.py`
- Modify: `src/infinitas_skill/memory/__init__.py`
- Modify: `tests/integration/test_memory_evaluation_matrix.py`
- Create: `tests/unit/memory/test_evaluation.py`
- Create: `tests/fixtures/memory_eval/usefulness_cases.json`
- Modify: `docs/ai/memory.md`

**Step 1: Write the failing tests**

Add tests for:

- computing usefulness summary metrics from fixture cases
- distinguishing recall success from actual decision usefulness
- surfacing stable aggregate metrics such as retrieval hit rate, top-hit rate, and decision influence rate

**Step 2: Run focused tests to verify RED**

Run:

```bash
uv run pytest tests/unit/memory/test_evaluation.py tests/integration/test_memory_evaluation_matrix.py -q
```

Expected: FAIL because the usefulness evaluator and new fixture coverage do not exist yet.

**Step 3: Implement a minimal deterministic evaluator**

Add:

- a small evaluator that scores fixture outcomes across recommendation and inspect flows
- aggregate usefulness metrics computed from expected fixture assertions
- helper output that can be reused by docs or future ops commands

Keep the matrix deterministic and fixture-backed.

**Step 4: Re-run focused tests to verify GREEN**

Run:

```bash
uv run pytest tests/unit/memory/test_evaluation.py tests/integration/test_memory_evaluation_matrix.py -q
```

### Task 3: Add operator memory observability summaries

**Files:**
- Create: `src/infinitas_skill/server/memory_observability.py`
- Modify: `src/infinitas_skill/server/ops.py`
- Modify: `tests/integration/test_cli_server_ops.py`
- Create: `tests/unit/server_ops/test_memory_observability.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`
- Modify: `docs/ops/2026-04-02-project-health-scorecard.md`

**Step 1: Write the failing tests**

Add tests for:

- a maintained CLI command that summarizes memory writeback, curation, and queue/job health together
- actionable operator output for recent failures, scheduled backlog, and curation outcomes

**Step 2: Run focused tests to verify RED**

Run:

```bash
uv run pytest tests/unit/server_ops/test_memory_observability.py tests/integration/test_cli_server_ops.py -q
```

Expected: FAIL because the observability summary surface does not exist yet.

**Step 3: Implement the minimal observability surface**

Add:

- a local-audit summary helper for memory writeback health, curation outcomes, and queued/running memory jobs
- a maintained server CLI command that emits JSON and concise text output
- doc updates explaining how to inspect memory operations health

**Step 4: Re-run focused tests to verify GREEN**

Run:

```bash
uv run pytest tests/unit/server_ops/test_memory_observability.py tests/integration/test_cli_server_ops.py -q
```

### Task 4: Run closeout verification and record outcomes

**Files:**
- Modify: `docs/plans/2026-04-03-memory-operations-next-phase.md`

**Step 1: Run verification**

Run:

```bash
uv run pytest tests/unit/server_ops/test_memory_curation_queue.py tests/unit/server_ops/test_systemd_memory_curation.py tests/unit/memory/test_evaluation.py tests/unit/server_ops/test_memory_observability.py tests/unit/memory/test_provider.py tests/unit/server_ops/test_memory_curation.py tests/unit/server_ops/test_memory_curation_execution.py tests/integration/test_cli_server_ops.py tests/integration/test_memory_evaluation_matrix.py tests/integration/test_private_registry_memory_flow.py -q
make doctor
make ci-fast
git status --short
```

**Step 2: Commit**

```bash
git add server/jobs.py server/worker.py src/infinitas_skill/server/ops.py src/infinitas_skill/server/systemd.py src/infinitas_skill/memory/evaluation.py src/infinitas_skill/memory/__init__.py src/infinitas_skill/server/memory_observability.py tests/unit/server_ops/test_memory_curation_queue.py tests/unit/server_ops/test_systemd_memory_curation.py tests/unit/memory/test_evaluation.py tests/unit/server_ops/test_memory_observability.py tests/integration/test_cli_server_ops.py tests/integration/test_memory_evaluation_matrix.py tests/fixtures/memory_eval/usefulness_cases.json docs/ai/memory.md docs/ops/server-deployment.md README.md docs/ops/2026-04-02-project-health-scorecard.md docs/plans/2026-04-03-memory-operations-next-phase.md
git commit -m "feat: expand memory operations"
```
