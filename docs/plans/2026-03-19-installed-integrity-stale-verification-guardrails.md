# Installed Integrity Stale Verification Guardrails Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent overwrite-style local mutation commands from relying silently on stale installed-integrity results by adding policy-governed freshness guardrails and explicit refresh guidance.

**Architecture:** Reuse v18's manifest-driven installed-integrity freshness state as the source of truth for how old the last local verification is. Extend the repo-managed install-integrity policy with a `stale_policy` contract, add one shared helper that converts target-local freshness into `ignore`, `warn`, or `fail` mutation decisions, then thread that decision into read-only update surfaces and overwrite-style commands without changing immutable release verification or introducing any background refresh service.

**Tech Stack:** Existing Bash and Python 3.11 CLI tooling, JSON schema validation, `config/install-integrity-policy.json`, `.infinitas-skill-install-manifest.json`, `scripts/*installed*`, update wrappers, and Markdown operator/AI docs.

---

### Task 1: Define stale-policy schema and failing advisory contract

**Files:**
- Modify: `config/install-integrity-policy.json`
- Modify: `schemas/install-integrity-policy.schema.json`
- Create: `scripts/test-installed-integrity-stale-guardrails.py`
- Modify: `scripts/test-skill-update.py`
- Modify: `scripts/test-explain-install.py`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/ai/discovery.md`

**Step 1: Write the failing tests**

Create `scripts/test-installed-integrity-stale-guardrails.py` with scenarios that:

- validate `freshness.stale_policy` accepts only `ignore`, `warn`, or `fail`
- assert the default normalized install-integrity policy uses:

```json
{
  "freshness": {
    "stale_after_hours": 168,
    "stale_policy": "warn"
  }
}
```

- assert a stale-but-clean installed entry produces a shared freshness-gate decision that:
  - allows silently when policy is `ignore`
  - allows with actionable warning when policy is `warn`
  - blocks when policy is `fail`
- assert `never-verified` entries keep the current additive behavior for now instead of being reclassified as a stale-policy block

Extend `scripts/test-skill-update.py` so `scripts/check-skill-update.sh` must expose additive freshness fields such as:

- `freshness_state`
- `checked_age_seconds`
- `last_checked_at`
- `recommended_action`
- `freshness_policy`
- `freshness_warning`

For a stale-but-clean install, assert:

- `freshness_state = stale`
- `recommended_action = refresh`
- `freshness_policy = warn`
- `freshness_warning` tells the operator to run `python3 scripts/report-installed-integrity.py <target-dir> --refresh`
- `next_step` points at refresh before suggesting upgrade

Extend `scripts/test-explain-install.py` so `scripts/upgrade-skill.sh --mode confirm`:

- includes freshness-aware `policy_reasons` and `next_actions` when the installed copy is stale
- exits with a stable JSON failure such as `error_code = stale-installed-integrity` when policy is `fail`

**Step 2: Run the focused tests to verify they fail**

Run:

```bash
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
```

Expected: FAIL because install-integrity policy has no stale-policy contract and update surfaces do not yet expose or explain freshness guardrails.

**Step 3: Define the stale-policy contract**

Extend the install-integrity policy with one additive freshness control:

```json
{
  "schema_version": 1,
  "freshness": {
    "stale_after_hours": 168,
    "stale_policy": "warn"
  },
  "history": {
    "max_inline_events": 20
  }
}
```

Define the additive advisory surface so read-only update flows can expose:

- `freshness_state`: still `fresh`, `stale`, or `never-verified`
- `freshness_policy`: configured stale-policy mode for stale installed copies
- `freshness_warning`: actionable string or `null`
- `error_code: stale-installed-integrity` for blocked confirm or mutation flows

Keep this task scoped to stale-but-clean installs. Do not change drift behavior, immutable release verification, or the meaning of `unknown`.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
```

Expected: PASS.

### Task 2: Implement shared freshness-gate helpers and read-only update surfaces

**Files:**
- Modify: `scripts/install_integrity_policy_lib.py`
- Modify: `scripts/installed_integrity_lib.py`
- Modify: `scripts/check-skill-update.sh`
- Modify: `scripts/upgrade-skill.sh`
- Modify: `scripts/explain_install_lib.py`
- Modify: `scripts/check-all.sh`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/ai/discovery.md`

**Step 1: Extend tests and check-all expectations**

Add assertions that:

- the shared helper returns one normalized freshness gate decision object instead of ad hoc shell-only logic
- `check-skill-update.sh` reuses the same freshness fields already emitted by `report-installed-integrity.py`
- `upgrade-skill.sh --mode confirm` stays non-mutating but no longer pretends a blocked stale install is an executable plan
- the new focused guardrail test runs from `scripts/check-all.sh`

**Step 2: Run focused tests to verify they fail**

Run:

```bash
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
```

Expected: FAIL because there is no shared stale-policy evaluator and read-only update flows do not yet reuse freshness metadata.

**Step 3: Implement the shared freshness gate**

Update installed-integrity helpers so they:

- load and validate `freshness.stale_policy` through the existing shared policy library
- expose one helper, for example:

```python
decision = evaluate_installed_freshness_gate(item, policy=policy)
```

- return additive fields such as:

```python
{
    "freshness_state": "stale",
    "freshness_policy": "warn",
    "blocking": False,
    "warning": "run python3 scripts/report-installed-integrity.py <target-dir> --refresh before overwriting local files"
}
```

- keep `never-verified` additive for now instead of silently upgrading it into a new block state
- let `check-skill-update.sh` and `upgrade-skill.sh --mode confirm` surface freshness guidance without scraping human-readable text

Add the new focused guardrail test to `scripts/check-all.sh`.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
```

