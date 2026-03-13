# Hosted Service Bundle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the hosted registry deployment docs into an executable deployment bundle by generating systemd units, an environment template, and a stable worker entrypoint for single-node server installs.

**Architecture:** Add a small renderer script that writes an operator bundle with an env example, API service unit, worker service unit, and backup service/timer pair. Add a dedicated long-running worker runner so the generated service starts a real poll loop instead of a one-shot queue drain. Keep everything single-node and SQLite-first to match the current hosted MVP.

**Tech Stack:** Python 3.11+, stdlib (`argparse`, `json`, `time`, `pathlib`), existing `server.worker.run_worker_loop`, current ops docs, script-style regression tests.

---

### Task 1: Add failing deployment-bundle coverage

**Files:**
- Create: `scripts/test-hosted-service-bundle.py`
- Reference: `scripts/test-server-ops.py`
- Reference: `docs/ops/server-deployment.md`
- Reference: `docs/ops/server-backup-and-restore.md`

**Step 1: Write the failing test**

Create `scripts/test-hosted-service-bundle.py` with scenarios that:

- run `scripts/render-hosted-systemd.py` against a temp output dir
- assert the output dir contains:
  - `<prefix>.env.example`
  - `<prefix>-api.service`
  - `<prefix>-worker.service`
  - `<prefix>-backup.service`
  - `<prefix>-backup.timer`
- assert the rendered files contain:
  - `EnvironmentFile=...`
  - `run-hosted-worker.py`
  - `backup-hosted-registry.py`
  - `OnCalendar=...`
  - the passed repo root and python binary
- assert docs mention the generated systemd bundle

Also add a worker-runner smoke scenario that:

- configures a temp empty SQLite database
- runs `scripts/run-hosted-worker.py --once`
- expects exit code `0`

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-service-bundle.py
```

Expected: FAIL because the renderer and worker runner do not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-hosted-service-bundle.py
git commit -m "test: add hosted service bundle coverage"
```

### Task 2: Implement the worker service entrypoint

**Files:**
- Create: `scripts/run-hosted-worker.py`
- Modify: `server/worker.py`
- Modify: `scripts/test-hosted-service-bundle.py`

**Step 1: Implement a stable worker runner**

Create a CLI wrapper that supports:

- `--poll-interval`
- `--once`
- `--limit`

Behavior:

- `--once` drains the queue once and exits with `0`
- default mode loops forever, sleeping for the poll interval when no jobs were processed
- reuses `server.worker.run_worker_loop`

Keep `server/worker.py` import-safe and only add helpers if needed.

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-service-bundle.py
```

Expected: still FAIL, but only because the systemd renderer is missing.

**Step 3: Commit**

```bash
git add scripts/run-hosted-worker.py server/worker.py scripts/test-hosted-service-bundle.py
git commit -m "feat: add hosted worker service entrypoint"
```

### Task 3: Implement the rendered systemd bundle

**Files:**
- Create: `scripts/render-hosted-systemd.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `docs/ops/server-backup-and-restore.md`
- Modify: `README.md`
- Modify: `scripts/test-hosted-service-bundle.py`

**Step 1: Implement the renderer**

Implement a script that accepts:

- `--output-dir`
- `--repo-root`
- `--python-bin`
- `--env-file`
- `--service-prefix`
- `--listen-host`
- `--listen-port`
- `--worker-poll-interval`
- `--backup-output-dir`
- `--backup-on-calendar`
- `--backup-label`

Render:

- `<prefix>.env.example`
- `<prefix>-api.service`
- `<prefix>-worker.service`
- `<prefix>-backup.service`
- `<prefix>-backup.timer`

The env example should include:

- `INFINITAS_SERVER_DATABASE_URL`
- `INFINITAS_SERVER_SECRET_KEY`
- `INFINITAS_SERVER_BOOTSTRAP_USERS`
- `INFINITAS_SERVER_REPO_PATH`
- `INFINITAS_SERVER_ARTIFACT_PATH`
- optional `INFINITAS_SERVER_REPO_LOCK_PATH`

The API unit should start `uvicorn server.app:app`.
The worker unit should start `scripts/run-hosted-worker.py`.
The backup timer should trigger the backup service on the configured schedule.

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-service-bundle.py
```

Expected: PASS.

**Step 3: Update docs**

Document:

- how to generate the deployment bundle
- how to install the env file and units
- how to enable the backup timer
- that this batch still targets SQLite-first single-node deployments

**Step 4: Run adjacent regression checks**

Run:

```bash
python3 scripts/test-server-ops.py
python3 scripts/test-mirror-registry.py
python3 scripts/test-hosted-api.py
git diff --check
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/render-hosted-systemd.py scripts/test-hosted-service-bundle.py docs/ops/server-deployment.md docs/ops/server-backup-and-restore.md README.md
git commit -m "feat: add hosted systemd deployment bundle"
```

### Task 4: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
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
git add docs/plans/2026-03-14-hosted-service-bundle.md scripts/test-hosted-service-bundle.py scripts/run-hosted-worker.py scripts/render-hosted-systemd.py docs/ops/server-deployment.md docs/ops/server-backup-and-restore.md README.md
git commit -m "feat: add hosted deployment service bundle automation"
```
