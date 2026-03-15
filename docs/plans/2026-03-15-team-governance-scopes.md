# Team Governance Scopes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a shared team-governance model that can back namespace ownership and delegated review scopes without breaking existing actor-based policy files.

**Architecture:** Introduce a new additive `team_policy` domain plus a small loader library so team membership is resolved in one place and reused by both namespace-policy and promotion-policy evaluation. Extend publisher authorization and reviewer-group resolution to accept team references, then thread the resolved team context into existing policy traces and JSON debug outputs.

**Tech Stack:** Python 3.11 CLI scripts, JSON schema files, policy-pack loading, script-style regression tests in `scripts/test-*.py`, and Markdown docs.

---

## Preconditions

- Work in a dedicated worktree.
- Use `@superpowers:test-driven-development` for each behavior change.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Preserve current direct actor lists so existing namespace and promotion policy files remain valid.
- Keep team resolution additive: team-backed scopes should expand into existing authorization and quorum logic, not replace it.

## Scope decisions

- Recommended approach: add a shared `team_policy` domain and reuse it from namespace and promotion policy evaluation.
- Rejected approach: duplicate team definitions inside both `namespace_policy` and `promotion_policy`, because that would create drift and weaken future auditability.
- Rejected approach: make teams the only valid way to express owners or reviewers, because 11-03 must stay backward-compatible with current single-maintainer repositories.
- Initial team policy fields should stay small:
  - `teams`
  - `members`
  - `delegates`
  - `description`
- Namespace-policy publisher entries should support additive team-backed scopes:
  - `owner_teams`
  - `maintainer_teams`
  - `authorized_signer_teams`
  - `authorized_releaser_teams`
- Promotion-policy review groups should support additive team references:
  - `teams`

### Task 1: Add failing coverage for team-backed namespace and review scopes

**Files:**
- Create: `scripts/test-team-governance-scopes.py`
- Reference: `scripts/test-review-governance.py`
- Reference: `scripts/test-namespace-identity.py`
- Reference: `scripts/check-promotion-policy.py`
- Reference: `scripts/validate-registry.py`

**Step 1: Write the failing test**

Create `scripts/test-team-governance-scopes.py` with focused scenarios that:

- copy the repository into a temp directory
- add `policy/team-policy.json` with teams such as `platform-admins` and `security-review`
- rewrite `policy/namespace-policy.json` so a publisher is authorized through `owner_teams` / `maintainer_teams`
- rewrite `policy/promotion-policy.json` so a review group resolves members through `teams`
- assert namespace validation accepts a skill whose owner/maintainer is authorized through a configured team
- assert promotion quorum can pass when the approving reviewer is allowed only through a configured team-backed group
- assert a negative case still fails when neither direct actors nor team membership authorize the claim
- assert JSON outputs include the delegated context:
  - `validate-registry.py --json` returns `validation_errors` on failure
  - `check-promotion-policy.py --json` returns `policy_trace` with blocking reasons on failure

Use assertion shapes like:

```python
payload = json.loads(run([sys.executable, str(repo / 'scripts' / 'validate-registry.py'), '--json', str(skill_dir)], cwd=repo, expect=1).stdout)
errors = payload.get('validation_errors') or []
entry = next((item for item in errors if item.get('skill_path') == 'skills/active/team-fixture'), None)
if not entry:
    fail(f'missing validation entry for delegated-team failure: {errors!r}')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-team-governance-scopes.py
```

Expected: FAIL because no shared team policy domain or team-backed authorization resolution exists yet.

**Step 3: Commit**

```bash
git add scripts/test-team-governance-scopes.py
git commit -m "test: add team governance scope coverage"
```

### Task 2: Add a shared `team_policy` domain and loader

**Files:**
- Create: `schemas/team-policy.schema.json`
- Create: `policy/team-policy.json`
- Create: `scripts/team_policy_lib.py`
- Modify: `schemas/policy-pack.schema.json`
- Modify: `scripts/policy_pack_lib.py`
- Modify: `scripts/test-policy-pack-loading.py`

**Step 1: Extend policy-pack coverage with a failing loader assertion**

Update `scripts/test-policy-pack-loading.py` so it asserts the policy-pack loader can resolve `team_policy` from packs plus a repository-local override.

Use assertion shapes like:

```python
resolution = load_policy_domain_resolution(repo, 'team_policy')
effective = resolution.get('effective') or {}
if 'teams' not in effective:
    fail(f"expected team_policy resolution to expose teams, got {effective!r}")
```

**Step 2: Run the focused loader test to verify it fails**

Run:

```bash
python3 scripts/test-policy-pack-loading.py
```

Expected: FAIL because `team_policy` is not a supported domain yet.

**Step 3: Implement the minimal shared team loader**

Add:

- `schemas/team-policy.schema.json`
- repository-local `policy/team-policy.json`
- `scripts/team_policy_lib.py` with helpers like:
  - `load_team_policy(root)`
  - `resolve_team(name, policy)`
  - `expand_team_refs(refs, policy)`

Keep the model additive:

- teams remain optional
- direct actor lists still work without teams
- `delegates` expand into resolved actor lists but should stay traceable

**Step 4: Re-run focused tests**

Run:

```bash
python3 scripts/test-policy-pack-loading.py
python3 scripts/test-check-policy-packs.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add schemas/team-policy.schema.json policy/team-policy.json scripts/team_policy_lib.py schemas/policy-pack.schema.json scripts/policy_pack_lib.py scripts/test-policy-pack-loading.py
git commit -m "feat: add shared team policy loading"
```

