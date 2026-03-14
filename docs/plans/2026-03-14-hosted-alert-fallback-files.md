# Hosted Alert Fallback Files Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the next hosted-ops reliability slice so alerting runs have a stable local fallback artifact when webhook delivery fails.

**Architecture:** Keep this slice small and file-first. Extend `scripts/inspect-hosted-state.py` with an optional fallback file path that writes the alert summary JSON when alerts exist and webhook delivery is unavailable. Record fallback write status in the returned notification metadata so operators can tell whether the fallback succeeded. Then extend `scripts/render-hosted-systemd.py` to pass an optional fallback file path into the generated inspect service so systemd timers can leave behind a last-known alert snapshot for external collectors.

**Tech Stack:** Python 3.11+, stdlib (`argparse`, `json`, `pathlib`, `tempfile`, `urllib.request`, `http.server`, `threading`), existing SQLAlchemy-based inspection script, existing `systemd` bundle renderer, script-style regression tests.

---

### Task 1: Add failing fallback coverage

**Files:**
- Create: `scripts/test-hosted-alert-fallback-files.py`
- Reference: `scripts/test-hosted-alert-webhooks.py`
- Reference: `scripts/test-hosted-warning-observability.py`
- Reference: `scripts/render-hosted-systemd.py`

**Step 1: Write the failing test**

Create `scripts/test-hosted-alert-fallback-files.py` with scenarios that:

- create a temp hosted SQLite DB containing:
  - 1 completed publish job whose log contains `WARNING:`
  - 1 published submission
- start a local HTTP server that always returns `500`
- run:

```bash
python3 scripts/inspect-hosted-state.py \
  --database-url sqlite:///... \
  --limit 5 \
  --max-warning-jobs 0 \
  --alert-webhook-url http://127.0.0.1:<port>/notify \
  --alert-fallback-file /tmp/latest-alert.json \
  --json
```

and expect:

- exit status `2`
- returned JSON contains:
  - `notification.delivered: false`
  - `notification.fallback.written: true`
- fallback file exists
- fallback file JSON contains:
  - `alerts` with `warning_jobs`
  - `notification.delivered: false`

Also assert:

- a successful webhook run with the same fallback path does **not** create the fallback file
- `scripts/render-hosted-systemd.py` renders an inspect service containing:
  - `--alert-fallback-file /var/lib/infinitas/alerts/latest-inspect-alert.json`

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-alert-fallback-files.py
```

Expected: FAIL because `inspect-hosted-state.py` and `render-hosted-systemd.py` do not support fallback files yet.

**Step 3: Commit**

```bash
git add scripts/test-hosted-alert-fallback-files.py
git commit -m "test: add hosted alert fallback coverage"
```

### Task 2: Implement optional fallback file writes

**Files:**
- Modify: `scripts/inspect-hosted-state.py`
- Modify: `scripts/render-hosted-systemd.py`
- Modify: `scripts/test-hosted-alert-fallback-files.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`

**Step 1: Add inspect fallback support**

Add:

- `--alert-fallback-file`

Behavior:

- only consider fallback writing when alerts exist
- if webhook delivery failed, or no webhook URL was configured, write the latest alert summary JSON to the fallback file
- create parent directories as needed
- write atomically via a temp file + rename
- record fallback metadata under `notification.fallback`:
  - `attempted`
  - `written`
  - `path`
  - optional `error`

**Step 2: Extend inspect service rendering**

Add:

- `--inspect-alert-fallback-file`

When configured, render the inspect service with:

- `--alert-fallback-file <path>`

**Step 3: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-alert-fallback-files.py
```

Expected: PASS.

**Step 4: Update docs**

Document:

- how to configure a stable fallback file path
- that fallback writes occur only for alerting runs when delivery cannot rely solely on the webhook channel
- that the fallback file contains the same alert summary JSON returned by the inspect script

**Step 5: Run adjacent regression checks**

Run:

```bash
python3 scripts/test-hosted-alert-webhooks.py
python3 scripts/test-hosted-warning-observability.py
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
git add scripts/inspect-hosted-state.py scripts/render-hosted-systemd.py scripts/test-hosted-alert-fallback-files.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted alert fallback files"
```

### Task 3: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-alert-fallback-files.py
python scripts/test-hosted-alert-webhooks.py
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
git add docs/plans/2026-03-14-hosted-alert-fallback-files.md scripts/test-hosted-alert-fallback-files.py scripts/inspect-hosted-state.py scripts/render-hosted-systemd.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted alert fallback files"
```
