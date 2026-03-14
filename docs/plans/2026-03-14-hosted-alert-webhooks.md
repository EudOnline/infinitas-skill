# Hosted Alert Webhooks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the next hosted-ops notification slice so scheduled inspection alerts can proactively deliver their summary to an operator webhook endpoint.

**Architecture:** Keep this slice small and optional. Extend `scripts/inspect-hosted-state.py` with one webhook delivery argument that POSTs the existing alert summary JSON only when alerts are present. Record delivery status back into the JSON summary so operators can distinguish “alert generated” from “alert delivered”. Then extend `scripts/render-hosted-systemd.py` to wire an optional webhook URL into the generated inspect service, so scheduled runs can notify an external endpoint without changing the core hosted worker flow.

**Tech Stack:** Python 3.11+, stdlib (`argparse`, `json`, `urllib.request`, `http.server`, `threading`), existing SQLAlchemy-based inspection script, existing `systemd` bundle renderer, script-style regression tests.

---

### Task 1: Add failing webhook coverage

**Files:**
- Create: `scripts/test-hosted-alert-webhooks.py`
- Reference: `scripts/test-hosted-ops-alerting.py`
- Reference: `scripts/test-hosted-warning-observability.py`
- Reference: `scripts/test-server-ops.py`

**Step 1: Write the failing test**

Create `scripts/test-hosted-alert-webhooks.py` with scenarios that:

- create a temp hosted SQLite DB containing:
  - 1 completed publish job with `WARNING:` in the job log
  - 1 published submission
- start a local HTTP capture server
- run:

```bash
python3 scripts/inspect-hosted-state.py \
  --database-url sqlite:///... \
  --limit 5 \
  --max-warning-jobs 0 \
  --alert-webhook-url http://127.0.0.1:<port>/notify \
  --json
```

and expect:

- exit status `2`
- returned JSON contains `ok: false`
- returned JSON contains `notification.delivered: true`
- capture server receives exactly one POST
- posted payload contains `alerts` with `warning_jobs`

Then run the same script with a permissive threshold and expect:

- exit status `0`
- no additional webhook delivery

Also assert `scripts/render-hosted-systemd.py` can render an inspect service containing:

- `--alert-webhook-url <url>`

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-hosted-alert-webhooks.py
```

Expected: FAIL because `inspect-hosted-state.py` and `render-hosted-systemd.py` do not support alert webhooks yet.

**Step 3: Commit**

```bash
git add scripts/test-hosted-alert-webhooks.py
git commit -m "test: add hosted alert webhook coverage"
```

### Task 2: Implement optional alert webhook delivery

**Files:**
- Modify: `scripts/inspect-hosted-state.py`
- Modify: `scripts/render-hosted-systemd.py`
- Modify: `scripts/test-hosted-alert-webhooks.py`
- Modify: `docs/ops/server-deployment.md`
- Modify: `README.md`

**Step 1: Add inspect webhook support**

Add:

- `--alert-webhook-url`

Behavior:

- only attempt delivery when alerts are present and the webhook URL is provided
- POST the full summary JSON to the webhook endpoint
- record `notification` metadata in the summary:
  - `attempted`
  - `delivered`
  - `url`
  - either `status_code` or `error`
- keep existing alert exit semantics:
  - alert runs still exit `2`
  - calm runs still exit `0`

**Step 2: Extend inspect service rendering**

Add:

- `--inspect-alert-webhook-url`

When configured, render the inspect service with:

- `--alert-webhook-url <url>`

**Step 3: Re-run the focused test**

Run:

```bash
python3 scripts/test-hosted-alert-webhooks.py
```

Expected: PASS.

**Step 4: Update docs**

Document:

- how to pass an alert webhook URL to inspection runs
- that webhook delivery only happens when alerts exist
- that the inspect JSON summary records delivery status

**Step 5: Run adjacent regression checks**

Run:

```bash
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
git add scripts/inspect-hosted-state.py scripts/render-hosted-systemd.py scripts/test-hosted-alert-webhooks.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted alert webhooks"
```

### Task 3: Final verification

**Files:**
- Modify: none expected

**Step 1: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
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
git add docs/plans/2026-03-14-hosted-alert-webhooks.md scripts/test-hosted-alert-webhooks.py scripts/inspect-hosted-state.py scripts/render-hosted-systemd.py docs/ops/server-deployment.md README.md
git commit -m "feat: add hosted alert webhooks"
```
