# Hosted Publish Hooks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the next hosted release-ops slice so a successful hosted publish can optionally trigger immediate one-way mirror completion hooks without changing the publish job’s primary success semantics.

**Architecture:** Keep this slice small and additive. Extend hosted server settings with optional mirror-hook configuration, then teach the worker’s publish path to run the existing `scripts/mirror-registry.sh` after artifact sync and the primary `origin` push succeed. Treat the hook as best-effort: if the mirror hook fails, keep the publish job successful but record a warning in the job log so operators still get an immediate signal while the scheduled mirror timer remains a fallback path.

**Tech Stack:** Python 3.11+, existing hosted worker code, existing bash mirror helper, existing script-style regression tests, environment-driven server configuration.

---

### Task 1: Add failing publish-hook coverage

**Files:**
- Create: `scripts/test-hosted-publish-hooks.py`
- Reference: `scripts/test-worker-publish.py`
- Reference: `scripts/test-mirror-registry.py`
- Reference: `server/worker.py`

**Step 1: Write the failing test**

Create `scripts/test-hosted-publish-hooks.py` with a scenario that:

- copies the repo into a temp server-owned checkout
- creates both:
  - a bare `origin.git`
  - a bare `mirror.git`
- configures hosted env with:
  - `INFINITAS_SERVER_MIRROR_REMOTE=github-mirror`
  - `INFINITAS_SERVER_MIRROR_BRANCH=main`
- queues validate / promote / publish for a fixture skill
- runs one worker loop
- asserts:
  - publish succeeds
  - the mirror bare remote receives the `main` branch
  - the publish job log mentions `mirror-registry.sh`
  - the publish job log mentions the configured mirror remote

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-publish-hooks.py
```

Expected: FAIL because no publish-completion mirror hook exists yet.

**Step 3: Commit**

```bash
git add scripts/test-hosted-publish-hooks.py
git commit -m "test: add hosted publish hook coverage"
```

### Task 2: Implement optional post-publish mirror hook

**Files:**
- Modify: `server/settings.py`
- Modify: `server/worker.py`
- Modify: `scripts/test-hosted-publish-hooks.py`
- Modify: `docs/ai/publish.md`
- Modify: `docs/release-checklist.md`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`

**Step 1: Add optional settings**

Add:

- `mirror_remote`
- `mirror_branch`

Read them from:

- `INFINITAS_SERVER_MIRROR_REMOTE`
- `INFINITAS_SERVER_MIRROR_BRANCH`

Behavior:

- when `mirror_remote` is empty, no publish hook runs
- when `mirror_remote` is set, the publish worker runs `scripts/mirror-registry.sh --remote <mirror_remote>` and appends `--branch <mirror_branch>` if configured

**Step 2: Hook into publish completion**

In the publish job flow:

- keep the current order for release + artifact sync + `origin` push
- then run the optional mirror hook
- if the mirror hook succeeds:
  - append the executed command log to the job log
- if the mirror hook fails:
  - append a `WARNING:` log entry containing the failure
  - do not fail the publish job solely because the optional mirror hook failed

**Step 3: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-publish-hooks.py
```

Expected: PASS.

**Step 4: Update docs**

Document:

- the new optional env vars
- that immediate publish hooks are best-effort
- that scheduled `mirror.timer` remains the safety-net fallback

**Step 5: Run adjacent regression checks**

Run:

```bash
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
git add server/settings.py server/worker.py scripts/test-hosted-publish-hooks.py docs/ai/publish.md docs/release-checklist.md docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted publish mirror hooks"
```

### Task 3: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
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
git add docs/plans/2026-03-14-hosted-publish-hooks.md scripts/test-hosted-publish-hooks.py server/settings.py server/worker.py docs/ai/publish.md docs/release-checklist.md docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted publish mirror hooks"
```
