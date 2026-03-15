# Break-Glass Exceptions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add time-bounded, justified break-glass exception records that can temporarily bypass selected promotion or release blockers while clearly recording when they were used.

**Architecture:** Introduce a shared `exception_policy` domain plus a small loader library so exception records are validated, time-checked, and matched consistently. Wire that shared matcher into promotion and release readiness checks by attaching stable rule ids to blocking conditions, then surface applied exception usage in JSON and debug trace output without breaking existing text-mode behavior.

**Tech Stack:** Python 3.11 CLI scripts, JSON policy/config files, policy-pack loading, script-style regression tests in `scripts/test-*.py`, and Markdown docs.

---

## Preconditions

- Work in a dedicated worktree.
- Use `@superpowers:test-driven-development` for each behavior change.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep break-glass additive: existing promotion and release checks should still fail exactly as before unless a valid active exception record matches.
- Keep exception targeting narrow in 11-04: exact skill names or qualified names only, no wildcards.

## Scope decisions

- Recommended approach: add a shared `exception_policy` domain with exact-skill targeting and stable blocking rule ids.
- Rejected approach: inline exception records into `promotion_policy` or `signing`, because that would duplicate model logic and make later audit export harder.
- Rejected approach: target human-readable error strings, because that would make exception matching brittle and translation-unfriendly.
- Initial exception fields should stay small:
  - `id`
  - `scope`
  - `skills`
  - `rules`
  - `approved_by`
  - `approved_by_teams`
  - `approved_at`
  - `justification`
  - `expires_at`
- Initial scopes in 11-04:
  - `promotion`
  - `release`
- Initial recording surfaces in 11-04:
  - `policy_trace.exceptions`
  - top-level `exception_usage` in JSON outputs for promotion and release

### Task 1: Add failing coverage for promotion and release break-glass behavior

**Files:**
- Create: `scripts/test-break-glass-exceptions.py`
- Reference: `scripts/check-promotion-policy.py`
- Reference: `scripts/check-release-state.py`
- Reference: `scripts/release_lib.py`
- Reference: `scripts/test-policy-evaluation-traces.py`

**Step 1: Write the failing test**

Create `scripts/test-break-glass-exceptions.py` with focused scenarios that:

- copy the repository into a temp directory
- add `policy/exception-policy.json` with one active future-dated promotion exception
- verify a promotion check that would normally fail for missing required reviewer coverage now passes when the matching exception is present
- verify an expired promotion exception is ignored
- add one active future-dated release exception for a dirty worktree
- verify `check-release-state.py <skill> --mode preflight --json` passes when only the dirty-worktree rule is waived by a matching exception
- verify JSON output includes:
  - `exception_usage`
  - `policy_trace.exceptions`
  - exception `justification`
  - exception `expires_at`

Use assertion shapes like:

```python
payload = json.loads(run([sys.executable, str(repo / 'scripts' / 'check-release-state.py'), skill_name, '--mode', 'preflight', '--json'], cwd=repo).stdout)
usage = payload.get('exception_usage') or []
if not any(item.get('id') == 'dirty-worktree-waiver' for item in usage):
    fail(f'expected dirty-worktree exception usage, got {usage!r}')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-break-glass-exceptions.py
```

Expected: FAIL because no exception policy domain or exception-aware evaluation exists yet.

**Step 3: Commit**

```bash
git add scripts/test-break-glass-exceptions.py
git commit -m "test: add break-glass exception coverage"
```

### Task 2: Add a shared `exception_policy` domain and loader

**Files:**
- Create: `schemas/exception-policy.schema.json`
- Create: `policy/exception-policy.json`
- Create: `scripts/exception_policy_lib.py`
- Modify: `schemas/policy-pack.schema.json`
- Modify: `scripts/policy_pack_lib.py`
- Modify: `scripts/check-policy-packs.py`
- Modify: `scripts/test-policy-pack-loading.py`

**Step 1: Extend pack loading coverage with a failing assertion**

Update `scripts/test-policy-pack-loading.py` so it asserts `load_policy_domain_resolution(repo, 'exception_policy')` works and merges pack data plus a repository-local exception override.

**Step 2: Run the focused loader test to verify it fails**

Run:

```bash
python3 scripts/test-policy-pack-loading.py
```

Expected: FAIL because `exception_policy` is not a supported domain yet.

**Step 3: Implement the minimal exception loader**

Add:

- `schemas/exception-policy.schema.json`
- `policy/exception-policy.json`
- `scripts/exception_policy_lib.py`

Include helpers like:

- `load_exception_policy(root)`
- `match_active_exceptions(scope, skill_identity, blocking_rule_ids, root)`
- `expand_exception_approvers(record, team_policy)`

Validation should enforce:

- non-empty `id`
- valid `scope`
- non-empty `rules`
- non-empty `justification`
- parseable `approved_at` / `expires_at`
- at least one approver via `approved_by` or `approved_by_teams`

**Step 4: Re-run focused tests**

Run:

```bash
python3 scripts/test-policy-pack-loading.py
python3 scripts/check-policy-packs.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add schemas/exception-policy.schema.json policy/exception-policy.json scripts/exception_policy_lib.py schemas/policy-pack.schema.json scripts/policy_pack_lib.py scripts/check-policy-packs.py scripts/test-policy-pack-loading.py
git commit -m "feat: add exception policy loading"
```

### Task 3: Wire break-glass exceptions into promotion checks

