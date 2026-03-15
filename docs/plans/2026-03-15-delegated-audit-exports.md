# Delegated Audit Exports Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend stable release audit metadata so release-state JSON and generated provenance can reconstruct delegated approvals plus break-glass override usage without introducing a separate export product yet.

**Architecture:** Reuse the existing release-state and provenance pipeline instead of inventing a new audit CLI. Enrich `collect_release_state()` with the authoritative review evaluation, delegated namespace-team context, and applied release exceptions, then persist those additive fields through `provenance_payload_lib.py` and document the resulting audit contract.

**Tech Stack:** Python 3.11 CLI scripts, JSON schemas and policy files, script-style regression tests in `scripts/test-*.py`, Git-backed release fixtures, and Markdown docs.

---

## Preconditions

- Work in this dedicated worktree: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-delegated-audit-exports`
- Use `@superpowers:test-driven-development` before each behavior change.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep 11-05 additive:
  - no new standalone audit export command yet
  - no discovery/catalog contract expansion unless a focused test proves it is required
  - preserve existing top-level `exception_usage` in release-state JSON for backward compatibility

## Scope decisions

- Recommended approach: enrich existing `check-release-state --json` and release provenance so the stable audit path is the same data flow already trusted by release tooling.
- Rejected approach: add a brand-new `audit.json` catalog or export CLI in 11-05, because that overlaps with later `FED-02` export work and would widen scope.
- Rejected approach: persist raw debug trace output into provenance verbatim, because `policy_trace` is explain/debug oriented while audit metadata should stay stable and purpose-specific.
- 11-05 should capture three audit layers:
  - review decision context:
    - `effective_review_state`
    - quorum counters
    - `latest_decisions`
    - `ignored_decisions`
    - `configured_groups`
  - delegated namespace/release authority context:
    - `delegated_teams`
    - resolved `authorized_signers`
    - resolved `authorized_releasers`
  - override context:
    - `exception_usage`
    - approvers
    - justification
    - expiration

### Task 1: Add failing release-state audit coverage

**Files:**
- Modify: `scripts/test-release-invariants.py`
- Reference: `scripts/release_lib.py`
- Reference: `scripts/review_lib.py`
- Reference: `scripts/skill_identity_lib.py`

**Step 1: Write the failing test**

Extend `scripts/test-release-invariants.py` with a scenario that:

- prepares a release fixture repo with:
  - `policy/team-policy.json`
  - team-backed `policy/namespace-policy.json`
  - team-backed `policy/promotion-policy.json`
  - one active `policy/exception-policy.json` dirty-worktree waiver
- writes an untracked dirty file
- runs:

```bash
python3 scripts/check-release-state.py release-fixture --mode preflight --json
```

- asserts the JSON now includes stable audit fields such as:
  - `review.effective_review_state`
  - `review.required_groups`
  - `review.latest_decisions`
  - `review.ignored_decisions`
  - `review.configured_groups`
  - `release.delegated_teams`
  - `release.exception_usage`

Use assertion shapes like:

```python
review = payload.get('review') or {}
groups = review.get('configured_groups') or {}
security = groups.get('security') or {}
if security.get('teams') != ['security-review']:
    fail(f'unexpected configured_groups.security.teams {security!r}')