Expected: PASS.

### Task 3: Define failing mutation-guardrail coverage for stale installed copies

**Files:**
- Modify: `scripts/test-installed-skill-integrity.py`
- Modify: `scripts/test-skill-update.py`
- Modify: `scripts/test-distribution-install.py`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/compatibility-contract.md`

**Step 1: Write the failing guardrail tests**

Extend the release-fixture mutation tests so they:

- install one clean fixture, then backdate `last_checked_at` until the install is stale while keeping `integrity.state = verified`
- set policy `stale_policy = warn` and assert:
  - `scripts/sync-skill.sh`
  - `scripts/switch-installed-skill.sh`
  - `scripts/rollback-installed-skill.sh`
  - `scripts/upgrade-skill.sh`
  still complete, but emit an actionable freshness warning that points at `report-installed-integrity.py --refresh`
- set policy `stale_policy = fail` and assert the same commands refuse to overwrite files until the target is refreshed
- run `python3 scripts/report-installed-integrity.py <target-dir> --refresh --json` and assert the block clears afterward
- assert `--force` bypasses stale-policy checks the same way it already bypasses drift guardrails

Keep explicit assertions that:

- drift still blocks first and still recommends `verify-installed-skill.py` or `repair-installed-skill.sh`
- stale policy only changes behavior for stale-but-clean installed copies

**Step 2: Run focused tests to verify they fail**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-skill-update.py
python3 scripts/test-distribution-install.py
```

Expected: FAIL because overwrite-style commands currently ignore stale freshness entirely.

**Step 3: Define the mutation contract**

Mutation guardrails should follow this order:

1. `drifted` still blocks first
2. stale-but-clean installs consult `freshness.stale_policy`
3. `warn` emits a warning and continues
4. `fail` blocks and tells the operator to run `report-installed-integrity.py --refresh`
5. `--force` bypasses stale-policy checks deliberately

Do not introduce any daemon, auto-refresh, or background verification. Refresh remains explicit and target-local.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-skill-update.py
python3 scripts/test-distribution-install.py
```

Expected: PASS.

### Task 4: Implement mutation enforcement and documentation closeout

**Files:**
- Modify: `scripts/installed_integrity_lib.py`
- Modify: `scripts/sync-skill.sh`
- Modify: `scripts/switch-installed-skill.sh`
- Modify: `scripts/rollback-installed-skill.sh`
- Modify: `scripts/upgrade-skill.sh`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/compatibility-contract.md`
- Modify: `docs/ai/discovery.md`

**Step 1: Extend docs expectations**

Add explicit operator guidance that:

- freshness guardrails are separate from immutable verification
- `report-installed-integrity.py --refresh` is the recovery path for stale-but-clean installs
- `--force` is the explicit override when an operator intentionally accepts overwrite risk
- `.infinitas-skill-installed-integrity.json` remains target-local history, not a repo-scoped enforcement database

**Step 2: Run the focused checks to verify they fail**

Run:

```bash
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-distribution-install.py
```

Expected: FAIL because overwrite-style mutation commands still lack stale-policy enforcement.

**Step 3: Implement stale-policy enforcement**

Update overwrite-style command flows so they:

- reuse the shared freshness-gate helper instead of open-coding stale checks per script
- print actionable warnings in `warn` mode
- block in `fail` mode before local files are overwritten
- preserve the existing JSON explanation style for confirm or update wrappers
- keep `repair-installed-skill.sh` and explicit refresh flows usable as recovery paths

**Step 4: Re-run verification**

Run:

```bash
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
python3 scripts/test-distribution-install.py
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-install-manifest-compat.py
./scripts/check-all.sh
```

Expected: PASS, with the same environment-sensitive hosted-registry e2e skip behavior already documented by the repository.

## Suggested Commit Sequence

1. `test: add installed integrity stale-policy coverage`
2. `feat: add freshness gate helpers for installed updates`
3. `test: add stale mutation guardrail coverage`
4. `feat: enforce stale verification guardrails in mutation flows`

## Verification Checklist

- `python3 scripts/test-installed-integrity-stale-guardrails.py`
- `python3 scripts/test-installed-skill-integrity.py`
- `python3 scripts/test-skill-update.py`
- `python3 scripts/test-explain-install.py`
- `python3 scripts/test-distribution-install.py`
- `python3 scripts/test-installed-integrity-freshness.py`
- `python3 scripts/test-installed-integrity-report.py`
- `python3 scripts/test-install-manifest-compat.py`
- `./scripts/check-all.sh`

## Handoff Notes

- Keep freshness enforcement target-local and explicit; do not introduce auto-refresh or hosted runtime state.
- Preserve the current immutable release trust contract; this plan only changes how stale local verification influences overwrite decisions.
- Keep `never-verified` additive for now unless implementation evidence shows a narrower, safer contract is necessary.
