# CI-native Attestations And Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add CI-generated provenance and verification policy so stable release trust can come from both repository-managed SSH attestations and CI-native attestations.

**Architecture:** Keep the current SSH-signed local release path as the existing trust anchor, then add a second attestation path produced by GitHub Actions and stored alongside release artifacts. Extend the attestation schema, verification CLI, and policy config so release and distribution checks can require `ssh`, `ci`, or `both` without ambiguity, while preserving current immutable manifest and provenance semantics.

**Tech Stack:** GitHub Actions, Python 3.11, existing Bash release scripts, JSON config/schema files, detached attestation sidecars in `catalog/provenance/`, existing script-style regression tests.

---

### Task 1: Add failing CI-attestation workflow coverage

**Files:**
- Create: `.github/workflows/release-attestation.yml`
- Create: `scripts/test-ci-attestation-workflow.py`
- Modify: `.github/workflows/validate.yml`
- Reference: `scripts/generate-provenance.py`
- Reference: `catalog/provenance/`

**Step 1: Write the failing test**

Create `scripts/test-ci-attestation-workflow.py` with scenarios that:

- load `.github/workflows/release-attestation.yml`
- assert the workflow:
  - runs on manual dispatch plus reusable invocation
  - sets up Python 3.11
  - rebuilds release provenance from an already-tagged immutable snapshot
  - emits a CI attestation sidecar into `catalog/provenance/`
  - records workflow identity, run URL or run id, commit SHA, ref, and artifact digest inputs
- fail if the workflow still only validates the repo and does not produce CI attestation output

Use simple YAML string assertions first, for example:

```python
workflow = (ROOT / '.github' / 'workflows' / 'release-attestation.yml').read_text(encoding='utf-8')
required = [
    'workflow_dispatch',
    'workflow_call',
    'actions/checkout@v4',
    'actions/setup-python@v5',
    'generate-provenance.py',
    'catalog/provenance',
]
for needle in required:
    if needle not in workflow:
        fail(f'missing workflow behavior: {needle}')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-ci-attestation-workflow.py
```

Expected: FAIL because `.github/workflows/release-attestation.yml` does not exist yet.

**Step 3: Add the workflow**

Create `.github/workflows/release-attestation.yml` with one job that:

- checks out the tagged source
- sets up Python 3.11
- runs `scripts/generate-provenance.py <skill> ...`
- writes a new CI-side attestation sidecar such as `catalog/provenance/<skill>-<version>.ci.json`
- records:
  - `github.repository`
  - `github.sha`
  - `github.ref`
  - `github.run_id`
  - `github.run_attempt`
  - `github.workflow`
  - bundle or manifest digest inputs
- uploads the generated CI attestation as a workflow artifact

Prefer `workflow_dispatch` inputs shaped like:

```yaml
on:
  workflow_dispatch:
    inputs:
      skill:
        required: true
      version:
        required: true
      manifest_path:
        required: true
```

**Step 4: Add a lightweight validation hook**

Extend `.github/workflows/validate.yml` so pull requests at least syntax-check the new workflow by running:

```bash
python3 scripts/test-ci-attestation-workflow.py
```

This keeps CI-attestation plumbing from silently drifting.

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-ci-attestation-workflow.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add .github/workflows/release-attestation.yml .github/workflows/validate.yml scripts/test-ci-attestation-workflow.py
git commit -m "feat: add CI attestation workflow scaffold"
```

### Task 2: Extend provenance schema for CI-native attestation payloads

**Files:**
- Modify: `schemas/provenance.schema.json`
- Modify: `scripts/generate-provenance.py`
- Create: `scripts/generate-ci-attestation.py`
- Create: `scripts/test-ci-attestation-payload.py`
- Reference: `config/signing.json`

**Step 1: Write the failing payload test**

Create `scripts/test-ci-attestation-payload.py` with scenarios that:

- generate a temporary attestation payload through `scripts/generate-ci-attestation.py`
- assert the payload keeps the current release context fields
- assert the payload adds a CI-specific section such as:
  - `attestation.format == "ci"`
  - `ci.provider == "github-actions"`
  - `ci.repository`
  - `ci.workflow`
  - `ci.run_id`
  - `ci.run_attempt`
  - `ci.ref`
  - `ci.sha`
  - `ci.trigger`
- assert the payload binds distribution-manifest and bundle digest metadata

Use a fixture assertion shape like:

```python
payload = json.loads(result.stdout)
if payload.get('attestation', {}).get('format') != 'ci':
    fail('expected CI attestation format')
