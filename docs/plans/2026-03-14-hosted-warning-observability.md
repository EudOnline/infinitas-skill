# Hosted Warning Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the next hosted-ops observability slice so best-effort publish hook failures remain visible to operators through regression coverage and scheduled state inspection alerts.

**Architecture:** Keep this slice small and operational. Add one focused regression script that proves a failed mirror hook records a warning while the publish job still completes. Then extend `scripts/inspect-hosted-state.py` to summarize completed jobs whose logs contain `WARNING:` and optionally alert on them via a new threshold. Finally, extend `scripts/render-hosted-systemd.py` so the generated inspect service can pass that warning threshold into scheduled runs.

**Tech Stack:** Python 3.11+, existing hosted worker + FastAPI test scaffolding, existing SQLAlchemy-based inspection script, existing `systemd` bundle renderer, script-style regression tests.

---

### Task 1: Add failing warning-observability coverage

**Files:**
- Create: `scripts/test-hosted-warning-observability.py`
- Reference: `scripts/test-hosted-publish-hooks.py`
- Reference: `scripts/test-hosted-ops-alerting.py`
- Reference: `scripts/test-worker-publish.py`

**Step 1: Write the failing test**

Create `scripts/test-hosted-warning-observability.py` with scenarios that:

- create a temp hosted repo with:
  - valid `origin`
  - intentionally missing mirror remote configured via `INFINITAS_SERVER_MIRROR_REMOTE=missing-remote`
- queue validate / promote / publish for a fixture skill
- run one worker loop
- assert:
  - the publish job status is still `completed`
  - the publish job log contains `WARNING: publish mirror hook failed`
  - release artifacts still land in the hosted artifact directory

Then inspect the same DB with:

- `scripts/inspect-hosted-state.py --json --max-warning-jobs 0`

and assert:

- exit status `2`
- payload contains:
  - `ok: false`
  - `jobs.warning_count >= 1`
  - `jobs.recent_warnings` containing the publish job
  - `alerts` containing `warning_jobs`

Also assert `scripts/render-hosted-systemd.py` can render an inspect service that includes:

- `--inspect-max-warning-jobs 0`

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-warning-observability.py
```

Expected: FAIL because warning jobs are not yet surfaced by the inspector or renderer.

**Step 3: Commit**

```bash
git add scripts/test-hosted-warning-observability.py
git commit -m "test: add hosted warning observability coverage"
```

### Task 2: Implement warning surfacing in inspection

**Files:**
- Modify: `scripts/inspect-hosted-state.py`
- Modify: `scripts/render-hosted-systemd.py`
- Modify: `scripts/test-hosted-warning-observability.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`

**Step 1: Add warning summarization and threshold**

Extend `scripts/inspect-hosted-state.py` with:

- `--max-warning-jobs`

Behavior:

- count jobs whose `log` contains `WARNING:`
- include:
  - `jobs.warning_count`
  - `jobs.recent_warnings`
- when `--max-warning-jobs` is exceeded:
  - emit alert entry `warning_jobs`
  - keep normal summary output
  - exit `2`

**Step 2: Extend the inspect service renderer**

Add:

- `--inspect-max-warning-jobs`

When configured, render the inspect service with:

- `--max-warning-jobs <value>`

**Step 3: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-warning-observability.py
```

Expected: PASS.

**Step 4: Update docs**

Document:

- that best-effort publish hook warnings are visible in job logs
- that `inspect-hosted-state.py` can summarize and alert on warning-bearing jobs
- how to wire the warning threshold into scheduled inspect runs

**Step 5: Run adjacent regression checks**

Run:

```bash
python3 scripts/test-hosted-publish-hooks.py
python3 scripts/test-hosted-mirror-automation.py
python3 scripts/test-worker-publish.py
python3 scripts/test-hosted-backup-retention.py
python3 scripts/test-hosted-ops-alerting.py
python3 scripts/test-hosted-ops-drills.py
python3 scripts/test-hosted-service-bundle.py
python3 scripts/test-server-ops.py
python3 scripts/test-mirror-registry.py
python3 scripts/test-hosted-api.py
git diff --check
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/inspect-hosted-state.py scripts/render-hosted-systemd.py scripts/test-hosted-warning-observability.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted warning observability"
```

### Task 3: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-warning-observability.py
python scripts/test-hosted-publish-hooks.py
python scripts/test-hosted-mirror-automation.py
python scripts/test-worker-publish.py
python scripts/test-hosted-backup-retention.py
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
git add docs/plans/2026-03-14-hosted-warning-observability.md scripts/test-hosted-warning-observability.py scripts/inspect-hosted-state.py scripts/render-hosted-systemd.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted warning observability"
```
