# Hosted Job Lease And Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Execution Status

- Completed on 2026-04-05.
- Landed job lease metadata, lease-aware claiming and stale-job reclaim, worker heartbeat/cleanup helpers, and inspection metrics for stale-running age visibility.

**Goal:** Add lease-based job claiming, heartbeats, stale-job recovery, and better inspection visibility so hosted release materialization does not depend on manual retries after worker crashes.

**Architecture:** Extend the `jobs` table with lease metadata, move worker ownership from plain `running` state to `running + lease_expires_at`, and add explicit stale-job recovery helpers that can either reclaim or fail abandoned work. Keep the queue API small: enqueue stays simple, claim becomes lease-aware, processing refreshes the lease during long work, and inspection surfaces stale/running age so operators can see bad states before users do.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, SQLite-first tests, existing hosted server ops CLI.

---

### Task 1: Add Lease Metadata To The Job Model

**Files:**
- Modify: `server/models.py:31-48`
- Create: `alembic/versions/<new_revision>_add_job_leases.py`
- Test: `tests/unit/server_ops/test_job_queue_claiming.py`

**Step 1: Write the failing test**

Add a test that creates a `Job`, persists it, and asserts new fields such as `lease_expires_at`, `heartbeat_at`, and `attempt_count` round-trip through SQLAlchemy.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/server_ops/test_job_queue_claiming.py -q`
Expected: FAIL because the new model fields and migration do not exist yet.

**Step 3: Write minimal implementation**

Add nullable lease timestamps plus a positive integer attempt counter to `Job`, then add an Alembic migration that backfills safe defaults for existing rows.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/server_ops/test_job_queue_claiming.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add server/models.py alembic/versions/<new_revision>_add_job_leases.py tests/unit/server_ops/test_job_queue_claiming.py
git commit -m "feat: add hosted job lease metadata"
```

### Task 2: Make Claiming Lease-Aware And Recover Stale Jobs

**Files:**
- Modify: `server/jobs.py:43-116`
- Modify: `server/modules/release/router.py:58-89`
- Test: `tests/unit/server_ops/test_job_queue_claiming.py`
- Test: `tests/integration/test_private_registry_release_materialization.py`

**Step 1: Write the failing tests**

Add tests for:
- claiming a queued job sets `lease_expires_at`, `heartbeat_at`, and increments attempts;
- a second worker can reclaim a stale `running` job after lease expiry;
- repeating release creation after a crashed worker results in recoverable queue state without duplicating healthy queued work.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/server_ops/test_job_queue_claiming.py tests/integration/test_private_registry_release_materialization.py -q`
Expected: FAIL because stale leases are not yet modeled.

**Step 3: Write minimal implementation**

Teach `claim_next_job()` to:
- claim queued jobs with a fresh lease;
- optionally reclaim stale running jobs whose lease expired;
- append log lines for claim/reclaim events;
- preserve the existing atomic `UPDATE ... RETURNING` behavior.

Update release requeue checks so they distinguish healthy queued work from stale running work using the new lease fields rather than raw status alone.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/server_ops/test_job_queue_claiming.py tests/integration/test_private_registry_release_materialization.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add server/jobs.py server/modules/release/router.py tests/unit/server_ops/test_job_queue_claiming.py tests/integration/test_private_registry_release_materialization.py
git commit -m "feat: add lease-aware hosted job claiming"
```

### Task 3: Add Worker Heartbeats And Failure Recovery

**Files:**
- Modify: `server/worker.py:29-135`
- Modify: `server/jobs.py`
- Test: `tests/unit/server_ops/test_job_queue_claiming.py`
- Test: `tests/integration/test_private_registry_release_materialization.py`

**Step 1: Write the failing tests**

Add tests for:
- worker heartbeats extending the active lease during long processing;
- stale claimed jobs becoming recoverable if a worker dies before completion;
- completed jobs clearing lease metadata so inspection is accurate.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/server_ops/test_job_queue_claiming.py tests/integration/test_private_registry_release_materialization.py -q`
Expected: FAIL because workers do not heartbeat or clear lease ownership yet.

**Step 3: Write minimal implementation**

Add small helpers such as `heartbeat_job()` and `complete_job()`/`fail_job()` so `process_job()` updates heartbeat/lease timestamps at well-defined boundaries. Keep memory writeback behavior unchanged and continue to dedupe `task.release.ready`.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/server_ops/test_job_queue_claiming.py tests/integration/test_private_registry_release_materialization.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add server/worker.py server/jobs.py tests/unit/server_ops/test_job_queue_claiming.py tests/integration/test_private_registry_release_materialization.py
git commit -m "feat: heartbeat hosted jobs during worker execution"
```

### Task 4: Surface Lease Health In Inspection Output

**Files:**
- Modify: `src/infinitas_skill/server/inspection_summary.py:18-133`
- Modify: `src/infinitas_skill/server/ops.py:47-118`
- Test: `tests/unit/server_ops/test_inspection_summary.py`
- Test: `tests/integration/test_cli_server_ops.py`

**Step 1: Write the failing tests**

Add tests asserting inspection JSON includes:
- `stale_running` count;
- longest running age;
- oldest queued age;
- recent reclaimed/stale jobs when present.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/server_ops/test_inspection_summary.py tests/integration/test_cli_server_ops.py -q`
Expected: FAIL because inspection only reports raw status counts today.

**Step 3: Write minimal implementation**

Extend serialization and summary logic to compute age-based metrics from `created_at`, `started_at`, `heartbeat_at`, and `lease_expires_at`. Add alert thresholds only if the new metrics are already useful without adding noisy configuration.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/server_ops/test_inspection_summary.py tests/integration/test_cli_server_ops.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/infinitas_skill/server/inspection_summary.py src/infinitas_skill/server/ops.py tests/unit/server_ops/test_inspection_summary.py tests/integration/test_cli_server_ops.py
git commit -m "feat: expose hosted job lease health in inspection output"
```

### Task 5: Run Full Verification And Document Recovery Semantics

**Files:**
- Modify: `docs/ops/<relevant-hosted-ops-doc>.md`
- Modify: `docs/plans/2026-04-05-hosted-job-lease-and-recovery-implementation.md`
- Verify: existing scripts and regression suite

**Step 1: Write the failing doc/test check**

If there is an ops doc covering worker behavior, add a small note describing lease expiry, reclaim semantics, and operator expectations. If no doc exists, add one concise hosted-ops note.

**Step 2: Run verification to find gaps**

Run:

```bash
uv run pytest tests/unit/server_ops/test_job_queue_claiming.py tests/unit/server_ops/test_inspection_summary.py tests/integration/test_private_registry_release_materialization.py tests/integration/test_cli_server_ops.py tests/integration/test_registry_read_tokens.py -q
make ci-fast
./scripts/check-all.sh full-regression
```

Expected: at least one command fails until all previous tasks are complete.

**Step 3: Write minimal implementation**

Update docs only as needed to match actual behavior. Do not invent extra queue states if the implementation does not use them.

**Step 4: Run verification to verify it passes**

Run the full command set above again.
Expected: PASS across all commands.

**Step 5: Commit**

```bash
git add docs/ops docs/plans/2026-04-05-hosted-job-lease-and-recovery-implementation.md
git commit -m "docs: record hosted job lease recovery behavior"
```