**Files:**
- Modify: `scripts/check-promotion-policy.py`
- Modify: `scripts/policy_trace_lib.py`
- Modify: `scripts/test-break-glass-exceptions.py`
- Modify: `scripts/test-policy-evaluation-traces.py`

**Step 1: Add failing promotion trace expectations**

Extend the new exception test and `scripts/test-policy-evaluation-traces.py` so they assert:

- applied exceptions appear in `policy_trace.exceptions`
- `check-promotion-policy.py --json` returns `exception_usage`
- expired exceptions do not suppress blocking rules

**Step 2: Run the focused tests to verify they fail**

Run:

```bash
python3 scripts/test-break-glass-exceptions.py
python3 scripts/test-policy-evaluation-traces.py
```

Expected: FAIL because promotion checks do not yet attach stable rule ids or apply exception records.

**Step 3: Implement minimal promotion exception handling**

Update `scripts/check-promotion-policy.py` so:

- each blocking condition gets a stable `id`
- promotion checks call the shared exception matcher with scope `promotion`
- matched rules are waived only while the exception remains active
- JSON output includes `exception_usage`
- text output remains unchanged unless `--debug-policy` is requested
- `policy_trace` shows applied exceptions distinctly from ordinary reasons

**Step 4: Re-run focused tests**

Run:

```bash
python3 scripts/test-break-glass-exceptions.py
python3 scripts/test-policy-evaluation-traces.py
python3 scripts/test-review-governance.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/check-promotion-policy.py scripts/policy_trace_lib.py scripts/test-break-glass-exceptions.py scripts/test-policy-evaluation-traces.py
git commit -m "feat: add promotion break-glass exceptions"
```

### Task 4: Wire break-glass exceptions into release readiness

**Files:**
- Modify: `scripts/release_lib.py`
- Modify: `scripts/check-release-state.py`
- Modify: `scripts/test-break-glass-exceptions.py`
- Modify: `scripts/test-release-invariants.py`

**Step 1: Add failing release exception assertions**

Extend the new exception test and `scripts/test-release-invariants.py` so they assert:

- a valid release exception can waive a dirty-worktree preflight blocker
- expired exceptions are ignored
- release JSON output includes `exception_usage`
- release `policy_trace.exceptions` records justification and expiration

**Step 2: Run the focused tests to verify they fail**

Run:

```bash
python3 scripts/test-break-glass-exceptions.py
python3 scripts/test-release-invariants.py
```

Expected: FAIL because release readiness does not yet apply exception records.

**Step 3: Implement minimal release exception handling**

Update `scripts/release_lib.py` so:

- release blocking conditions get stable ids
- exception matching runs with scope `release`
- matched blockers are removed from the final error list
- `policy_trace` and returned state include `exception_usage`

Keep initial 11-04 scope narrow:

- exact skill name / qualified name matching only
- no catalog export yet
- no exception use persisted into release provenance yet

**Step 4: Re-run focused tests**

Run:

```bash
python3 scripts/test-break-glass-exceptions.py
python3 scripts/test-release-invariants.py
python3 scripts/test-policy-evaluation-traces.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/release_lib.py scripts/check-release-state.py scripts/test-break-glass-exceptions.py scripts/test-release-invariants.py
git commit -m "feat: add release break-glass exceptions"
```

### Task 5: Document exception records and run final 11-04 verification

**Files:**
- Modify: `README.md`
- Modify: `docs/policy-packs.md`
- Modify: `docs/promotion-policy.md`
- Modify: `docs/release-checklist.md`
- Modify: `scripts/test-policy-trace-docs.py`
- Modify: `scripts/check-all.sh`

**Step 1: Add docs regression coverage**

Extend `scripts/test-policy-trace-docs.py` so it asserts docs mention:

- `policy/exception-policy.json`
- `justification`
- `expires_at`
- break-glass exception usage in debug traces

**Step 2: Update docs and test entrypoints**

Document:

- how to declare exception records
- how to time-bound them
- how they target exact skills
- how applied exceptions appear in JSON and `--debug-policy` traces

If `scripts/test-break-glass-exceptions.py` is not already covered by `scripts/check-all.sh`, add it.

**Step 3: Run focused verification**

Run:

```bash
python3 scripts/test-break-glass-exceptions.py
python3 scripts/test-policy-pack-loading.py
python3 scripts/check-policy-packs.py
python3 scripts/test-policy-evaluation-traces.py
python3 scripts/test-review-governance.py
python3 scripts/test-release-invariants.py
python3 scripts/test-policy-trace-docs.py
```

Expected: PASS.

**Step 4: Run touched compatibility regressions**

Run:

```bash
python3 scripts/test-team-governance-scopes.py
python3 scripts/test-ci-attestation-policy.py
python3 scripts/test-hosted-registry-source.py
```

Expected: PASS.

**Step 5: Run full repository verification**

Run:

```bash
scripts/check-all.sh
```

Expected: PASS, except the existing hosted E2E dependency skip remains acceptable if optional hosted-stack packages are absent.

**Step 6: Inspect final branch state**

Run:

```bash
git status --short
git log --oneline -8
```

Expected:

- only intended 11-04 and planning-sync files changed
- commits are easy to review by task

**Step 7: Decide branch completion flow**

After verification, use `@superpowers:finishing-a-development-branch` to choose whether to merge locally, push a PR, keep the branch, or discard it.