ci = payload.get('ci') or {}
for key in ['provider', 'repository', 'workflow', 'run_id', 'sha', 'ref']:
    if not ci.get(key):
        fail(f'missing ci.{key}')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-ci-attestation-payload.py
```

Expected: FAIL because no CI-attestation generator or schema support exists.

**Step 3: Extend the schema**

Update `schemas/provenance.schema.json` so attestation payloads support:

- existing SSH payloads unchanged
- CI-native payloads with:
  - `attestation.format: "ci"`
  - `ci.provider`
  - `ci.repository`
  - `ci.workflow`
  - `ci.run_id`
  - `ci.run_attempt`
  - `ci.sha`
  - `ci.ref`
  - `ci.event_name`
  - `ci.url`
- a clear discriminator so verification can tell whether a payload is `ssh` or `ci`

Keep current `kind: skill-release-attestation` and release/distribution binding intact.

**Step 4: Add a dedicated CI generator**

Create `scripts/generate-ci-attestation.py` that:

- accepts the same release/distribution binding inputs as `scripts/generate-provenance.py`
- reads GitHub Actions metadata from env vars
- emits JSON to stdout
- writes no signature itself

Recommended env reads:

```python
github = {
    'provider': 'github-actions',
    'repository': os.environ['GITHUB_REPOSITORY'],
    'workflow': os.environ['GITHUB_WORKFLOW'],
    'run_id': os.environ['GITHUB_RUN_ID'],
    'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
    'sha': os.environ['GITHUB_SHA'],
    'ref': os.environ['GITHUB_REF'],
    'event_name': os.environ.get('GITHUB_EVENT_NAME'),
    'url': f"{server}/{repo}/actions/runs/{run_id}",
}
```

**Step 5: Reuse the current release context**

Refactor `scripts/generate-provenance.py` minimally so shared release-context assembly can be reused by both generators instead of duplicating dependency and distribution binding logic.

**Step 6: Re-run the focused test**

Run:

```bash
python3 scripts/test-ci-attestation-payload.py
```

Expected: PASS.

**Step 7: Commit**

```bash
git add schemas/provenance.schema.json scripts/generate-provenance.py scripts/generate-ci-attestation.py scripts/test-ci-attestation-payload.py
git commit -m "feat: add CI attestation payload format"
```

### Task 3: Extend trust policy config for `ssh`, `ci`, and `both`

**Files:**
- Modify: `config/signing.json`
- Modify: `schemas/signing.schema.json`
- Modify: `scripts/attestation_lib.py`
- Create: `scripts/test-ci-attestation-policy.py`

**Step 1: Write the failing policy test**

Create `scripts/test-ci-attestation-policy.py` with scenarios that assert policy config can require:

- `ssh` only
- `ci` only
- `both`

and that unsupported values fail validation.

Use fixture config shapes like:

```json
{
  "attestation": {
    "policy": {
      "release_trust_mode": "both",
      "require_verified_attestation_for_release_output": true,
      "require_verified_attestation_for_distribution": true
    }
  }
}
```

Also assert the loaded config returns explicit booleans or enums for:

- release-output enforcement
- distribution enforcement
- accepted attestation formats

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-ci-attestation-policy.py
```

Expected: FAIL because current config only models a single SSH-based attestation path.

**Step 3: Extend config and schema**

Update `config/signing.json` and `schemas/signing.schema.json` to support:

- `attestation.policy.release_trust_mode`
- allowed values: `ssh`, `ci`, `both`
- optional `ci` section for provider expectations such as:
  - `provider`
  - `issuer`
  - `repository`
  - `workflow`

Preserve current behavior by making `ssh` the default when the new field is omitted.

**Step 4: Load the policy in attestation helpers**

Extend `scripts/attestation_lib.py` so `load_attestation_config()` returns:

