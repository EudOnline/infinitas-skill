# Never-Verified Policy and Project Closeout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining post-v19 trust and completion gaps by giving `never-verified` installed copies an explicit policy contract, making hosted-registry verification fully exercised in CI, and defining the final project closeout gates.

**Architecture:** Reuse the installed-integrity decision layer added in v18 and v19, but stop treating `never-verified` as a purely descriptive edge case. Add one shared mutation-readiness evaluator that normalizes drift, stale, and never-verified behavior for read-only and mutation flows, keep recovery explicit and target-local, and finish by making the full supported verification matrix deterministic in CI plus documented for operators.

**Tech Stack:** Existing Bash and Python 3.11 CLI tooling, JSON schema validation, install-manifest and installed-integrity helpers, `scripts/check-all.sh`, GitHub Actions, and Markdown operator/AI docs.

---

### Task 1: Define `never_verified_policy` and the failing readiness contract

**Files:**
- Modify: `config/install-integrity-policy.json`
- Modify: `schemas/install-integrity-policy.schema.json`
- Create: `scripts/test-installed-integrity-never-verified-guardrails.py`
- Modify: `scripts/test-install-manifest-compat.py`
- Modify: `scripts/test-skill-update.py`
- Modify: `scripts/test-explain-install.py`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/ai/discovery.md`

**Step 1: Write the failing tests**

Create `scripts/test-installed-integrity-never-verified-guardrails.py` with scenarios that:

- validate `freshness.never_verified_policy` accepts only `ignore`, `warn`, or `fail`
- assert the default normalized install-integrity policy now includes:

```json
{
  "freshness": {
    "stale_after_hours": 168,
    "stale_policy": "warn",
    "never_verified_policy": "warn"
  }
}
```

- assert a legacy install entry with no `last_checked_at` and no usable verification timestamp:
  - stays additive when policy is `ignore`
  - emits actionable readiness warning when policy is `warn`
  - blocks overwrite-style mutation when policy is `fail`
- assert the readiness helper distinguishes `never-verified` from `stale` instead of silently folding both into one state

Extend `scripts/test-install-manifest-compat.py` so older manifests still normalize safely while any new readiness fields remain deterministic and additive.

Extend `scripts/test-skill-update.py` and `scripts/test-explain-install.py` so read-only update surfaces must expose readiness guidance for `never-verified` installs, including the correct recovery path.

**Step 2: Run tests to confirm the red state**

Run:

```bash
python3 scripts/test-installed-integrity-never-verified-guardrails.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
```

Expected: FAIL because no `never_verified_policy` or readiness contract exists yet.

**Step 3: Define the policy contract**

Extend install-integrity policy with:

```json
{
  "freshness": {
    "stale_after_hours": 168,
    "stale_policy": "warn",
    "never_verified_policy": "warn"
  }
}
```

Define one additive readiness contract for legacy installs:

- `freshness_state: "never-verified"`
- `mutation_readiness: "ready" | "warning" | "blocked"`
- `mutation_policy: "ignore" | "warn" | "fail" | null`
- `mutation_reason_code: "never-verified-installed-integrity" | null`
- `recovery_action: "refresh" | "repair" | "reinstall" | "backfill-distribution-manifest" | "none"`

Keep this contract target-local and additive. Do not change immutable release verification rules.

**Step 4: Re-run focused verification**

Run the same commands from Step 2.

Expected: PASS.

### Task 2: Add a shared mutation-readiness helper and thread it into read-only surfaces

**Files:**
- Modify: `scripts/install_integrity_policy_lib.py`
- Modify: `scripts/installed_integrity_lib.py`
- Modify: `scripts/report-installed-integrity.py`
- Modify: `scripts/check-skill-update.sh`
- Modify: `scripts/upgrade-skill.sh`
- Modify: `scripts/explain_install_lib.py`
- Modify: `scripts/test-installed-integrity-report.py`
- Modify: `scripts/test-installed-integrity-freshness.py`

**Step 1: Extend tests to define the helper contract**

Add assertions that one helper, for example:

```python
decision = evaluate_installed_mutation_readiness(item, policy=policy)
```

returns normalized fields for:

- `drifted`
- `stale`
- `never-verified`
- legacy compatibility-only installs

Also assert:

- `report-installed-integrity.py --json` exposes the same readiness fields as `check-skill-update.sh`
- `upgrade-skill.sh --mode confirm` reuses those readiness fields instead of recomputing ad hoc shell-only logic

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3 scripts/test-installed-integrity-never-verified-guardrails.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
```

