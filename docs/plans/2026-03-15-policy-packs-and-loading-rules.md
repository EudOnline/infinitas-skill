# Policy Packs And Loading Rules Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reusable policy packs and deterministic repository-level loading and override rules so governance, release, install, and distribution policy can be composed instead of scattered across one-off loaders.

**Architecture:** Introduce JSON-only policy packs under `policy/packs/` plus a repository selector file at `policy/policy-packs.json`. Add a small Python loader that resolves active packs in order, deep-merges supported policy domains, and applies repository-local files such as `policy/promotion-policy.json` and `config/signing.json` as the final override layer so current CLIs stay compatible during migration.

**Tech Stack:** Python 3.11 helper libraries, existing Bash entrypoints, JSON schema validation, script-style regression tests in `scripts/test-*.py`, and Markdown docs.

---

## Preconditions

- Work in a dedicated worktree.
- Use `@superpowers:test-driven-development` for every behavior change.
- Use `@superpowers:verification-before-completion` before each completion claim or commit.
- Keep existing file paths compatible in this phase; policy packs are additive and repository-local files remain the final override layer.
- Keep policy packs repo-local and JSON-only; do not add remote fetching, executable hooks, or dynamic plugin loading in 11-01.

## Scope decisions

- Recommended approach: ordered JSON policy packs plus final repository-local overrides.
- Rejected approach: a monolithic new top-level policy file, because it would force an all-at-once migration across current tooling.
- Rejected approach: executable or plugin-style policy evaluators, because 11-01 needs deterministic structure and loading rules, not a new runtime.
- Merge rules for 11-01:
  - objects deep-merge
  - arrays replace
  - scalars replace
  - later packs win over earlier packs
  - repository-local files win over packs
- Explainable decision traces are explicitly deferred to 11-02; 11-01 stops at structure, loading, and compatibility-safe integration.

### Task 1: Add failing coverage for policy-pack loading and precedence

**Files:**
- Create: `scripts/test-policy-pack-loading.py`
- Reference: `scripts/review_lib.py`
- Reference: `scripts/skill_identity_lib.py`
- Reference: `scripts/attestation_lib.py`
- Reference: `scripts/registry_source_lib.py`

**Step 1: Write the failing test**

Create `scripts/test-policy-pack-loading.py` with focused scenarios that:

- create a temporary repo with:
  - `policy/policy-packs.json`
  - `policy/packs/baseline.json`
  - `policy/packs/dual-attestation.json`
  - repository-local overrides in `policy/promotion-policy.json` and `config/signing.json`
- assert active packs are applied in declared order
- assert repository-local files override pack-derived values
- assert unsupported policy domains or missing pack names fail with clear errors
- assert the effective payload returned to existing loaders does not change their domain shape

Use assertion shapes like:

```python
effective_signing = load_effective_policy_domain(repo, 'signing')
policy = ((effective_signing.get('attestation') or {}).get('policy') or {})
if policy.get('release_trust_mode') != 'ci':
    fail(f"expected repo-local signing override to win, got {policy.get('release_trust_mode')!r}")

effective_promotion = load_effective_policy_domain(repo, 'promotion_policy')
reviews = effective_promotion.get('reviews') or {}
if reviews.get('allow_owner_when_no_distinct_reviewer') is not True:
    fail('expected policy pack to populate promotion-policy review fallback')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-policy-pack-loading.py
```

Expected: FAIL because policy-pack loaders and schemas do not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-policy-pack-loading.py
git commit -m "test: add policy-pack loading coverage"
```

### Task 2: Define policy-pack schemas and validation entrypoints

**Files:**
- Create: `schemas/policy-pack.schema.json`
- Create: `schemas/policy-pack-selection.schema.json`
- Create: `scripts/check-policy-packs.py`
- Create: `scripts/test-check-policy-packs.py`
- Create: `policy/policy-packs.json`
- Create: `policy/packs/baseline.json`

**Step 1: Write the failing validation test**

Create `scripts/test-check-policy-packs.py` with scenarios that:

- accept a valid `policy/policy-packs.json` containing ordered `active_packs`
- accept a valid pack file with supported domains:
  - `promotion_policy`
  - `namespace_policy`
  - `signing`
  - `registry_sources`
- reject:
  - duplicate active pack names
  - unknown pack files
  - unknown policy domains
  - malformed JSON objects

Use assertion shapes like:

```python
result = run(['python3', 'scripts/check-policy-packs.py'], cwd=repo, check=False)
if result.returncode == 0:
    fail('expected invalid policy-pack config to fail validation')
if 'unknown policy domain' not in (result.stdout + result.stderr):
    fail('expected policy-pack validation error to mention unknown policy domain')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-check-policy-packs.py
