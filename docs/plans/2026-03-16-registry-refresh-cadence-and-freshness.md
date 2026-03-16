# Registry Refresh Cadence And Freshness Policy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let maintainers define registry refresh cadence and stale-cache policy, persist refresh state for cached registries, and surface or enforce freshness checks during sync and resolution.

**Architecture:** Extend registry source policy with an explicit `refresh_policy` block and record per-registry refresh state in a cache-local JSON file after successful syncs. Reuse that persisted state to power a new freshness-status command and to warn or fail when sync or resolution attempts rely on stale remote registry caches beyond configured policy.

**Tech Stack:** Existing Bash sync helpers, Python 3.11 registry policy libraries, JSON schema validation, cache-local state files under `.cache/registries/`, and Markdown operator documentation.

---

### Task 1: Define refresh-policy schema and validation with a failing test

**Files:**
- Create: `scripts/test-registry-refresh-policy.py`
- Modify: `schemas/registry-sources.schema.json`
- Modify: `scripts/registry_source_lib.py`
- Modify: `scripts/check-registry-sources.py`
- Modify: `config/registry-sources.json`
- Modify: `policy/packs/baseline.json`

**Step 1: Write the failing test**

Create `scripts/test-registry-refresh-policy.py` with scenarios that validate:

- a remote git registry may declare:

```json
"refresh_policy": {
  "interval_hours": 24,
  "max_cache_age_hours": 72,
  "stale_policy": "warn"
}
```

- `interval_hours` and `max_cache_age_hours` must be positive integers
- `max_cache_age_hours` cannot be less than `interval_hours`
- `stale_policy` accepts only `ignore`, `warn`, or `fail`
- `local-only` registries such as `self` may omit `refresh_policy` without failing

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-registry-refresh-policy.py
```

Expected: FAIL because `refresh_policy` is not defined or validated yet.

**Step 3: Implement the minimal schema and validation**

Update the schema and registry policy helpers so remote registries support `refresh_policy`, and validation enforces the integer and enum rules above while keeping current `git`, `local`, and `http` behavior intact.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-registry-refresh-policy.py
python3 scripts/check-registry-sources.py
```

Expected: PASS.

### Task 2: Persist refresh state and expose operator-facing freshness status

**Files:**
- Create: `scripts/registry_refresh_state_lib.py`
- Create: `scripts/registry-refresh-status.py`
- Modify: `scripts/sync-registry-source.sh`
- Modify: `scripts/test-registry-refresh-policy.py`

**Step 1: Extend the failing test**

Add scenarios that:

- sync a cached remote registry fixture
- assert a state file is written under `.cache/registries/_state/<registry>.json`
- assert the state file records:
  - `registry`
  - `kind`
  - `refreshed_at`
  - `source_commit`
  - `source_ref` or `source_tag`
  - `cache_path`
- assert `python3 scripts/registry-refresh-status.py <registry> --json` prints freshness info based on that state file

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-registry-refresh-policy.py
```

Expected: FAIL because no refresh-state library or status command exists yet.

**Step 3: Implement minimal refresh-state recording**

Add a small state helper library and update `scripts/sync-registry-source.sh` so successful remote syncs persist refresh metadata. Implement `scripts/registry-refresh-status.py` to read that state plus current policy and report:

- freshness age
- configured refresh interval
- configured max cache age
- derived freshness state such as `fresh`, `stale-warning`, or `stale-fail`

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-registry-refresh-policy.py
python3 scripts/registry-refresh-status.py self --json
```

Expected: PASS for the fixture scenario, and the status command prints a machine-readable response for local inspection.

### Task 3: Enforce stale-cache policy in resolver and sync flows

**Files:**
- Modify: `scripts/registry_source_lib.py`
- Modify: `scripts/resolve-skill-source.py`
- Modify: `scripts/sync-registry-source.sh`
- Modify: `scripts/test-registry-refresh-policy.py`
- Modify: `docs/multi-registry.md`
- Create: `docs/registry-refresh-policy.md`

**Step 1: Extend the failing test**

Add scenarios where:

- a remote registry state file is older than `max_cache_age_hours`
- `stale_policy: warn` still allows resolution but emits freshness warnings
- `stale_policy: fail` blocks resolution with an actionable error
- syncing a remote registry refreshes the state and clears the stale error

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-registry-refresh-policy.py
```

Expected: FAIL because resolution currently ignores cache freshness entirely.

**Step 3: Implement the minimal enforcement**

Update registry helpers and resolver logic so remote registries compute a freshness decision from policy plus persisted state. Keep the first pass additive:

- warn-mode keeps the registry eligible but exposes the stale reason
- fail-mode blocks that registry with a deterministic error
- `sync-registry-source.sh` refreshes the state after success so policy can recover automatically

**Step 4: Document operator workflow**

Document:

- how to configure `refresh_policy`
- where refresh state is stored
- how to inspect registry freshness
- what `warn` versus `fail` means in practice

**Step 5: Re-run focused verification**

Run:

```bash
python3 scripts/test-registry-refresh-policy.py
python3 scripts/check-registry-sources.py
```

Expected: PASS.

### Task 4: Run full verification and capture the phase-1 start commit

**Files:**
- Modify: any files changed above

**Step 1: Run targeted checks**

Run:

```bash
python3 scripts/test-registry-refresh-policy.py
python3 scripts/registry-refresh-status.py self --json
```

Expected: PASS.

**Step 2: Run full verification**

Run:

```bash
./scripts/check-all.sh
```

Expected: PASS, with the existing hosted-registry e2e environment skip if the Python extras remain unavailable.

**Step 3: Commit**

Run:

```bash
git add schemas/registry-sources.schema.json scripts/registry_source_lib.py scripts/check-registry-sources.py scripts/registry_refresh_state_lib.py scripts/registry-refresh-status.py scripts/sync-registry-source.sh scripts/resolve-skill-source.py scripts/test-registry-refresh-policy.py config/registry-sources.json policy/packs/baseline.json docs/multi-registry.md docs/registry-refresh-policy.md
git commit -m "feat: add registry refresh cadence policy"
```