Expected: FAIL because no shared readiness evaluator exists yet.

**Step 3: Implement the minimal helper**

Update installed-integrity helpers so they:

- load `stale_policy` and `never_verified_policy` through the shared policy library
- keep drift precedence explicit
- map `never-verified` into normalized `mutation_readiness`, `mutation_policy`, `mutation_reason_code`, and `recovery_action`
- prefer `refresh` only when the install has enough immutable source metadata to support explicit refresh
- prefer `repair` or `reinstall` when refresh cannot establish trust locally

Thread those fields through:

- `report-installed-integrity.py`
- `check-skill-update.sh`
- `upgrade-skill.sh --mode confirm`
- explanation builders

**Step 4: Re-run focused verification**

Run the same commands from Step 2.

Expected: PASS.

### Task 3: Define failing mutation coverage for `never-verified` installs

**Files:**
- Modify: `scripts/test-installed-skill-integrity.py`
- Modify: `scripts/test-distribution-install.py`
- Modify: `scripts/test-skill-update.py`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/compatibility-contract.md`

**Step 1: Write the failing tests**

Extend mutation-path tests so they build legacy-style install targets that stay `freshness_state = never-verified`, then assert:

- policy `warn`:
  - `scripts/sync-skill.sh`
  - `scripts/switch-installed-skill.sh`
  - `scripts/rollback-installed-skill.sh`
  - `scripts/upgrade-skill.sh`
  surface explicit readiness warning and recommended recovery before overwrite
- policy `fail`:
  - the same commands refuse mutation until the operator explicitly repairs, refreshes, or reinstalls according to the surfaced recovery path
- `--force` continues to bypass the new guardrail deliberately
- `drifted` still blocks first
- `stale` still blocks or warns before `never-verified` when both are not applicable to the same target

**Step 2: Run focused tests to verify failure**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-distribution-install.py
python3 scripts/test-skill-update.py
```

Expected: FAIL because mutation commands do not yet honor `never_verified_policy`.

**Step 3: Define the mutation contract**

Mutation guardrails should follow this order:

1. `drifted` blocks first
2. `stale` consults `freshness.stale_policy`
3. `never-verified` consults `freshness.never_verified_policy`
4. explicit recovery guidance depends on immutable-source capability
5. `--force` bypasses the local guardrails deliberately

Do not add background refresh, daemon state, or hosted runtime coordination.

**Step 4: Re-run focused verification**

Run the same commands from Step 2.

Expected: PASS.

### Task 4: Enforce `never-verified` guardrails in overwrite-style mutation flows

**Files:**
- Modify: `scripts/sync-skill.sh`
- Modify: `scripts/switch-installed-skill.sh`
- Modify: `scripts/rollback-installed-skill.sh`
- Modify: `scripts/upgrade-skill.sh`
- Modify: `scripts/installed_integrity_lib.py`
- Modify: `scripts/report-installed-integrity.py`

**Step 1: Extend guard expectations**

Make the tests lock in that:

- shell flows do not open-code policy-specific branches per script
- the same readiness helper drives warnings and failures everywhere
- recovery strings remain machine-consumable and deterministic

