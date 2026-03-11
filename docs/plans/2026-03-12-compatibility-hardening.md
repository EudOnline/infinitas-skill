# Compatibility Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden `infinitas-skill` so future repository evolution does not easily break legacy skill folders, existing install manifests, or historical installs.

**Architecture:** Treat compatibility as an explicit product surface instead of an accidental side effect of current scripts. Add versioned contracts for `_meta.json` and install manifests, centralize manifest reads/writes, provide migration commands, and lock the behavior down with compatibility regression tests. Keep the first pass additive: dual-read old + new formats, single-write the new format, and defer any hard break to a later deprecation window.

**Tech Stack:** Bash, Python 3.11, JSON Schema draft 2020-12, existing registry/install scripts, temp-repo style test fixtures, immutable distribution manifests, and current `scripts/check-all.sh` validation flow.

---

## Preconditions

- Create a dedicated worktree before implementation.
- Standardize on `Python 3.11` before adding or running new tests.
- Keep this project on a compatibility-first path for at least one deprecation window:
  - missing `schema_version` must continue to load as version `1`
  - legacy unqualified skill references must continue to resolve
  - existing install manifests without `schema_version` must continue to work
- Do not remove archived snapshot resolution in this plan.
- Do not require trusted signer bootstrapping to finish phase 1; compatibility work must run in the current local warning-only environment.

## Scope decisions

- Add explicit `schema_version` to `_meta.json` and `.infinitas-skill-install-manifest.json`.
- Treat schema-version support as **dual-read, single-write**:
  - readers accept legacy versionless payloads as `v1`
  - writers always emit the newest supported schema version for that file
- Add migration commands for both metadata and install manifests.
- Add regression tests for compatibility-sensitive flows before making behavior changes.
- Keep working-tree resolution temporarily available for developer flows in this plan; document it as non-stable and follow up later with stricter release-only semantics.

## Non-goals

- Do not build a hosted registry service.
- Do not replace the current release artifact format.
- Do not redesign `SKILL.md` runtime semantics in this pass.
- Do not require all historical skills to be rewritten by hand.

## Delivery phases

- **Week 1**
  - Task 1: document the compatibility contract
  - Task 2: add `_meta.json` schema-version support
- **Month 1**
  - Task 3: add install-manifest schema-version support
  - Task 4: ship migration commands
  - Task 5: add compatibility regression coverage to CI
- **Long-term follow-ons**
  - move install identity from bare `name` toward `identity_key` / `qualified_name`
  - make immutable release artifacts the only stable install source for non-dev flows

### Task 1: Document the compatibility contract

**Files:**
- Create: `docs/compatibility-contract.md`
- Modify: `README.md`
- Modify: `docs/metadata-schema.md`
- Modify: `docs/history-and-snapshots.md`
- Modify: `docs/compatibility-matrix.md`

**Step 1: Write the document skeleton**

Create `docs/compatibility-contract.md` with these sections:

```md
# Compatibility Contract

## Stable surfaces
## Versioned file formats
## Deprecation policy
## Dual-read / single-write rule
## Migration guarantees
## Compatibility test matrix
```

**Step 2: Make the contract explicit**

Document these guarantees in the new file:

```md
- `_meta.json` without `schema_version` is treated as schema version 1.
- `.infinitas-skill-install-manifest.json` without `schema_version` is treated as schema version 1.
- Legacy bare skill names continue to resolve unless the user opts into a stricter mode.
- Archived exact-version snapshot resolution is part of the compatibility contract.
- New writers emit the latest schema version; readers remain backward-compatible within the supported window.
```

Add a short table that labels each surface as one of:
- stable contract
- soft contract / deprecation candidate
- internal implementation detail

At minimum classify:
- `_meta.json` core identity fields
- install manifest core keys
- `scripts/install-skill.sh`, `scripts/sync-skill.sh`, `scripts/list-installed.sh`
- archived snapshot resolution semantics
- `catalog/compatibility.json`

**Step 3: Link the contract from existing docs**

Update the existing docs so the contract is discoverable:

