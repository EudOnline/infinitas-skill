# AI Publish/Pull Protocol Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an AI-first publish/pull surface to `infinitas-skill` using immutable release artifacts only, with machine-readable protocol docs, a dedicated AI index, and autonomous-by-default wrappers.

**Architecture:** Keep the existing governance, release, distribution, and install pipeline as the execution core. Add a thin AI-facing contract layer on top of it: `docs/ai/*.md` for protocol, `catalog/ai-index.json` for discovery, `schemas/ai-index.schema.json` for validation, and `scripts/publish-skill.sh` / `scripts/pull-skill.sh` as stable entrypoints. Prefer extending current scripts over rewriting them.

**Tech Stack:** Bash, Python 3.11, JSON Schema draft 2020-12, Git tags, existing `release-skill.sh`, `install-skill.sh`, `build-catalog.sh`, and distribution-manifest helpers.

---

## Preconditions

- Create a dedicated worktree before implementation.
- Standardize on `Python 3.11` before running new tests or `scripts/check-all.sh`.
- Treat this as an MVP contract build:
  - support `--mode auto|confirm`
  - default to `auto`
  - allow install from immutable release artifacts only
  - do **not** add a hosted registry service
  - do **not** add automatic version bumping in the first pass; `--version` is an assertion/filter, not a mutator

## Scope decisions

- Reuse current distribution manifests instead of inventing a second package format.
- Reuse current install manifest/lock behavior instead of building a new local state format.
- Keep the AI interface to two top-level commands:
  - `scripts/publish-skill.sh`
  - `scripts/pull-skill.sh`
- Make `confirm` mode non-mutating: it prints a structured execution plan and exits without changing files.

### Task 1: Add AI protocol documents

**Files:**
- Create: `docs/ai/publish.md`
- Create: `docs/ai/pull.md`
- Modify: `README.md`

**Step 1: Write the protocol skeletons**

Create both docs with these required sections:

```md
# publish-skill Protocol

## Command
## Inputs
## Preconditions
## Ordered execution steps
## Stop conditions
## Output JSON
## Forbidden assumptions
```

`pull.md` mirrors the same structure, but substitutes install semantics for publish semantics.

**Step 2: Make the docs explicit for AI**

Write concrete rules into the docs:

```md
- Default mode is `auto`.
- `confirm` mode must not mutate repository or target directories.
- AI must never install from `skills/active` or `skills/incubating`.
- Missing manifest or attestation is a hard stop.
```

**Step 3: Link the docs from the human entrypoint**

Add a short "AI Protocol" section to `README.md` that points to `docs/ai/publish.md` and `docs/ai/pull.md` and explains that these files are the machine-facing contract.

**Step 4: Validate the docs are discoverable**

Run:

```bash
rg -n 'AI Protocol|publish-skill|pull-skill|immutable-only' README.md docs/ai
```

Expected: matches in all three files.

**Step 5: Commit**

```bash
git add README.md docs/ai/publish.md docs/ai/pull.md
git commit -m "docs: add ai publish and pull protocols"
```

### Task 2: Add the AI index schema and validator helpers

**Files:**
- Create: `schemas/ai-index.schema.json`
- Create: `scripts/ai_index_lib.py`
- Modify: `scripts/validate-registry.py`
- Test: `scripts/test-ai-index.py`

**Step 1: Write the failing test**

Create `scripts/test-ai-index.py` using the same temp-repo style as `scripts/test-distribution-install.py`. Start with assertions like:

```python
payload = json.loads((repo / 'catalog' / 'ai-index.json').read_text(encoding='utf-8'))
assert payload['install_policy']['mode'] == 'immutable-only'
assert payload['install_policy']['direct_source_install_allowed'] is False
assert 'skills' in payload
```

Also assert one negative case by corrupting `default_install_version` and expecting validation failure.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-ai-index.py
```

Expected: FAIL because `catalog/ai-index.json` and its validator do not exist yet.

**Step 3: Add the schema contract**

Create `schemas/ai-index.schema.json` with these minimum invariants:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["schema_version", "generated_at", "registry", "install_policy", "skills"]
}
```