- the required trust mode
- expected CI provider metadata
- helper predicates like:
  - `requires_ssh_attestation`
  - `requires_ci_attestation`

This should be additive and not break the existing SSH verification path.

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-ci-attestation-policy.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add config/signing.json schemas/signing.schema.json scripts/attestation_lib.py scripts/test-ci-attestation-policy.py
git commit -m "feat: add CI attestation trust policy"
```

### Task 4: Add CI-native verification alongside SSH verification

**Files:**
- Modify: `scripts/verify-attestation.py`
- Create: `scripts/verify-ci-attestation.py`
- Modify: `scripts/verify-provenance.py`
- Modify: `scripts/test-attestation-verification.py`
- Create: `scripts/test-verify-ci-attestation.py`

**Step 1: Write the failing verification test**

Create `scripts/test-verify-ci-attestation.py` with scenarios that:

- verify a valid CI attestation fixture succeeds
- reject mismatched `repository`, `workflow`, or `sha`
- reject missing CI metadata when policy requires `ci` or `both`
- prove SSH-only payloads still pass through the existing path unchanged

Also extend `scripts/test-attestation-verification.py` with one mixed-mode scenario where:

- SSH verification succeeds
- CI verification succeeds
- policy `both` requires both to pass
- tampering either side causes overall verification failure

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-verify-ci-attestation.py
python3 scripts/test-attestation-verification.py
```

Expected: FAIL because no CI verifier exists and the main verifier only understands SSH payloads.

**Step 3: Implement the CI verifier**

Create `scripts/verify-ci-attestation.py` that:

- reads the attestation JSON
- validates it against the CI payload contract
- checks provider metadata against repository policy
- verifies the claimed digest, commit SHA, ref, and workflow identity
- prints machine-readable JSON with `--json`

Keep the initial verification deterministic and repository-configured; do not add network lookups in the first pass.

**Step 4: Route by format in the main verifier**

Update `scripts/verify-attestation.py` so it:

- detects `attestation.format`
- dispatches to SSH or CI verification
- when policy is `both`, verifies both required sidecars and fails if either is missing or invalid

Prefer output shaped like:

```json
{
  "verified": true,
  "formats_verified": ["ssh", "ci"],
  "policy_mode": "both"
}
```

**Step 5: Keep backward compatibility**

Update `scripts/verify-provenance.py` only if needed so older HMAC-oriented helpers clearly fail closed or forward callers to the current attestation verifier instead of silently implying the legacy path is authoritative.

**Step 6: Re-run the focused tests**

Run:

```bash
python3 scripts/test-verify-ci-attestation.py
python3 scripts/test-attestation-verification.py
```

Expected: PASS.

**Step 7: Commit**

```bash
git add scripts/verify-attestation.py scripts/verify-ci-attestation.py scripts/verify-provenance.py scripts/test-attestation-verification.py scripts/test-verify-ci-attestation.py
git commit -m "feat: verify CI attestations alongside SSH"
```

### Task 5: Enforce CI-attestation requirements in release and distribution flows

**Files:**
- Modify: `scripts/release-skill.sh`
- Modify: `scripts/verify-distribution-manifest.py`
- Modify: `scripts/generate-distribution-manifest.py`
- Create: `scripts/test-release-ci-attestation-gates.py`
- Modify: `scripts/test-distribution-install.py`

**Step 1: Write the failing gate tests**

Create `scripts/test-release-ci-attestation-gates.py` with scenarios that:

- set trust mode to `ci` and assert release output is blocked until a valid CI attestation exists
- set trust mode to `both` and assert SSH-only output is insufficient
- set trust mode to `ssh` and assert current stable release flow still passes unchanged