- `README.md`: add a short “Compatibility Contract” section near the registry model / CI docs.
- `docs/metadata-schema.md`: mention `schema_version`, default-to-v1 behavior, and migration expectations.
- `docs/history-and-snapshots.md`: explicitly call out that version-locked installs and archived snapshot resolution are compatibility guarantees.
- `docs/compatibility-matrix.md`: clarify that `agent_compatible` is a runtime-compatibility declaration, not a file-format-compatibility guarantee.

**Step 4: Validate discoverability**

Run:

```bash
rg -n 'Compatibility Contract|schema_version|dual-read|deprecation|archived snapshot' README.md docs
```

Expected: matches in the new contract doc and the updated reference docs.

**Step 5: Commit**

```bash
git add README.md docs/compatibility-contract.md docs/metadata-schema.md docs/history-and-snapshots.md docs/compatibility-matrix.md
git commit -m "docs: define compatibility contract"
```

### Task 2: Add `_meta.json` schema-version support

**Files:**
- Create: `scripts/test-skill-meta-compat.py`
- Modify: `schemas/skill-meta.schema.json`
- Modify: `scripts/check-skill.sh`
- Modify: `scripts/validate-registry.py`
- Modify: `templates/basic-skill/_meta.json`
- Modify: `templates/scripted-skill/_meta.json`
- Modify: `templates/reference-heavy-skill/_meta.json`
- Modify: `docs/metadata-schema.md`

**Step 1: Write the failing compatibility test**

Create `scripts/test-skill-meta-compat.py` using the same temp-repo style as `scripts/test-distribution-install.py`. Cover these cases:

```python
legacy_meta = fixture_meta_without_schema_version()
assert validate_registry(repo_with(legacy_meta)) == 0

v1_meta = fixture_meta_with_schema_version(1)
assert validate_registry(repo_with(v1_meta)) == 0

unsupported_meta = fixture_meta_with_schema_version(999)
assert validate_registry(repo_with(unsupported_meta)) == 1
assert 'unsupported schema_version' in combined_output
```

Also verify that generated templates include `schema_version` after the implementation lands.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-skill-meta-compat.py
```

Expected: FAIL because `_meta.json` has no schema-version semantics yet.

**Step 3: Implement minimal schema-version support**

Update `schemas/skill-meta.schema.json` so it accepts:

```json
{
  "schema_version": 1
}
```

with these rules:
- `schema_version` is optional for backward compatibility
- when present it must currently equal `1`

Update `scripts/check-skill.sh` and `scripts/validate-registry.py` so they:
- default missing `schema_version` to `1`
- fail on non-integer values
- fail on unsupported future versions with a clear message

Update all three templates to write:

```json
"schema_version": 1,
```

near the top of `_meta.json`.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-skill-meta-compat.py
```

Expected: PASS.

**Step 5: Run a broader local validation pass**

Run:

```bash
INFINITAS_SKIP_RELEASE_TESTS=1 \
INFINITAS_SKIP_ATTESTATION_TESTS=1 \
INFINITAS_SKIP_DISTRIBUTION_TESTS=1 \
INFINITAS_SKIP_AI_WRAPPER_TESTS=1 \
INFINITAS_SKIP_BOOTSTRAP_TESTS=1 \
./scripts/check-all.sh
```

Expected: PASS, possibly with the existing warning about `config/allowed_signers` having no trusted signer entries.

**Step 6: Commit**

```bash
git add schemas/skill-meta.schema.json scripts/check-skill.sh scripts/validate-registry.py scripts/test-skill-meta-compat.py templates/basic-skill/_meta.json templates/scripted-skill/_meta.json templates/reference-heavy-skill/_meta.json docs/metadata-schema.md
git commit -m "feat: version skill metadata schema"
```

### Task 3: Add install-manifest schema-version support and centralize manifest IO

**Files:**
- Create: `scripts/install_manifest_lib.py`
- Create: `scripts/test-install-manifest-compat.py`
- Modify: `scripts/update-install-manifest.py`
- Modify: `scripts/dependency_lib.py`
- Modify: `scripts/list-installed.sh`
- Modify: `scripts/sync-skill.sh`
- Modify: `scripts/rollback-installed-skill.sh`
- Modify: `scripts/switch-installed-skill.sh`
- Modify: `docs/history-and-snapshots.md`

**Step 1: Write the failing compatibility test**

