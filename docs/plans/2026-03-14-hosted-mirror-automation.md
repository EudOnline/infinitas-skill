# Hosted Mirror Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the next hosted-ops automation slice so operators can schedule one-way outward mirroring to GitHub or another backup remote without hand-writing `systemd` units.

**Architecture:** Reuse the existing `scripts/mirror-registry.sh` as the only mirroring executor. Extend `scripts/render-hosted-systemd.py` with optional mirror arguments that render a `mirror.service` / `mirror.timer` pair only when an explicit mirror remote is provided, preserving the current “GitHub is optional and one-way only” deployment model. Keep this slice additive: no changes to the mirror semantics themselves, only automation around the existing trusted helper.

**Tech Stack:** Python 3.11+, stdlib (`argparse`, `pathlib`), existing bash mirror helper, existing `systemd` bundle renderer, script-style regression tests.

---

### Task 1: Add failing mirror automation coverage

**Files:**
- Create: `scripts/test-hosted-mirror-automation.py`
- Reference: `scripts/test-mirror-registry.py`
- Reference: `scripts/test-hosted-service-bundle.py`
- Reference: `docs/ops/server-deployment.md`

**Step 1: Write the failing test**

Create `scripts/test-hosted-mirror-automation.py` with scenarios that:

- run `scripts/render-hosted-systemd.py` with:
  - `--mirror-remote github-mirror`
  - `--mirror-branch main`
  - `--mirror-on-calendar daily`
- expect rendered files:
  - `<prefix>-mirror.service`
  - `<prefix>-mirror.timer`
- assert the mirror service includes:
  - `mirror-registry.sh`
  - `--remote github-mirror`
  - `--branch main`
- assert the mirror timer includes:
  - `OnCalendar=daily`

Also assert deployment docs mention:

- optional mirror timer generation
- enabling `infinitas-hosted-mirror.timer`
- one-way outward mirroring

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-mirror-automation.py
```

Expected: FAIL because mirror service/timer rendering does not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-hosted-mirror-automation.py
git commit -m "test: add hosted mirror automation coverage"
```

### Task 2: Render mirror service and timer

**Files:**
- Modify: `scripts/render-hosted-systemd.py`
- Modify: `scripts/test-hosted-mirror-automation.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`

**Step 1: Add renderer args**

Add:

- `--mirror-remote`
- `--mirror-branch`
- `--mirror-on-calendar`

Behavior:

- if `--mirror-remote` is omitted, do not render mirror units
- if `--mirror-remote` is provided, render:
  - `<prefix>-mirror.service`
  - `<prefix>-mirror.timer`
- the mirror service should execute `scripts/mirror-registry.sh` with:
  - `--remote <mirror-remote>`
  - optional `--branch <mirror-branch>`
- the timer should target the mirror service on the configured schedule

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-mirror-automation.py
```

Expected: PASS.

**Step 3: Update docs**

Document:

- that mirror automation is optional
- how to include mirror units in the rendered bundle
- how to enable the mirror timer
- that the timer preserves the existing one-way mirror rule

**Step 4: Run adjacent regression checks**

Run:

```bash
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

**Step 5: Commit**

```bash
git add scripts/render-hosted-systemd.py scripts/test-hosted-mirror-automation.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted mirror timer automation"
```

### Task 3: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-mirror-automation.py
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
git add docs/plans/2026-03-14-hosted-mirror-automation.md scripts/test-hosted-mirror-automation.py scripts/render-hosted-systemd.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted mirror timer automation"
```