```

Expected: FAIL because policy-pack schemas and checker do not exist yet.

**Step 3: Implement the schemas and checker**

Add `schemas/policy-pack.schema.json` and `schemas/policy-pack-selection.schema.json` so:

- pack files are versioned JSON objects
- pack files can only define the supported policy domains
- the repository selector file declares ordered `active_packs`
- selector-level metadata can include a short description and compatibility version

Add `scripts/check-policy-packs.py` so it:

- validates `policy/policy-packs.json`
- validates every referenced pack file
- prints actionable errors without mutating the repository

Ship a minimal `policy/packs/baseline.json` plus `policy/policy-packs.json` so the repo has one concrete example to build on.

**Step 4: Re-run the focused tests**

Run:

```bash
python3 scripts/test-check-policy-packs.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add schemas/policy-pack.schema.json schemas/policy-pack-selection.schema.json scripts/check-policy-packs.py scripts/test-check-policy-packs.py policy/policy-packs.json policy/packs/baseline.json
git commit -m "feat: add policy-pack schemas and validation"
```

### Task 3: Implement the shared policy-pack loader and wire existing policy consumers through it

**Files:**
- Create: `scripts/policy_pack_lib.py`
- Modify: `scripts/review_lib.py`
- Modify: `scripts/skill_identity_lib.py`
- Modify: `scripts/registry_source_lib.py`
- Modify: `scripts/attestation_lib.py`
- Modify: `scripts/test-policy-pack-loading.py`

**Step 1: Implement the shared loader**

Create `scripts/policy_pack_lib.py` with helpers like:

```python
SUPPORTED_DOMAINS = {'promotion_policy', 'namespace_policy', 'signing', 'registry_sources'}

def load_policy_pack_selection(root: Path) -> dict:
    ...

def load_policy_pack(root: Path, name: str) -> dict:
    ...

def load_effective_policy_domain(root: Path, domain: str) -> dict:
    ...
```

Implementation rules:

- load active packs in the listed order
- deep-merge objects
- replace arrays and scalars
- apply repository-local file overrides last
- keep error messages specific to the domain or pack name that failed

**Step 2: Route existing loaders through the new helper**

Update:

- `scripts/review_lib.py` to resolve effective `promotion_policy`
- `scripts/skill_identity_lib.py` to resolve effective `namespace_policy`
- `scripts/registry_source_lib.py` to resolve effective `registry_sources`
- `scripts/attestation_lib.py` to resolve effective `signing`

Keep the public return shape unchanged so current callers and tests do not need format migrations.

**Step 3: Re-run the focused tests**

Run:

```bash
python3 scripts/test-policy-pack-loading.py
python3 scripts/test-check-policy-packs.py
```

Expected: PASS.

**Step 4: Add compatibility regressions**

Run the existing domain tests that cover the touched loaders:

```bash
python3 scripts/test-review-governance.py
python3 scripts/test-namespace-identity.py
python3 scripts/test-ci-attestation-policy.py
python3 scripts/test-hosted-registry-source.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/policy_pack_lib.py scripts/review_lib.py scripts/skill_identity_lib.py scripts/registry_source_lib.py scripts/attestation_lib.py scripts/test-policy-pack-loading.py
git commit -m "feat: load effective policy through ordered policy packs"
```

### Task 4: Document policy-pack usage and wire validation into the standard checks

**Files:**
- Create: `docs/policy-packs.md`
- Modify: `docs/promotion-policy.md`
- Modify: `docs/signing-bootstrap.md`
- Modify: `docs/multi-registry.md`
- Modify: `README.md`
- Modify: `scripts/check-all.sh`
- Create: `scripts/test-policy-pack-docs.py`

**Step 1: Write the failing docs and integration test**

Create `scripts/test-policy-pack-docs.py` with assertions that:

- `README.md` mentions `policy/policy-packs.json`
- `docs/policy-packs.md` documents:
  - pack file location
  - supported policy domains
  - precedence order
  - repository-local overrides winning last
- `scripts/check-all.sh` runs `python3 scripts/check-policy-packs.py`

Use assertion shapes like:

```python
assert_contains(ROOT / 'README.md', 'policy/policy-packs.json')
assert_contains(ROOT / 'docs' / 'policy-packs.md', 'repository-local files win over packs')
assert_contains(ROOT / 'scripts' / 'check-all.sh', 'python3 scripts/check-policy-packs.py')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-policy-pack-docs.py
```

Expected: FAIL because policy-pack docs and `check-all` wiring do not exist yet.

**Step 3: Implement the docs and standard-check integration**

Document:

- how to declare active packs
- which domains are currently supported
- how precedence works
- what is intentionally deferred to 11-02

Update `scripts/check-all.sh` so policy-pack validation runs near the other configuration and policy checks.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-policy-pack-docs.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add docs/policy-packs.md docs/promotion-policy.md docs/signing-bootstrap.md docs/multi-registry.md README.md scripts/check-all.sh scripts/test-policy-pack-docs.py
git commit -m "docs: add policy-pack usage and validation guidance"
```

### Task 5: Run final 11-01 verification

**Files:**
- No new files expected

**Step 1: Run the focused policy-pack checks**

Run:

```bash
python3 scripts/test-policy-pack-loading.py
python3 scripts/test-check-policy-packs.py
python3 scripts/test-policy-pack-docs.py
```

Expected: PASS.

**Step 2: Run the touched compatibility regressions**

Run:

```bash
python3 scripts/test-review-governance.py
python3 scripts/test-namespace-identity.py
python3 scripts/test-ci-attestation-policy.py
python3 scripts/test-hosted-registry-source.py
```

Expected: PASS.

**Step 3: Run the full repository verification**

Run:

```bash
scripts/check-all.sh
```

Expected: PASS, except the existing hosted-E2E dependency skip remains acceptable if the Python environment still lacks optional hosted-stack packages.

**Step 4: Inspect final worktree state**

Run:

```bash
git status --short
git log --oneline -6
```

Expected:

- only the intended 11-01 files changed
- the commit stack is clean and easy to review by task

**Step 5: Decide branch completion flow**

After verification, use `@superpowers:finishing-a-development-branch` to decide whether to keep the task commits as-is, squash for merge, or open a review branch.