Create `scripts/test-install-manifest-compat.py` with temp-target fixtures that cover:

```python
legacy_manifest = {
    'repo': 'example',
    'updated_at': '2026-03-12T00:00:00Z',
    'skills': {'demo': {'name': 'demo', 'version': '1.2.3'}},
    'history': {},
}

assert list_installed_accepts(legacy_manifest)
assert dependency_planner_accepts(legacy_manifest)

new_manifest = read_manifest_after_install()
assert new_manifest['schema_version'] == 1
```

Also assert that a malformed future manifest version fails with a message mentioning `schema_version`.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-install-manifest-compat.py
```

Expected: FAIL because install-manifest version handling is still duplicated and implicit.

**Step 3: Add a shared manifest helper**

Create `scripts/install_manifest_lib.py` with helpers shaped like:

```python
def load_install_manifest(target_dir: Path) -> dict:
    ...


def normalize_install_manifest(payload: dict) -> dict:
    ...


def write_install_manifest(target_dir: Path, payload: dict) -> Path:
    ...
```

Rules:
- missing `schema_version` becomes `1`
- current writer emits `schema_version = 1`
- preserve unknown top-level keys where reasonable
- preserve `history` entries rather than rewriting them away

**Step 4: Move readers and writers onto the shared helper**

Refactor these paths to use the shared loader/writer:
- `scripts/update-install-manifest.py`
- `scripts/dependency_lib.py`
- `scripts/list-installed.sh`
- `scripts/sync-skill.sh`
- `scripts/rollback-installed-skill.sh`
- `scripts/switch-installed-skill.sh`

Do not change install semantics yet; this task is about versioned IO, not new behavior.

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-install-manifest-compat.py
```

Expected: PASS.

**Step 6: Re-run an existing install-flow regression**

Run:

```bash
python3 scripts/test-distribution-install.py
```

Expected: PASS.

**Step 7: Commit**

```bash
git add scripts/install_manifest_lib.py scripts/test-install-manifest-compat.py scripts/update-install-manifest.py scripts/dependency_lib.py scripts/list-installed.sh scripts/sync-skill.sh scripts/rollback-installed-skill.sh scripts/switch-installed-skill.sh docs/history-and-snapshots.md
git commit -m "feat: version install manifests"
```

### Task 4: Add migration commands for metadata and install manifests

**Files:**
- Create: `scripts/migrate-skill-meta.py`
- Create: `scripts/migrate-install-manifest.py`
- Create: `scripts/test-migrations.py`
- Modify: `README.md`
- Modify: `docs/compatibility-contract.md`
- Modify: `docs/metadata-schema.md`
- Modify: `docs/history-and-snapshots.md`

**Step 1: Write the failing migration test**

Create `scripts/test-migrations.py` and cover these cases:

```python
result = run([sys.executable, 'scripts/migrate-skill-meta.py', '--check', legacy_skill_dir])
assert result.returncode == 1
assert 'would update schema_version to 1' in combined_output

result = run([sys.executable, 'scripts/migrate-install-manifest.py', '--check', target_dir])
assert result.returncode == 1
assert 'would write schema_version' in combined_output

run([sys.executable, 'scripts/migrate-skill-meta.py', legacy_skill_dir])
run([sys.executable, 'scripts/migrate-install-manifest.py', target_dir])
assert migrated_files_are_valid()
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-migrations.py
```

Expected: FAIL because the migration commands do not exist yet.

**Step 3: Implement the migration commands**

`scripts/migrate-skill-meta.py` should:
- accept one skill directory or a parent directory
- support `--check`
- add `schema_version: 1` when missing
- preserve formatting as plain JSON rewrite with trailing newline
- refuse unsupported future versions rather than silently rewriting them

`scripts/migrate-install-manifest.py` should:
- accept a target skills directory or a direct manifest path
- support `--check`
- add `schema_version: 1` when missing
- preserve `skills`, `history`, and extra metadata

**Step 4: Re-run the focused migration test**

Run:

```bash
python3 scripts/test-migrations.py
```

Expected: PASS.

**Step 5: Smoke-test the commands on the current repo**

Run:

