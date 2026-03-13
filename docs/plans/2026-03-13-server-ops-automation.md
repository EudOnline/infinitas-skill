# Hosted Server Ops Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the first executable server-ops automation layer for the hosted registry so operators can run a real health check and create a consistent backup set without relying on manual runbook interpretation.

**Architecture:** Keep this slice small and operational. Add one Python health-check CLI that validates the hosted API, repo path, artifact path, and database connectivity, plus one Python backup CLI that captures a repo bundle, SQLite database copy, artifact archive, and JSON manifest. Keep both tools filesystem-first and single-node friendly so they match the current hosted MVP while leaving PostgreSQL and object storage as later extensions.

**Tech Stack:** Python 3.11+, existing `pyproject.toml` environment, stdlib (`argparse`, `json`, `sqlite3`, `tarfile`, `subprocess`, `urllib`), existing hosted server settings/docs, standalone script-style regression tests.

---

### Task 1: Add failing ops automation coverage

**Files:**
- Create: `scripts/test-server-ops.py`
- Reference: `scripts/test-hosted-api.py`
- Reference: `scripts/test-mirror-registry.py`
- Reference: `docs/ops/server-deployment.md`
- Reference: `docs/ops/server-backup-and-restore.md`

**Step 1: Write the failing test**

Create `scripts/test-server-ops.py` with two scenarios:

- `server-healthcheck.py` succeeds when:
  - a temp repo checkout exists and is clean
  - a temp SQLite database exists
  - a temp artifact directory contains `ai-index.json` and `catalog/`
  - a temp HTTP health endpoint returns `{"ok": true}`
- `backup-hosted-registry.py` succeeds when:
  - given repo path, SQLite database path, artifact path, and output dir
  - it writes a backup directory containing a repo bundle, copied SQLite DB, artifact tarball, and `manifest.json`

Also assert failures for:

- missing artifact directory
- missing `ai-index.json`
- dirty repo backup attempt

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-server-ops.py
```

Expected: FAIL because the ops automation scripts do not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-server-ops.py
git commit -m "test: add hosted server ops automation coverage"
```

### Task 2: Implement hosted health-check automation

**Files:**
- Create: `scripts/server-healthcheck.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`
- Reference: `server/app.py`
- Reference: `server/settings.py`

**Step 1: Implement the minimal health-check CLI**

Implement a script that accepts:

- `--api-url`
- `--repo-path`
- `--artifact-path`
- `--database-url`
- `--token` (optional, reserved for future authenticated probes)
- `--json`

Checks:

- `GET <api-url>/healthz` returns HTTP 200 and `ok=true`
- repo path exists and is a git worktree
- artifact path exists and includes `ai-index.json` plus `catalog/`
- SQLite database path extracted from `sqlite:///...` exists and can answer `SELECT 1`

Output:

- human-readable success lines by default
- machine-readable summary with `--json`

**Step 2: Run the focused test and confirm it still fails on backup**

Run:

```bash
python3 scripts/test-server-ops.py
```

Expected: still FAIL, but only for the missing backup behavior.

**Step 3: Update docs**

Add explicit examples to `docs/ops/server-deployment.md` and `README.md` showing:

- how to run the health check
- what it verifies
- that phase 1 only supports SQLite database checks

**Step 4: Commit**

```bash
git add scripts/server-healthcheck.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted server health check automation"
```

### Task 3: Implement hosted backup automation

**Files:**
- Create: `scripts/backup-hosted-registry.py`
- Modify: `docs/ops/server-backup-and-restore.md`
- Modify: `README.md`
- Modify: `scripts/test-server-ops.py`

**Step 1: Implement the minimal backup CLI**

Implement a script that accepts:

- `--repo-path`
- `--database-url`
- `--artifact-path`
- `--output-dir`
- `--label`
- `--json`

Behavior:

- refuse to run if the repo worktree is dirty
- create a timestamped backup directory under `--output-dir`
- write `repo.bundle` using `git bundle create ... --all`
- copy the SQLite DB file into the backup directory
- archive the artifact directory as `artifacts.tar.gz`
- write `manifest.json` including timestamp, label, git HEAD, source paths, and generated file names

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-server-ops.py
```

Expected: PASS.

**Step 3: Document restore linkage**

Update `docs/ops/server-backup-and-restore.md` and `README.md` with:

- exact command examples
- backup directory contents
- note that PostgreSQL/object storage automation remains a future extension

**Step 4: Run adjacent regression checks**

Run:

```bash
python3 scripts/test-mirror-registry.py
python3 scripts/test-hosted-api.py
git diff --check
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/backup-hosted-registry.py scripts/test-server-ops.py docs/ops/server-backup-and-restore.md README.md
git commit -m "feat: add hosted server backup automation"
```

### Task 4: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-server-ops.py
python scripts/test-mirror-registry.py
python scripts/test-hosted-api.py
git diff --check
git status --short
```

Expected: all checks pass and working tree is clean except for intentional tracked changes.

**Step 2: Commit**

```bash
git add docs/ops/server-deployment.md docs/ops/server-backup-and-restore.md README.md scripts/server-healthcheck.py scripts/backup-hosted-registry.py scripts/test-server-ops.py
git commit -m "feat: automate hosted server health checks and backups"
```
