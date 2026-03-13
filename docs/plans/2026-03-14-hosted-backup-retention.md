# Hosted Backup Retention Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the next hosted-ops safety slice so scheduled backups do not grow without bound by introducing explicit backup-retention pruning and a generated `systemd` prune timer.

**Architecture:** Keep this slice small and filesystem-first. Add one standalone Python CLI that prunes only recognized hosted backup directories under the configured backup root, preserving the newest `N` snapshots while leaving unknown directories untouched. Then extend `scripts/render-hosted-systemd.py` to generate a prune `service/timer` pair so operators can schedule retention cleanup next to the existing backup and inspect timers.

**Tech Stack:** Python 3.11+, stdlib (`argparse`, `json`, `pathlib`, `re`, `shutil`), existing hosted backup naming conventions, existing `systemd` bundle renderer, script-style regression tests.

---

### Task 1: Add failing retention coverage

**Files:**
- Create: `scripts/test-hosted-backup-retention.py`
- Reference: `scripts/test-server-ops.py`
- Reference: `scripts/test-hosted-service-bundle.py`
- Reference: `docs/ops/server-backup-and-restore.md`

**Step 1: Write the failing test**

Create `scripts/test-hosted-backup-retention.py` with scenarios that:

- create a temp backup root containing:
  - 4 valid hosted backup directories named with the existing timestamp convention
  - a `manifest.json` inside each valid directory
  - 1 unrelated directory that should be ignored
- run `scripts/prune-hosted-backups.py --backup-root <root> --keep-last 2 --json`
- expect exit `0` and JSON payload showing:
  - `ok: true`
  - exactly 2 deleted backup directories
  - exactly 2 kept backup directories
  - ignored entries preserved
- run `scripts/render-hosted-systemd.py` with prune arguments and assert it renders:
  - `<prefix>-prune.service`
  - `<prefix>-prune.timer`
  - the prune service includes `prune-hosted-backups.py`, `--backup-root`, and `--keep-last`
  - the timer includes the configured prune schedule

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-backup-retention.py
```

Expected: FAIL because the prune helper and prune service/timer do not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-hosted-backup-retention.py
git commit -m "test: add hosted backup retention coverage"
```

### Task 2: Implement backup-retention pruning

**Files:**
- Create: `scripts/prune-hosted-backups.py`
- Modify: `scripts/test-hosted-backup-retention.py`
- Modify: `docs/ops/server-backup-and-restore.md`
- Modify: `README.md`

**Step 1: Implement the minimal prune CLI**

Implement a script that accepts:

- `--backup-root`
- `--keep-last`
- `--json`

Behavior:

- require that `--backup-root` exists and is a directory
- only consider directories whose names match the hosted backup timestamp naming pattern and that contain `manifest.json`
- sort eligible backup directories newest-first
- keep the newest `--keep-last` entries
- delete older eligible backup directories recursively
- leave unrelated or malformed directories untouched and report them under `ignored`
- emit a machine-readable summary with `kept`, `deleted`, and `ignored`

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-backup-retention.py
```

Expected: still FAIL, but only because the rendered prune service/timer is missing.

**Step 3: Update docs**

Document:

- how retention pruning works
- that only recognized hosted backup directories are deleted
- a reasonable starting retention value for a small single-node deployment

**Step 4: Commit**

```bash
git add scripts/prune-hosted-backups.py scripts/test-hosted-backup-retention.py docs/ops/server-backup-and-restore.md README.md
git commit -m "feat: add hosted backup retention pruning"
```

### Task 3: Render prune service and timer

**Files:**
- Modify: `scripts/render-hosted-systemd.py`
- Modify: `scripts/test-hosted-backup-retention.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `docs/ops/server-backup-and-restore.md`
- Modify: `README.md`

**Step 1: Add renderer args**

Add:

- `--prune-on-calendar`
- `--prune-keep-last`

Render:

- `<prefix>-prune.service`
- `<prefix>-prune.timer`

The prune service should execute `scripts/prune-hosted-backups.py` with:

- the configured backup root
- the configured `--keep-last`
- `--json`

The timer should run on the configured schedule and target the prune service.

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-backup-retention.py
```

Expected: PASS.

**Step 3: Update docs**

Document:

- how to enable the prune timer
- how prune scheduling relates to the backup timer
- that prune only removes older recognized backup snapshots, not arbitrary folders

**Step 4: Run adjacent regression checks**

Run:

```bash
python3 scripts/test-hosted-ops-alerting.py
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
git add scripts/render-hosted-systemd.py scripts/test-hosted-backup-retention.py docs/ops/server-deployment.md docs/ops/server-backup-and-restore.md README.md
git commit -m "feat: add hosted backup prune timer"
```

### Task 4: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
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
git add docs/plans/2026-03-14-hosted-backup-retention.md scripts/test-hosted-backup-retention.py scripts/prune-hosted-backups.py scripts/render-hosted-systemd.py docs/ops/server-deployment.md docs/ops/server-backup-and-restore.md README.md
git commit -m "feat: add hosted backup retention automation"
```