```bash
python3 scripts/migrate-skill-meta.py --check templates skills
python3 scripts/migrate-install-manifest.py --check ~/.openclaw/skills || true
```

Expected:
- first command exits `0` if everything in-repo is already current, otherwise prints what would change
- second command is allowed to no-op cleanly when the target manifest does not exist locally

**Step 6: Commit**

```bash
git add scripts/migrate-skill-meta.py scripts/migrate-install-manifest.py scripts/test-migrations.py README.md docs/compatibility-contract.md docs/metadata-schema.md docs/history-and-snapshots.md
git commit -m "feat: add compatibility migration commands"
```

### Task 5: Add compatibility regression coverage and wire it into CI

**Files:**
- Create: `scripts/test-compat-regression.py`
- Modify: `scripts/check-all.sh`
- Modify: `README.md`
- Modify: `docs/compatibility-contract.md`
- Modify: `docs/history-and-snapshots.md`

**Step 1: Write the failing end-to-end compatibility test**

Create `scripts/test-compat-regression.py` using the temp-repo pattern and cover this minimum matrix:

```python
cases = [
    'legacy skill metadata without schema_version still validates',
    'legacy install manifest without schema_version still loads',
    'locked install refuses unsafe upgrade',
    'archived exact-version snapshot still resolves',
    'bare skill name still resolves when publisher-qualified identity also exists',
]
```

Keep the test self-contained by scaffolding fixture skills from `templates/basic-skill` rather than committing long-lived test fixtures into the repo.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-compat-regression.py
```

Expected: FAIL because not all compatibility behaviors are pinned down yet.

**Step 3: Implement the missing compatibility glue**

As the test drives it, make the smallest behavior-preserving fixes needed so the full matrix passes. Likely touchpoints:
- clearer `schema_version` error messages
- shared manifest loading paths
- any one-off legacy parsing branch that still assumes the newest shape

Do **not** use this task to change resolution policy or identity semantics beyond what the test requires.

**Step 4: Wire the new regression into the standard check path**

Update `scripts/check-all.sh` to run:

```bash
python3 scripts/test-compat-regression.py
```

Place it after the focused metadata/install checks and before the full catalog rebuild diff.

**Step 5: Run the local validation flow**

Run:

```bash
INFINITAS_SKIP_RELEASE_TESTS=1 \
INFINITAS_SKIP_ATTESTATION_TESTS=1 \
INFINITAS_SKIP_DISTRIBUTION_TESTS=0 \
INFINITAS_SKIP_AI_WRAPPER_TESTS=0 \
INFINITAS_SKIP_BOOTSTRAP_TESTS=1 \
./scripts/check-all.sh
```

Expected: PASS, with the current signer warning still acceptable unless this task also includes signer bootstrap work.

**Step 6: Commit**

```bash
git add scripts/test-compat-regression.py scripts/check-all.sh README.md docs/compatibility-contract.md docs/history-and-snapshots.md
git commit -m "test: lock compatibility behavior"
```

## Follow-on work after this plan

These items are intentionally deferred until the compatibility baseline above is in place:

1. **Identity-first install state**
   - migrate install-history keys from bare `name` to `identity_key`
   - keep legacy alias lookups for a deprecation window
   - add same-slug cross-publisher coexistence tests

2. **Immutable-only stable install path**
   - make working-tree resolution explicitly dev-only
   - require distribution-manifest-backed installs for stable automation paths
   - add a strict mode flag rather than silently changing developer workflows

3. **Separate runtime compatibility from format compatibility**
   - keep `agent_compatible` for runtime claims
   - add a separate machine-readable schema-compatibility export if needed

## Final verification checklist

Before declaring the compatibility hardening complete, run all of the following from the worktree:

```bash
python3 scripts/test-skill-meta-compat.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-migrations.py
python3 scripts/test-compat-regression.py
python3 scripts/test-distribution-install.py
python3 scripts/test-ai-index.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-publish.py
INFINITAS_SKIP_RELEASE_TESTS=1 INFINITAS_SKIP_ATTESTATION_TESTS=1 INFINITAS_SKIP_BOOTSTRAP_TESTS=1 ./scripts/check-all.sh
```

Expected: all focused compatibility tests pass; broader checks pass except for any already-known local signer bootstrap warning.