### Task 3: Extend namespace policy to authorize publishers through teams

**Files:**
- Modify: `schemas/namespace-policy.schema.json`
- Modify: `policy/namespace-policy.json`
- Modify: `scripts/skill_identity_lib.py`
- Modify: `scripts/validate-registry.py`
- Modify: `scripts/release_lib.py`
- Modify: `scripts/test-team-governance-scopes.py`
- Modify: `scripts/test-namespace-identity.py`

**Step 1: Add failing namespace assertions**

Extend the new test and `scripts/test-namespace-identity.py` so they assert:

- publisher `owners` / `maintainers` may be authorized through `owner_teams` / `maintainer_teams`
- `authorized_signers` / `authorized_releasers` may be expanded from team-backed fields
- `namespace_policy` traces explain whether authorization came from direct actors or delegated teams

**Step 2: Run the focused namespace tests to verify they fail**

Run:

```bash
python3 scripts/test-team-governance-scopes.py
python3 scripts/test-namespace-identity.py
```

Expected: FAIL because namespace evaluation does not yet expand team-backed scopes.

**Step 3: Implement minimal namespace-team resolution**

Update namespace policy validation and reporting so publisher entries may define:

- `owner_teams`
- `maintainer_teams`
- `authorized_signer_teams`
- `authorized_releaser_teams`

Resolved behavior should:

- merge direct actor lists with expanded team membership
- keep unauthorized claims actionable
- expose resolved team names in `namespace_policy_report`
- preserve current fallback behavior for repositories that define no teams

**Step 4: Re-run focused tests**

Run:

```bash
python3 scripts/test-team-governance-scopes.py
python3 scripts/test-namespace-identity.py
python3 scripts/test-release-invariants.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add schemas/namespace-policy.schema.json policy/namespace-policy.json scripts/skill_identity_lib.py scripts/validate-registry.py scripts/release_lib.py scripts/test-team-governance-scopes.py scripts/test-namespace-identity.py
git commit -m "feat: add team-backed namespace authorization"
```

### Task 4: Extend promotion review groups to resolve team-backed scopes

**Files:**
- Modify: `schemas/promotion-policy.schema.json`
- Modify: `policy/promotion-policy.json`
- Modify: `scripts/review_lib.py`
- Modify: `scripts/check-promotion-policy.py`
- Modify: `scripts/test-team-governance-scopes.py`
- Modify: `scripts/test-review-governance.py`

**Step 1: Add failing review-group coverage**

Extend the new team-governance test and `scripts/test-review-governance.py` so they assert:

- `reviews.groups.<name>` may contain `teams` in addition to `members`
- quorum/group coverage counts approvals from team-resolved reviewers
- failing traces mention missing delegated group coverage when no authorized team member approved

**Step 2: Run the focused review tests to verify they fail**

Run:

```bash
python3 scripts/test-team-governance-scopes.py
python3 scripts/test-review-governance.py
```

Expected: FAIL because reviewer groups do not yet expand team refs.

**Step 3: Implement minimal delegated review scope resolution**

Update promotion policy validation and review evaluation so:

- groups may specify `members`, `teams`, and `description`
- resolved reviewer maps merge direct members plus expanded team membership
- computed review outputs retain group names while optionally recording which team supplied a reviewer
- `check-promotion-policy.py --json` / `--debug-policy` remains additive and surfaces delegated group context in `policy_trace`

**Step 4: Re-run focused tests**

Run:

```bash
python3 scripts/test-team-governance-scopes.py
python3 scripts/test-review-governance.py
python3 scripts/test-policy-evaluation-traces.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add schemas/promotion-policy.schema.json policy/promotion-policy.json scripts/review_lib.py scripts/check-promotion-policy.py scripts/test-team-governance-scopes.py scripts/test-review-governance.py
git commit -m "feat: add team-backed review scopes"
```

### Task 5: Document team governance and run final 11-03 verification

**Files:**
- Modify: `README.md`
- Modify: `docs/policy-packs.md`
- Modify: `docs/review-workflow.md`
- Modify: `scripts/check-all.sh`
- Modify: `scripts/test-policy-trace-docs.py`

**Step 1: Add docs regression coverage**

Extend `scripts/test-policy-trace-docs.py` so it asserts docs mention:

- `policy/team-policy.json`
- team-backed publisher authorization
- review groups with `teams`
- delegated policy traces

**Step 2: Update docs and test entrypoints**

Document:

- how to declare shared teams
- how namespace policy delegates ownership to teams
- how promotion policy review groups delegate to teams
- how `--json` / `--debug-policy` outputs explain delegated decisions

If `scripts/test-team-governance-scopes.py` is not already covered by `scripts/check-all.sh`, add it.

**Step 3: Run focused verification**

Run:

```bash
python3 scripts/test-team-governance-scopes.py
python3 scripts/test-policy-pack-loading.py
python3 scripts/test-check-policy-packs.py
python3 scripts/test-namespace-identity.py
python3 scripts/test-review-governance.py
python3 scripts/test-policy-evaluation-traces.py
python3 scripts/test-policy-trace-docs.py
```

Expected: PASS.

**Step 4: Run touched compatibility regressions**

Run:

```bash
python3 scripts/test-release-invariants.py
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

- only intended 11-03 and planning-sync files changed
- commits are easy to review by task

**Step 7: Decide branch completion flow**

After verification, use `@superpowers:finishing-a-development-branch` to choose whether to merge locally, push a PR, keep the branch, or discard it.
