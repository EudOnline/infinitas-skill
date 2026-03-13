# Hosted Ops Drills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the next operational safety slice for the hosted registry so operators can rehearse backup restores non-destructively and inspect job/submission state from the hosted database without opening SQLite manually.

**Architecture:** Add two small operator CLIs. First, a restore-rehearsal script that validates a backup directory, verifies the repo bundle, copies the SQLite database, extracts artifacts, and proves the backup is structurally restorable into a staging directory. Second, a state-inspection script that summarizes job queues, failures, and submission status counts from the hosted database. Keep both SQLite-first and non-destructive.

**Tech Stack:** Python 3.11+, stdlib (`argparse`, `json`, `sqlite3`, `tarfile`, `subprocess`, `shutil`, `pathlib`), SQLAlchemy models for hosted state inspection, existing backup manifest contract from `scripts/backup-hosted-registry.py`.

---

### Task 1: Add failing ops-drill coverage

**Files:**
- Create: `scripts/test-hosted-ops-drills.py`
- Reference: `scripts/test-server-ops.py`
- Reference: `scripts/backup-hosted-registry.py`
- Reference: `server/models.py`

**Step 1: Write the failing test**

Create `scripts/test-hosted-ops-drills.py` with scenarios that:

- create a temp repo, SQLite DB, and artifact directory
- run `scripts/backup-hosted-registry.py` to create a real backup set
- run `scripts/rehearse-hosted-restore.py` against that backup into a temp output dir
- assert the rehearsal output contains:
  - extracted repo clone
  - copied SQLite DB
  - extracted artifact directory with `ai-index.json` and `catalog/`
  - JSON summary referencing the backup label
- create a temp hosted DB with queued, failed, and completed jobs plus a couple of submissions
- run `scripts/inspect-hosted-state.py --json`
- assert queue counts, failed-job summaries, and submission status counts are correct

Also assert failures for:

- missing `manifest.json` in the backup dir
- missing `repo.bundle` referenced by the manifest

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-ops-drills.py
```

Expected: FAIL because the rehearsal and inspection scripts do not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-hosted-ops-drills.py
git commit -m "test: add hosted ops drill coverage"
```

### Task 2: Implement restore rehearsal

**Files:**
- Create: `scripts/rehearse-hosted-restore.py`
- Modify: `scripts/test-hosted-ops-drills.py`
- Modify: `docs/ops/server-backup-and-restore.md`

**Step 1: Implement the rehearsal script**

Implement a script that accepts:

- `--backup-dir`
- `--output-dir`
- `--json`

Behavior:

- load and validate `manifest.json`
- require the referenced repo bundle, DB backup file, and artifact archive to exist
- run `git bundle verify`
- clone the bundle into the output dir
- copy the SQLite DB backup into the output dir and verify it opens
- extract the artifact tarball into the output dir and verify `artifacts/ai-index.json` plus `artifacts/catalog/`

Output:

- human-readable summary by default
- machine-readable JSON with restored staging paths and manifest metadata when `--json` is used

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-ops-drills.py
```

Expected: still FAIL, but only because the state-inspection script is missing.

**Step 3: Update docs**

Document how to run a restore rehearsal before touching production restore paths.

**Step 4: Commit**

```bash
git add scripts/rehearse-hosted-restore.py scripts/test-hosted-ops-drills.py docs/ops/server-backup-and-restore.md
git commit -m "feat: add hosted restore rehearsal"
```

### Task 3: Implement hosted state inspection

**Files:**
- Create: `scripts/inspect-hosted-state.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`
- Modify: `scripts/test-hosted-ops-drills.py`

**Step 1: Implement the inspection script**

Implement a script that accepts:

- `--database-url`
- `--limit`
- `--json`

Behavior:

- validate the SQLite database path exists
- summarize jobs by status
- include recent failed jobs with `id`, `kind`, `submission_id`, `updated_at`, and `error_message`
- include recent queued/running jobs
- summarize submissions by status

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-ops-drills.py
```

Expected: PASS.

**Step 3: Update docs**

Document:

- how to inspect queue depth and recent failed jobs
- how the inspection script complements `server-healthcheck.py`
- that the current implementation remains SQLite-first

**Step 4: Run adjacent regression checks**

Run:

```bash
python3 scripts/test-hosted-service-bundle.py
python3 scripts/test-server-ops.py
python3 scripts/test-mirror-registry.py
python3 scripts/test-hosted-api.py
git diff --check
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/inspect-hosted-state.py scripts/test-hosted-ops-drills.py docs/ops/server-deployment.md docs/ops/server-backup-and-restore.md README.md
git commit -m "feat: add hosted ops inspection drills"
```

### Task 4: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
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
git add docs/plans/2026-03-14-hosted-ops-drills.md scripts/test-hosted-ops-drills.py scripts/rehearse-hosted-restore.py scripts/inspect-hosted-state.py docs/ops/server-deployment.md docs/ops/server-backup-and-restore.md README.md
git commit -m "feat: add hosted restore drills and state inspection"
```