```

**Step 2: Run the focused test to verify it fails**

Run:

```bash
python3 scripts/test-release-invariants.py
```

Expected: FAIL because `collect_release_state()` does not yet export delegated review and exception audit context.

**Step 3: Commit**

```bash
git add scripts/test-release-invariants.py
git commit -m "test: add delegated audit export coverage"
```

### Task 2: Implement audit-rich release-state JSON

**Files:**
- Modify: `scripts/release_lib.py`
- Reference: `scripts/review_lib.py`
- Reference: `scripts/exception_policy_lib.py`
- Reference: `scripts/skill_identity_lib.py`

**Step 1: Implement the minimal release-state export**

Update `scripts/release_lib.py` so `collect_release_state()`:

- uses `evaluate_review_state()` instead of only `review_audit_entries()`
- exports a richer `review` block containing:
  - `effective_review_state`
  - `approval_count`
  - `blocking_rejection_count`
  - `required_approvals`
  - `required_groups`
  - `covered_groups`
  - `missing_groups`
  - `quorum_met`
  - `review_gate_pass`
  - `latest_decisions`
  - `ignored_decisions`
  - `configured_groups`
- exports `release.delegated_teams` from `namespace_policy_report()`
- mirrors release exception usage into `release.exception_usage` while preserving the existing top-level `exception_usage`

Keep the new fields additive so older callers still find `errors`, `warnings`, `policy_trace`, and top-level `exception_usage` where they already expect them.

**Step 2: Re-run the focused test**

Run:

```bash
python3 scripts/test-release-invariants.py
```

Expected: PASS.

**Step 3: Commit**

```bash
git add scripts/release_lib.py scripts/test-release-invariants.py
git commit -m "feat: export delegated audit details in release state"
```

### Task 3: Add failing provenance audit coverage

**Files:**
- Modify: `scripts/test-attestation-verification.py`
- Reference: `scripts/generate-provenance.py`
- Reference: `scripts/provenance_payload_lib.py`
- Reference: `schemas/provenance.schema.json`

**Step 1: Write the failing test**

Extend `scripts/test-attestation-verification.py` with a scenario that:

- prepares a team-backed release fixture repo
- creates and pushes the stable tag
- adds an active dirty-worktree exception plus an untracked dirty file
- runs:

```bash
scripts/release-skill.sh release-fixture --write-provenance
```

- asserts the generated `catalog/provenance/release-fixture-1.2.3.json` includes:
  - `review.latest_decisions`
  - `review.configured_groups`
  - `release.delegated_teams`
  - `release.exception_usage`
  - exception `justification`
  - exception `approved_by` or resolved approvers

**Step 2: Run the focused provenance test to verify it fails**

Run:

```bash
python3 scripts/test-attestation-verification.py
```

Expected: FAIL because provenance currently persists only shallow reviewer and release actor fields.

**Step 3: Commit**

```bash
git add scripts/test-attestation-verification.py
git commit -m "test: add delegated provenance audit coverage"
```

### Task 4: Persist delegated audit metadata into provenance

**Files:**
- Modify: `scripts/provenance_payload_lib.py`
- Modify: `schemas/provenance.schema.json`
- Modify: `scripts/test-attestation-verification.py`

**Step 1: Implement the minimal provenance export**

Update `scripts/provenance_payload_lib.py` so `build_common_payload()` persists the new release-state audit fields into the attestation payload:

- `review` should now include the richer quorum and decision context from `collect_release_state()`
- `release` should now include:
  - `delegated_teams`
  - `exception_usage`
  - existing namespace governance fields

Update `schemas/provenance.schema.json` additively:

- allow the new nested objects and arrays
- do not make them required if doing so would invalidate already checked-in historical provenance fixtures

**Step 2: Re-run focused provenance tests**

Run:

```bash
python3 scripts/test-attestation-verification.py
python3 scripts/test-release-invariants.py
```

Expected: PASS.

**Step 3: Commit**

```bash
git add scripts/provenance_payload_lib.py schemas/provenance.schema.json scripts/test-attestation-verification.py scripts/test-release-invariants.py
git commit -m "feat: persist delegated audit metadata in provenance"
```

### Task 5: Document 11-05 and run final verification

**Files:**
- Modify: `docs/release-strategy.md`
- Modify: `docs/release-checklist.md`
- Modify: `.planning/PROJECT.md`
- Modify: `.planning/ROADMAP.md`
- Modify: `.planning/STATE.md`
- Modify: `.planning/REQUIREMENTS.md`

**Step 1: Update docs**

Document:

- that release-state JSON now includes delegated approval and exception audit context
- that generated provenance now records delegated teams plus applied exception usage
- that 11-05 intentionally stops short of a separate export product

**Step 2: Run focused verification**

Run:

```bash
python3 scripts/test-release-invariants.py
python3 scripts/test-attestation-verification.py
```

Expected: PASS.

**Step 3: Run full verification**

Run:

```bash
scripts/check-all.sh
```

Expected: PASS, with hosted e2e allowed to skip when its optional Python dependencies are unavailable.

**Step 4: Commit**

```bash
git add docs/release-strategy.md docs/release-checklist.md .planning/PROJECT.md .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md
git commit -m "docs: close out delegated audit export phase"
```