Include required nested fields for:
- `install_policy.mode = immutable-only`
- `direct_source_install_allowed = false`
- version entries containing `manifest_path`, `bundle_path`, `bundle_sha256`, `attestation_path`, `published_at`, `installable`

**Step 4: Add a reusable Python helper**

Create `scripts/ai_index_lib.py` with functions shaped like:

```python
def build_ai_index(*, root: Path, catalog_entries: list, distribution_entries: list) -> dict:
    ...


def validate_ai_index_payload(payload: dict) -> list[str]:
    ...
```

Validation must enforce semantic invariants that are awkward to express in pure schema form:
- `default_install_version` exists in `available_versions`
- every `available_version` exists in `versions`
- every installable version includes manifest, digest, and attestation references
- all generated paths are repo-relative

**Step 5: Wire the validator into registry validation**

Update `scripts/validate-registry.py` so it validates `catalog/ai-index.json` if present and prints `FAIL:` messages consistent with the rest of the repo.

**Step 6: Re-run the test**

Run:

```bash
python3 scripts/test-ai-index.py
```

Expected: PASS.

**Step 7: Commit**

```bash
git add schemas/ai-index.schema.json scripts/ai_index_lib.py scripts/validate-registry.py scripts/test-ai-index.py
git commit -m "feat: add ai index schema and validation"
```

### Task 3: Generate `catalog/ai-index.json` from the existing catalog pipeline

**Files:**
- Modify: `scripts/build-catalog.sh`
- Modify: `scripts/check-all.sh`
- Modify: `scripts/ai_index_lib.py`
- Create: `catalog/ai-index.json`
- Test: `scripts/test-ai-index.py`

**Step 1: Extend the failing test with deterministic generation checks**

Add assertions to `scripts/test-ai-index.py` that:

```python
first = json.loads((repo / 'catalog' / 'ai-index.json').read_text(encoding='utf-8'))
run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
second = json.loads((repo / 'catalog' / 'ai-index.json').read_text(encoding='utf-8'))
assert {k: v for k, v in first.items() if k != 'generated_at'} == {k: v for k, v in second.items() if k != 'generated_at'}
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-ai-index.py
```

Expected: FAIL because `build-catalog.sh` does not emit `catalog/ai-index.json` yet.

**Step 3: Teach the catalog builder to emit the AI view**

Update `scripts/build-catalog.sh` to:
- import `build_ai_index` from `scripts/ai_index_lib.py`
- derive AI entries from the same canonical metadata used for `catalog.json`
- prefer distribution-manifest-backed versions only
- write `catalog/ai-index.json` with stable sort order and repo-relative paths only

The emitted install policy must look like:

```json
{
  "mode": "immutable-only",
  "direct_source_install_allowed": false,
  "require_attestation": true,
  "require_sha256": true
}
```

**Step 4: Include AI index in deterministic repo checks**

Update `scripts/check-all.sh` to include `catalog/ai-index.json` in the pre/post build normalization diff.

**Step 5: Run the targeted test and the builder**

Run:

```bash
python3 scripts/test-ai-index.py
scripts/build-catalog.sh
```

Expected: both commands succeed and leave `catalog/ai-index.json` up to date.

**Step 6: Commit**

```bash
git add scripts/build-catalog.sh scripts/check-all.sh scripts/ai_index_lib.py catalog/ai-index.json scripts/test-ai-index.py
git commit -m "feat: generate ai index from catalog pipeline"
```

### Task 4: Implement the AI install entrypoint

**Files:**
- Create: `scripts/pull-skill.sh`
- Modify: `README.md`
- Test: `scripts/test-ai-pull.py`

**Step 1: Write the failing end-to-end test**

Create `scripts/test-ai-pull.py` using the fixture/release approach already used in `scripts/test-distribution-install.py`.