Also extend `scripts/test-distribution-install.py` so a distribution manifest requiring CI or mixed trust fails install when the required CI sidecar is absent.

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-release-ci-attestation-gates.py
python3 scripts/test-distribution-install.py
```

Expected: FAIL because release/distribution gates currently only understand the SSH path.

**Step 3: Bind attestation requirements into release output**

Update `scripts/release-skill.sh` so:

- `ssh` mode keeps current behavior
- `ci` mode writes release output only when a valid CI attestation sidecar is present
- `both` mode requires both sidecars before final success

Keep preview mode read-only.

**Step 4: Bind trust mode into manifests**

Update `scripts/generate-distribution-manifest.py` and `scripts/verify-distribution-manifest.py` so manifests can declare which attestation formats are required for consumers and verification checks enforce that declaration.

**Step 5: Re-run the focused tests**

Run:

```bash
python3 scripts/test-release-ci-attestation-gates.py
python3 scripts/test-distribution-install.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/release-skill.sh scripts/verify-distribution-manifest.py scripts/generate-distribution-manifest.py scripts/test-release-ci-attestation-gates.py scripts/test-distribution-install.py
git commit -m "feat: enforce CI attestation release policy"
```

### Task 6: Document offline and online verification flows

**Files:**
- Modify: `docs/ai/publish.md`
- Modify: `docs/ai/pull.md`
- Modify: `docs/release-checklist.md`
- Modify: `README.md`
- Create: `docs/ai/ci-attestation.md`

**Step 1: Write the failing doc coverage test**

Create a small regression script such as `scripts/test-ci-attestation-docs.py` that asserts docs mention:

- SSH verification flow
- CI verification flow
- mixed `both` trust mode
- offline verification expectations
- online or GitHub-linked operator checks

**Step 2: Run the doc test to verify it fails**

Run:

```bash
python3 scripts/test-ci-attestation-docs.py
```

Expected: FAIL because CI-native attestation docs do not exist yet.

**Step 3: Document the operator flows**

Update docs so they clearly separate:

- **Offline verification:** verify manifest, bundle digest, SSH attestation, and CI attestation from downloaded release files only
- **Online verification:** optionally cross-check GitHub workflow run metadata, repository, tag, and commit against the CI attestation payload
- **Compatibility mode:** how `ssh`, `ci`, and `both` interact during rollout

Include exact command examples like:

```bash
python3 scripts/verify-attestation.py catalog/provenance/my-skill-1.2.3.json --json
python3 scripts/verify-ci-attestation.py catalog/provenance/my-skill-1.2.3.ci.json --json
python3 scripts/verify-distribution-manifest.py catalog/distributions/_legacy/my-skill/1.2.3/manifest.json
```

**Step 4: Re-run the doc test**

Run:

```bash
python3 scripts/test-ci-attestation-docs.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add docs/ai/publish.md docs/ai/pull.md docs/release-checklist.md README.md docs/ai/ci-attestation.md scripts/test-ci-attestation-docs.py
git commit -m "docs: add CI attestation verification guide"
```

### Task 7: Run final verification for Phase 4

**Files:**
- Reference: `.github/workflows/release-attestation.yml`
- Reference: `scripts/test-ci-attestation-workflow.py`
- Reference: `scripts/test-ci-attestation-payload.py`
- Reference: `scripts/test-ci-attestation-policy.py`
- Reference: `scripts/test-verify-ci-attestation.py`
- Reference: `scripts/test-attestation-verification.py`
- Reference: `scripts/test-release-ci-attestation-gates.py`
- Reference: `scripts/test-distribution-install.py`
- Reference: `scripts/test-ci-attestation-docs.py`

**Step 1: Run the focused Phase 4 regression suite**

Run:

```bash
python3 scripts/test-ci-attestation-workflow.py
python3 scripts/test-ci-attestation-payload.py
python3 scripts/test-ci-attestation-policy.py
python3 scripts/test-verify-ci-attestation.py
python3 scripts/test-attestation-verification.py
python3 scripts/test-release-ci-attestation-gates.py
python3 scripts/test-distribution-install.py
python3 scripts/test-ci-attestation-docs.py
```

Expected: PASS.

**Step 2: Run the broader registry validation**

Run:

```bash
scripts/check-all.sh
```

Expected: PASS.

**Step 3: Smoke the workflow contract**

If `gh` is available and a safe test branch exists, dry-run or manually dispatch the workflow against a tagged fixture release and confirm the CI attestation artifact appears.

**Step 4: Commit any final cleanups**

```bash
git add .
git commit -m "feat: complete v10 phase 4 CI-native attestation support"
```