**Step 2: Run the failing mutation tests**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-distribution-install.py
python3 scripts/test-skill-update.py
```

Expected: FAIL because overwrite commands still only understand drift plus stale.

**Step 3: Implement the guardrails**

Update overwrite-style commands so they:

- reuse the shared readiness helper
- emit warning text in `warn` mode
- block in `fail` mode before mutation begins
- preserve JSON explanation behavior for confirm or wrapper flows
- keep `repair-installed-skill.sh`, `report-installed-integrity.py --refresh`, and reinstall guidance usable as explicit recovery paths

**Step 4: Re-run focused verification**

Run the same commands from Step 2.

Expected: PASS.

### Task 5: Make hosted-registry end-to-end verification deterministic in CI

**Files:**
- Create: `requirements-hosted-e2e.txt`
- Create: `scripts/bootstrap-hosted-e2e-env.sh`
- Modify: `.github/workflows/validate.yml`
- Modify: `scripts/check-all.sh`
- Modify: `docs/federation-operations.md`
- Modify: `docs/ai/discovery.md`

**Step 1: Write the failing verification expectations**

Add or extend tests so CI expectations now require:

- hosted e2e dependencies are explicitly installable from one repo-managed manifest
- GitHub validation installs those dependencies before `scripts/check-all.sh`
- local docs explain one bootstrap path instead of leaving the hosted e2e dependency set implicit

Prefer extending existing regression coverage over inventing a new large test harness.

**Step 2: Run the checks to confirm the current gap**

Run:

```bash
./scripts/check-all.sh
```

Expected: PASS locally with hosted e2e skipped unless dependencies are missing, which documents the current gap that CI still needs to close explicitly.

**Step 3: Implement deterministic CI coverage**

Add:

- one small dependency manifest for hosted e2e requirements
- one local bootstrap helper for operators
- one workflow step in `.github/workflows/validate.yml` that installs those dependencies before `scripts/check-all.sh`

Keep local default behavior compatibility-safe: routine local runs may still skip hosted e2e when the environment is intentionally minimal, but CI should no longer do so.

**Step 4: Re-run verification**

Run:

```bash
./scripts/check-all.sh
```

Expected: PASS locally, with documentation and CI configuration now making the full hosted e2e path deterministic.

### Task 6: Project closeout docs, roadmap sync, and final merge gates

**Files:**
- Modify: `.planning/PROJECT.md`
- Modify: `.planning/REQUIREMENTS.md`
- Modify: `.planning/ROADMAP.md`
- Modify: `.planning/STATE.md`
- Create: `docs/project-closeout.md`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/compatibility-contract.md`

**Step 1: Write the failing closeout expectations**

Add assertions or doc checks that:

- planning docs mark v19 complete and v20 as the final closeout milestone
- operator docs explain the final decision matrix:
  - drifted
  - stale
  - never-verified
  - explicit `--force`
- one closeout doc lists the final branch-merge and verification gates for considering the project complete

**Step 2: Run targeted doc checks**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
```

Expected: FAIL until the docs and plan metadata mention the final readiness matrix and closeout surfaces.

**Step 3: Complete the closeout docs**

Update planning and operator docs so they:

- mark v19 as complete
- define v20 as the final planned closeout milestone
- document the recovery decision matrix and CI expectations
- define the final merge gate checklist

**Step 4: Run final verification**

Run:

```bash
python3 scripts/test-installed-integrity-never-verified-guardrails.py
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
python3 scripts/test-distribution-install.py
./scripts/check-all.sh
```

Expected: PASS, with hosted-registry e2e exercised deterministically in CI and local skip behavior remaining explicit when the environment is intentionally minimal.

## Suggested Commit Sequence

1. `test: add never-verified policy coverage`
2. `feat: add shared mutation readiness contract`
3. `test: add never-verified mutation guardrail coverage`
4. `feat: enforce never-verified mutation guardrails`
5. `chore: make hosted e2e verification deterministic in ci`
6. `docs: add project closeout and final readiness guidance`

## Verification Checklist

- `python3 scripts/test-installed-integrity-never-verified-guardrails.py`
- `python3 scripts/test-installed-integrity-stale-guardrails.py`
- `python3 scripts/test-installed-integrity-report.py`
- `python3 scripts/test-installed-integrity-freshness.py`
- `python3 scripts/test-install-manifest-compat.py`
- `python3 scripts/test-installed-skill-integrity.py`
- `python3 scripts/test-skill-update.py`
- `python3 scripts/test-explain-install.py`
- `python3 scripts/test-distribution-install.py`
- `./scripts/check-all.sh`

## Handoff Notes

- Keep the project Git-native and private-first. Do not expand into hosted runtime state or background agents.
- Prefer one shared readiness evaluator over more shell-only special cases.
- Preserve compatibility for legacy manifests; new policy should be additive by default.
- Treat this milestone as closeout work, not the start of a new platform expansion.