Cover these cases:

```python
# auto mode installs from an indexed released version
result = run([str(repo / 'scripts' / 'pull-skill.sh'), 'release-test/release-fixture', str(target)], cwd=repo)
assert json.loads(result.stdout)['ok'] is True

# missing version is a hard failure
run([str(repo / 'scripts' / 'pull-skill.sh'), 'release-test/release-fixture', str(target), '--version', '9.9.9'], cwd=repo, expect=1)

# confirm mode makes no filesystem changes
before = sorted(target.glob('**/*'))
run([str(repo / 'scripts' / 'pull-skill.sh'), 'release-test/release-fixture', str(target), '--mode', 'confirm'], cwd=repo)
after = sorted(target.glob('**/*'))
assert before == after
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-ai-pull.py
```

Expected: FAIL because `scripts/pull-skill.sh` does not exist.

**Step 3: Implement the wrapper with strict AI rules**

Create `scripts/pull-skill.sh` to do this in order:
- parse `qualified-name`, `target-dir`, optional `--version`, optional `--mode`
- read `catalog/ai-index.json`
- enforce `install_policy.mode == immutable-only`
- resolve the selected version from `default_install_version` or explicit `--version`
- fail if the selected version lacks manifest/bundle/attestation refs
- in `confirm` mode: print JSON plan and exit without mutation
- in `auto` mode: call `scripts/install-skill.sh <qualified-name> <target-dir> --version <resolved>`
- emit structured JSON result after install

**Step 4: Keep JSON output stable**

The output should include at least:

```json
{
  "ok": true,
  "qualified_name": "release-test/release-fixture",
  "requested_version": null,
  "resolved_version": "1.2.4",
  "target_dir": "/tmp/.../skills",
  "state": "installed",
  "lockfile_path": "/tmp/.../.infinitas-skill-install.json"
}
```

**Step 5: Re-run the test**

Run:

```bash
python3 scripts/test-ai-pull.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/pull-skill.sh scripts/test-ai-pull.py README.md
git commit -m "feat: add ai pull entrypoint"
```

### Task 5: Implement the AI publish entrypoint

**Files:**
- Create: `scripts/publish-skill.sh`
- Modify: `README.md`
- Test: `scripts/test-ai-publish.py`

**Step 1: Write the failing end-to-end test**

Create `scripts/test-ai-publish.py` with a temporary repo fixture. Cover both `active` and `incubating` cases.

Core checks:

```python
# auto mode publishes an active skill and returns manifest paths
result = run([str(repo / 'scripts' / 'publish-skill.sh'), 'release-fixture'], cwd=repo)
payload = json.loads(result.stdout)
assert payload['ok'] is True
assert payload['state'] == 'published'
assert Path(payload['manifest_path']).exists()

# confirm mode is non-mutating
run([str(repo / 'scripts' / 'publish-skill.sh'), 'release-fixture', '--mode', 'confirm'], cwd=repo)

# incubating skill must pass active review gate before promotion/release
run([str(repo / 'scripts' / 'publish-skill.sh'), 'needs-review'], cwd=repo, expect=1)
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-ai-publish.py
```

Expected: FAIL because `scripts/publish-skill.sh` does not exist.

**Step 3: Implement the wrapper around existing governance flow**

Create `scripts/publish-skill.sh` to do this in order:
- resolve the target skill by name or path
- load `_meta.json` and verify optional `--version` matches current metadata
- if status is `incubating`, run `python3 scripts/review-status.py <skill> --as-active --require-pass`
- if incubating review passes, run `scripts/promote-skill.sh <skill>`
- run `scripts/release-skill.sh <skill> --push-tag --write-provenance`
- run `scripts/build-catalog.sh`
- print structured JSON result

In `confirm` mode, print the action plan only and exit without changing the repo.

**Step 4: Keep publish semantics narrow for MVP**

