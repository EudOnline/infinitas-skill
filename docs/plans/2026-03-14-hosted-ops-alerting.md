# Hosted Ops Alerting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn hosted state inspection from a passive report into an operational alert surface by adding configurable thresholds, non-zero exit codes, and a generated `systemd` inspection service/timer.

**Architecture:** Extend `scripts/inspect-hosted-state.py` with queue/failure thresholds and a structured `alerts` section. When thresholds are exceeded, the script should still emit a summary but exit non-zero so `systemd` can treat the run as failed. Then extend `scripts/render-hosted-systemd.py` to generate an inspection `service/timer` pair that runs the script on a schedule with operator-chosen thresholds.

**Tech Stack:** Python 3.11+, stdlib (`argparse`, `json`, `pathlib`), existing SQLAlchemy-based state inspection script, existing `systemd` bundle renderer, script-style regression tests.

---

### Task 1: Add failing alerting coverage

**Files:**
- Create: `scripts/test-hosted-ops-alerting.py`
- Reference: `scripts/test-hosted-ops-drills.py`
- Reference: `scripts/test-hosted-service-bundle.py`

**Step 1: Write the failing test**

Create `scripts/test-hosted-ops-alerting.py` with scenarios that:

- create a temp hosted SQLite DB with:
  - 2 queued jobs
  - 1 failed job
  - 1 published submission
- run `scripts/inspect-hosted-state.py --json --max-queued-jobs 1 --max-failed-jobs 0`
- expect a non-zero exit and JSON payload containing:
  - `ok: false`
  - `alerts` list with queued and failed thresholds
- run the same script with more permissive thresholds and expect exit `0`

Also assert that `scripts/render-hosted-systemd.py` renders:

- `<prefix>-inspect.service`
- `<prefix>-inspect.timer`

and that the inspect service includes:

- `inspect-hosted-state.py`
- the configured threshold flags
- the configured `database-url`

while the timer includes:

- the configured inspection schedule

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-ops-alerting.py
```

Expected: FAIL because alert thresholds and inspect service/timer do not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-hosted-ops-alerting.py
git commit -m "test: add hosted ops alerting coverage"
```

### Task 2: Implement alert thresholds in state inspection

**Files:**
- Modify: `scripts/inspect-hosted-state.py`
- Modify: `scripts/test-hosted-ops-alerting.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`

**Step 1: Add threshold args**

Add:

- `--max-queued-jobs`
- `--max-running-jobs`
- `--max-failed-jobs`

Behavior:

- if a threshold is omitted, do not alert on that dimension
- if a threshold is exceeded, include an alert entry with `kind`, `actual`, `threshold`, and `message`
- still emit the normal summary
- exit `2` when alerts are present
- exit `0` when no alerts are present

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-ops-alerting.py
```

Expected: still FAIL, but only because the rendered inspect service/timer is missing.

**Step 3: Update docs**

Document the new threshold flags and the meaning of the non-zero exit code for operator automation.

**Step 4: Commit**

```bash
git add scripts/inspect-hosted-state.py scripts/test-hosted-ops-alerting.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted ops alert thresholds"
```

### Task 3: Render inspect service and timer

**Files:**
- Modify: `scripts/render-hosted-systemd.py`
- Modify: `scripts/test-hosted-ops-alerting.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`

**Step 1: Add renderer args**

Add:

- `--inspect-on-calendar`
- `--inspect-limit`
- `--inspect-max-queued-jobs`
- `--inspect-max-running-jobs`
- `--inspect-max-failed-jobs`

Render:

- `<prefix>-inspect.service`
- `<prefix>-inspect.timer`

The inspect service should execute `scripts/inspect-hosted-state.py` with:

- the configured database URL
- the configured `--limit`
- any configured threshold flags
- `--json`

The timer should run on the configured schedule and target the inspect service.

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-ops-alerting.py
```

Expected: PASS.

**Step 3: Update docs**

Document:

- how to enable the inspect timer
- that a failed inspect service run means a threshold breach, not necessarily a crashed process
- example threshold choices for a small single-node deployment

**Step 4: Run adjacent regression checks**

Run:

```bash
python3 scripts/test-hosted-ops-drills.py
python3 scripts/test-hosted-service-bundle.py
python3 scripts/test-server-ops.py
python3 scripts/test-mirror-registry.py
python3 scripts/test-hosted-api.py
git diff --check
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/render-hosted-systemd.py scripts/test-hosted-ops-alerting.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted ops inspection timer"
```

### Task 4: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-ops-alerting.py
python scripts/test-hosted-ops-drills.py
python scripts/test-hosted-service-bundle.py
python scripts/test-server-ops.py
python scripts/test-mirror-registry.py
python scripts/test-hosted-api.py
git diff --check
git status --short
```

Expected: all checks pass and the worktree is clean except for intentional tracked changes.

**Step 2: Commit**

```bash
git add docs/plans/2026-03-14-hosted-ops-alerting.md scripts/test-hosted-ops-alerting.py scripts/inspect-hosted-state.py scripts/render-hosted-systemd.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted ops alerting automation"
```