Do **not** mutate version numbers in this script. If `--version` is passed, use it only to assert the targeted published version.

**Step 5: Re-run the test**

Run:

```bash
python3 scripts/test-ai-publish.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/publish-skill.sh scripts/test-ai-publish.py README.md
git commit -m "feat: add ai publish entrypoint"
```

### Task 6: Integrate the new checks into the full validation loop

**Files:**
- Modify: `scripts/check-all.sh`
- Modify: `.github/workflows/validate.yml` (only if needed)
- Test: `scripts/test-ai-index.py`
- Test: `scripts/test-ai-pull.py`
- Test: `scripts/test-ai-publish.py`

**Step 1: Add the new tests to the local gate**

Update `scripts/check-all.sh` so it runs:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-publish.py
```

Place them after existing distribution-related tests so fixtures can reuse the same mental model.

**Step 2: Ensure CI inherits the new coverage**

If `.github/workflows/validate.yml` already shells to `scripts/check-all.sh`, leave it unchanged. Only touch the workflow if an explicit Python 3.11 note or step is still missing after implementation.

**Step 3: Run the focused tests first**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-publish.py
```

Expected: PASS for all three.

**Step 4: Run the full repo check**

Run:

```bash
scripts/check-all.sh
```

Expected: `OK: full registry check passed`.

**Step 5: Commit**

```bash
git add scripts/check-all.sh .github/workflows/validate.yml
git commit -m "test: cover ai publish and pull workflows"
```

### Task 7: Finalize human-facing docs and rollout notes

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-03-09-ai-skill-registry-design.md`
- Create: `docs/plans/2026-03-09-ai-protocol-rollout-notes.md` (optional)

**Step 1: Update quick start and registry model docs**

Add the AI-facing commands to `README.md`:

```bash
scripts/publish-skill.sh my-skill
scripts/pull-skill.sh lvxiaoer/my-skill ~/.openclaw/skills
```

Make it explicit that these are the default machine-facing commands and that installation is immutable-only.

**Step 2: Back-link implementation decisions into the design doc**

Add a short section near the bottom of `docs/plans/2026-03-09-ai-skill-registry-design.md` noting any intentional MVP constraints:
- `--version` is assert-only in v1
- `confirm` mode is non-mutating plan output
- AI install path is strictly manifest-backed

**Step 3: Optional rollout note**

If useful, create `docs/plans/2026-03-09-ai-protocol-rollout-notes.md` listing:
- required Python version
- how to regenerate `catalog/ai-index.json`
- how to test publish/pull locally
- what is intentionally out of scope

**Step 4: Sanity check the final surface**

Run:

```bash
rg -n 'publish-skill.sh|pull-skill.sh|ai-index.json|immutable-only' README.md docs/ai docs/plans
```

Expected: all protocol surfaces are documented consistently.

**Step 5: Commit**

```bash
git add README.md docs/plans/2026-03-09-ai-skill-registry-design.md docs/plans/2026-03-09-ai-protocol-rollout-notes.md
git commit -m "docs: finalize ai registry rollout guidance"
```

## Implementation order summary

1. docs contract
2. schema + validator
3. catalog generation
4. pull wrapper
5. publish wrapper
6. full validation integration
7. rollout docs

## Verification checklist

Before claiming completion, verify all of the following:

- `catalog/ai-index.json` is generated and committed
- `schemas/ai-index.schema.json` exists and matches emitted payload shape
- `scripts/pull-skill.sh --mode confirm` does not mutate disk
- `scripts/publish-skill.sh --mode confirm` does not mutate the repo
- `scripts/pull-skill.sh` refuses missing or non-indexed versions
- `scripts/publish-skill.sh` refuses incubating skills that fail active review requirements
- `scripts/check-all.sh` passes on Python 3.11

## Out of scope for this plan

- hosted registry service
- automatic semantic version bumping
- changing the underlying bundle format
- public marketplace/discovery UX
- cross-repo package mirrors beyond current registry-source support
