# Agent-First Discovery and Distribution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a private-first, by-name discovery and install workflow to `infinitas-skill`, with explicit external-registry confirmation, source-aware install state, and deterministic update/upgrade commands.

**Architecture:** Keep the current immutable release model as the execution core. Add a generated `discovery-index` for name resolution, extend the exact install path so it can target a specific configured registry, then build thin user-facing commands on top: `resolve-skill.sh`, `install-by-name.sh`, `check-skill-update.sh`, and `upgrade-skill.sh`. Preserve backward compatibility for existing exact-name installs, install manifests, and `pull-skill.sh` behavior when `--registry` is omitted.

**Tech Stack:** Bash, Python 3.11, JSON, existing `catalog/ai-index.json`, `scripts/build-catalog.sh`, `scripts/pull-skill.sh`, `scripts/install-skill.sh`, `scripts/update-install-manifest.py`, `scripts/install_manifest_lib.py`, and the temp-repo integration-test style used by `scripts/test-ai-index.py` and `scripts/test-distribution-install.py`.

---

## Preconditions

- Create a dedicated worktree before implementation.
- Use `Python 3.11` for all new tests and scripts.
- Use `@superpowers:test-driven-development` discipline inside each task: test first, then minimal implementation.
- Before claiming success on any task, use `@superpowers:verification-before-completion` and run the exact validation commands listed in that task.
- Do **not** weaken the existing immutable install policy:
  - no direct installs from `skills/active/` or `skills/incubating/`
  - no silent external-registry auto-installs
  - no fallback from immutable release artifacts to mutable source for the new agent-facing commands

## Scope decisions

- Keep `scripts/pull-skill.sh` as the exact immutable installer, but extend it with optional registry selection.
- Add `catalog/discovery-index.json` as a new machine-facing aggregation layer; do **not** replace `catalog/ai-index.json`.
- Prefer thin shell entrypoints plus Python helper libraries over large monolithic shell scripts.
- Make external-registry matches confirmation-gated by default.
- Keep install-manifest reads backward-compatible with existing schema version behavior.
- Defer `search-skills.sh` and `recommend-skill.sh` until after by-name install and source-aware upgrade are shipped.

### Task 1: Add the discovery index schema and generator

**Files:**
- Create: `schemas/discovery-index.schema.json`
- Create: `scripts/discovery_index_lib.py`
- Modify: `scripts/build-catalog.sh:18-23`
- Modify: `scripts/build-catalog.sh:80-86`
- Modify: `scripts/validate-registry.py:233-245`
- Modify: `scripts/check-all.sh:24-29`
- Test: `scripts/test-discovery-index.py`

**Step 1: Write the failing test**

Create `scripts/test-discovery-index.py` using the same temp-repo style as `scripts/test-ai-index.py`. Cover these cases:

```python
payload = json.loads((repo / 'catalog' / 'discovery-index.json').read_text(encoding='utf-8'))
assert payload['default_registry'] == 'self'
assert payload['resolution_policy']['private_registry_first'] is True
assert 'skills' in payload and payload['skills']

first = payload['skills'][0]
assert first['qualified_name']
assert first['source_registry']
assert isinstance(first['match_names'], list)
assert isinstance(first['install_requires_confirmation'], bool)
```

Also add one negative case by corrupting the generated file, for example:

```python
payload['skills'][0]['match_names'] = 'not-a-list'
write_json(discovery_index_path, payload)
result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
assert 'match_names' in (result.stdout + result.stderr)
```

Seed two fixture registries in the temp repo:

- `self` with one released active skill
- `external-demo` as a `local-only` configured registry clone with one released active skill and its own `catalog/ai-index.json`

This makes the first implementation exercise both local and external aggregation without network access.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-discovery-index.py
```

Expected: FAIL because `catalog/discovery-index.json`, its schema, and the generator do not exist yet.

**Step 3: Implement the discovery-index generator and validator**

Create `schemas/discovery-index.schema.json` with a compact, explicit schema. Require these top-level fields:

```json
{
  "schema_version": 1,
  "generated_at": "2026-03-12T00:00:00Z",
  "default_registry": "self",
  "sources": [],
  "resolution_policy": {
    "private_registry_first": true,
    "external_requires_confirmation": true,
    "auto_install_mutable_sources": false
  },
  "skills": []
}
```

Create `scripts/discovery_index_lib.py` with small pure functions:

```python
def build_discovery_index(*, root: Path, local_ai_index: dict, registry_config: dict) -> dict:
    ...

def validate_discovery_index_payload(payload: dict) -> list[str]:
    ...

def normalize_discovery_skill(entry: dict) -> dict:
    return {
        'name': entry['name'],
        'qualified_name': entry['qualified_name'],
        'source_registry': entry['source_registry'],
        'match_names': sorted({entry['name'], entry['qualified_name'], *entry.get('aliases', [])}),
        'install_requires_confirmation': entry['source_registry'] != default_registry,
    }
```

Implementation details:

- Read `catalog/ai-index.json` from the working repo for the local registry.
- For every enabled configured registry from `registry_source_lib.load_registry_config`, resolve its local root with `resolve_registry_root`.
- For external registries, load their cached `catalog/ai-index.json` if present; skip missing files silently for now and report them only in `sources[*].status`.
- Normalize all entries into one `skills` array with:
  - `name`
  - `qualified_name`
  - `publisher`
  - `summary`
  - `source_registry`
  - `source_priority`
  - `match_names`
  - `default_install_version`
  - `latest_version`
  - `available_versions`
  - `agent_compatible`
  - `install_requires_confirmation`
  - `trust_level`
  - `use_when`
  - `avoid_when`
- Sort the aggregated list by `source_priority` descending, then `qualified_name`, then `latest_version` descending.

Modify `scripts/build-catalog.sh` to:

- import `build_discovery_index`
- compute `out_discovery_index = root / 'catalog' / 'discovery-index.json'`
- write the new artifact next to `catalog/ai-index.json`

Modify `scripts/validate-registry.py` to validate `catalog/discovery-index.json` if it exists, mirroring the existing `validate_ai_index` pattern.

Modify `scripts/check-all.sh` so its catalog normalization and diff checks include `catalog/discovery-index.json`.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-discovery-index.py
```

Expected: PASS.

**Step 5: Run a broader validation pass**

Run:

```bash
INFINITAS_SKIP_RELEASE_TESTS=1 \
INFINITAS_SKIP_ATTESTATION_TESTS=1 \
INFINITAS_SKIP_DISTRIBUTION_TESTS=1 \
INFINITAS_SKIP_AI_WRAPPER_TESTS=1 \
INFINITAS_SKIP_BOOTSTRAP_TESTS=1 \
./scripts/check-all.sh
```

Expected: PASS.

**Step 6: Commit**

```bash
git add schemas/discovery-index.schema.json scripts/discovery_index_lib.py scripts/test-discovery-index.py scripts/build-catalog.sh scripts/validate-registry.py scripts/check-all.sh catalog/discovery-index.json
git commit -m "feat: add discovery index"
```

### Task 2: Extend the immutable pull path with registry selection

**Files:**
- Modify: `scripts/pull-skill.sh:4-249`
- Modify: `docs/ai/pull.md`
- Test: `scripts/test-ai-pull.py`

**Step 1: Write the failing test**

Extend `scripts/test-ai-pull.py` with a new scenario that creates a second configured registry and released fixture skill, then calls:

```bash
scripts/pull-skill.sh partner/demo-skill /tmp/target --registry external-demo --mode confirm
```

Assert that the JSON payload includes:

```python
assert payload['qualified_name'] == 'partner/demo-skill'
assert payload['registry_name'] == 'external-demo'
assert payload['resolved_version'] == '1.2.3'
assert payload['state'] == 'planned'
```

Also add a negative case:

```python
result = run([... '--registry', 'external-demo', '--version', '9.9.9'], expect=1)
assert 'version-not-found' in (result.stdout + result.stderr)
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-ai-pull.py
```

Expected: FAIL because `scripts/pull-skill.sh` does not accept `--registry` yet.

**Step 3: Implement registry-aware immutable pull**

Update `scripts/pull-skill.sh` to accept:

```bash
scripts/pull-skill.sh <qualified-name-or-name> <target-dir> [--version X.Y.Z] [--registry NAME] [--mode auto|confirm]
```

Refactor the embedded Python so it:

- loads the configured registry config via `registry_source_lib.load_registry_config`
- resolves the requested registry root via `resolve_registry_root`
- reads `catalog/ai-index.json` from that registry root instead of always using the working repo root when `--registry` is present
- includes these fields in the output JSON:

```json
{
  "registry_name": "external-demo",
  "registry_root": "/abs/path/to/cache",
  "ai_index_path": "catalog/ai-index.json"
}
```

Preserve current behavior when `--registry` is omitted.

When `--registry` is provided:

- fail if the registry is disabled or unresolved
- fail if the target registry has no valid `catalog/ai-index.json`
- keep the same immutable-only install-policy checks
- pass the resolved registry name through to the final install result so `install-by-name.sh` can call this command deterministically

Update `docs/ai/pull.md` so the contract explicitly documents optional registry selection for federated-but-local immutable pulls.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-ai-pull.py
```

Expected: PASS.

**Step 5: Run the AI-wrapper subset**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-publish.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/pull-skill.sh docs/ai/pull.md scripts/test-ai-pull.py
git commit -m "feat: allow registry-aware immutable pulls"
```

### Task 3: Add deterministic name resolution

**Files:**
- Create: `scripts/discovery_resolver_lib.py`
- Create: `scripts/resolve-skill.sh`
- Test: `scripts/test-resolve-skill.py`
- Modify: `docs/ai/agent-operations.md:45-60`

**Step 1: Write the failing test**

Create `scripts/test-resolve-skill.py` using the same temp-repo fixture style. Cover these cases:

```python
payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), 'demo-skill']).stdout)
assert payload['state'] == 'resolved-private'
assert payload['requires_confirmation'] is False
assert payload['resolved']['source_registry'] == 'self'

payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), 'external-only-skill']).stdout)
assert payload['state'] == 'resolved-external'
assert payload['requires_confirmation'] is True

payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), 'ambiguous-skill']).stdout)
assert payload['state'] == 'ambiguous'
assert len(payload['candidates']) == 2
```

Also add a target-agent compatibility case:

```python
payload = json.loads(run([..., '--target-agent', 'codex']).stdout)
assert payload['state'] != 'incompatible'
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-resolve-skill.py
```

Expected: FAIL because the resolver command and library do not exist yet.

**Step 3: Implement the resolver library and shell entrypoint**

Create `scripts/discovery_resolver_lib.py` with small functions such as:

```python
def load_discovery_index(root: Path) -> dict:
    ...

def filter_candidates(skills: list[dict], query: str, *, target_agent: str | None) -> list[dict]:
    ...

def rank_candidates(candidates: list[dict], *, default_registry: str) -> list[dict]:
    return sorted(candidates, key=lambda item: (
        item.get('source_registry') != default_registry,
        query not in {item.get('name'), item.get('qualified_name')},
        target_agent not in (item.get('agent_compatible') or []),
        -(item.get('source_priority') or 0),
        item.get('qualified_name') or '',
    ))
```

Create `scripts/resolve-skill.sh` as a thin shell wrapper around that library. Its JSON output should look like:

```json
{
  "ok": true,
  "query": "demo-skill",
  "state": "resolved-private",
  "resolved": {
    "qualified_name": "lvxiaoer/demo-skill",
    "source_registry": "self",
    "resolved_version": "1.2.3"
  },
  "candidates": [],
  "requires_confirmation": false,
  "recommended_next_step": "run install-by-name"
}
```

Return these `state` values exactly:

- `resolved-private`
- `resolved-external`
- `ambiguous`
- `not-found`
- `incompatible`

Resolver rules:

- private-registry exact or unique matches win immediately
- if private has multiple matches, stop and return `ambiguous`
- only search external registries when private has no suitable match
- external-only results must set `requires_confirmation=true`
- never read mutable source directories for this command; use `catalog/discovery-index.json` only

Update `docs/ai/agent-operations.md` quick decision guide to mention `scripts/resolve-skill.sh` for “find the right installable skill by name”.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-resolve-skill.py
```

Expected: PASS.

**Step 5: Rebuild catalogs and smoke the resolver manually**

Run:

```bash
scripts/build-catalog.sh
scripts/resolve-skill.sh demo-skill
scripts/resolve-skill.sh demo-skill --target-agent codex
```

Expected: valid JSON each time; at least one call returns `resolved-private`.

**Step 6: Commit**

```bash
git add scripts/discovery_resolver_lib.py scripts/resolve-skill.sh scripts/test-resolve-skill.py docs/ai/agent-operations.md
git commit -m "feat: add skill resolver"
```

### Task 4: Add by-name install and richer install-manifest state

**Files:**
- Create: `scripts/install-by-name.sh`
- Modify: `scripts/install_manifest_lib.py:22-75`
- Modify: `scripts/update-install-manifest.py:43-110`
- Modify: `scripts/list-installed.sh:23-49`
- Test: `scripts/test-install-by-name.py`
- Test: `scripts/test-distribution-install.py`
- Test: `scripts/test-install-manifest-compat.py`

**Step 1: Write the failing test**

Create `scripts/test-install-by-name.py` with these scenarios:

```python
run([str(repo / 'scripts' / 'install-by-name.sh'), 'demo-skill', str(target_dir)], cwd=repo)
manifest = read_install_manifest(target_dir)
entry = manifest['skills']['demo-skill']
assert entry['source_registry'] == 'self'
assert entry['qualified_name'] == 'lvxiaoer/demo-skill'
assert entry['installed_version'] == '1.2.3'
assert entry['resolved_release_digest']
assert entry['install_target'] == str(target_dir)
```

Add an external-only safety case:

```python
result = run([str(repo / 'scripts' / 'install-by-name.sh'), 'external-only-skill', str(target_dir)], cwd=repo, expect=1)
assert 'confirmation-required' in (result.stdout + result.stderr)
assert not (target_dir / 'external-only-skill').exists()
```

Add a confirm-mode case:

```python
payload = json.loads(run([..., '--mode', 'confirm']).stdout)
assert payload['state'] == 'planned'
assert payload['requires_confirmation'] is True
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-install-by-name.py
```

Expected: FAIL because `scripts/install-by-name.sh` does not exist yet.

**Step 3: Implement the installer and manifest extensions**

Create `scripts/install-by-name.sh` as a thin orchestrator:

1. call `scripts/resolve-skill.sh`
2. if `state=ambiguous` or `state=not-found`, print the JSON and exit non-zero
3. if `state=resolved-external` and `--mode auto`, fail with `confirmation-required`
4. call `scripts/pull-skill.sh <qualified_name> <target-dir> --version <resolved_version> --registry <source_registry>`
5. emit one final JSON payload for the caller

Its final payload should include:

```json
{
  "ok": true,
  "query": "demo-skill",
  "qualified_name": "lvxiaoer/demo-skill",
  "source_registry": "self",
  "requested_version": null,
  "resolved_version": "1.2.3",
  "target_dir": "/tmp/installed",
  "manifest_path": "/tmp/installed/.infinitas-skill-install-manifest.json",
  "state": "installed",
  "requires_confirmation": false,
  "next_step": "check-update-or-use"
}
```

Extend `scripts/update-install-manifest.py` so each manifest entry writes these new fields in a backward-compatible way:

```python
manifest_entry.update({
    'installed_version': meta.get('version'),
    'resolved_release_digest': source_info.get('distribution_bundle_sha256'),
    'install_target': str(target_dir),
    'installed_at': manifest['updated_at'],
    'last_checked_at': manifest['updated_at'],
    'target_agent': source_info.get('target_agent'),
    'install_mode': action,
})
```

Do **not** remove current fields like `version`, `locked_version`, `source_distribution_manifest`, or `resolution_plan`; keep old readers working.

Update `scripts/install_manifest_lib.py` to default missing new keys gracefully rather than hard-failing old manifests.

Update `scripts/list-installed.sh` so the display line surfaces the most useful new state, for example:

```text
- lvxiaoer/demo-skill: 1.2.3, locked=1.2.3 [active] (install) -> demo-skill from self/distribution-manifest, checked=2026-03-12T00:00:00Z
```

**Step 4: Re-run the focused tests**

Run:

```bash
python3 scripts/test-install-by-name.py
python3 scripts/test-install-manifest-compat.py
```

Expected: PASS.

**Step 5: Run the adjacent install regression suite**

Run:

```bash
python3 scripts/test-distribution-install.py
python3 scripts/test-compat-regression.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/install-by-name.sh scripts/install_manifest_lib.py scripts/update-install-manifest.py scripts/list-installed.sh scripts/test-install-by-name.py scripts/test-distribution-install.py scripts/test-install-manifest-compat.py
git commit -m "feat: add install by name"
```

### Task 5: Add source-aware update checks and upgrades

**Files:**
- Create: `scripts/check-skill-update.sh`
- Create: `scripts/upgrade-skill.sh`
- Test: `scripts/test-skill-update.py`
- Modify: `scripts/sync-skill.sh:47-180`
- Modify: `scripts/list-installed.sh:23-49`

**Step 1: Write the failing test**

Create `scripts/test-skill-update.py` using a released fixture with two versions. Cover these cases:

```python
payload = json.loads(run([str(repo / 'scripts' / 'check-skill-update.sh'), 'demo-skill', str(target_dir)]).stdout)
assert payload['installed_version'] == '1.2.3'
assert payload['latest_available_version'] == '1.2.4'
assert payload['update_available'] is True
assert payload['source_registry'] == 'self'
```

Upgrade case:

```python
payload = json.loads(run([str(repo / 'scripts' / 'upgrade-skill.sh'), 'demo-skill', str(target_dir)]).stdout)
assert payload['from_version'] == '1.2.3'
assert payload['to_version'] == '1.2.4'
manifest = read_install_manifest(target_dir)
assert manifest['skills']['demo-skill']['installed_version'] == '1.2.4'
assert len((manifest['history'] or {}).get('demo-skill') or []) >= 1
```

Safety case:

```python
result = run([str(repo / 'scripts' / 'upgrade-skill.sh'), 'demo-skill', str(target_dir), '--registry', 'other-registry'], expect=1)
assert 'cross-source-upgrade-not-allowed' in (result.stdout + result.stderr)
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-skill-update.py
```

Expected: FAIL because both commands are missing.

**Step 3: Implement source-aware update and upgrade commands**

Create `scripts/check-skill-update.sh` that:

- loads the install manifest entry by name or qualified name
- reads `source_registry`, `qualified_name`, and `installed_version`
- calls the same registry-aware immutable resolution path used by `pull-skill.sh`
- returns a non-mutating JSON payload:

```json
{
  "ok": true,
  "qualified_name": "lvxiaoer/demo-skill",
  "source_registry": "self",
  "installed_version": "1.2.3",
  "latest_available_version": "1.2.4",
  "update_available": true,
  "state": "update-available",
  "next_step": "run upgrade-skill"
}
```

Create `scripts/upgrade-skill.sh` that:

- reads the existing install-manifest entry
- refuses to switch registries silently
- uses `scripts/pull-skill.sh` with the recorded `source_registry`
- preserves atomic behavior by relying on the existing exact install path
- records history through `scripts/update-install-manifest.py`

Refactor `scripts/sync-skill.sh` to reuse the same manifest lookup rules instead of duplicating ad hoc resolution where practical. Keep the current sync command behavior, but do not make it the new preferred update path for agents.

Update `scripts/list-installed.sh` to show the latest check timestamp when present.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-skill-update.py
```

Expected: PASS.

**Step 5: Run the broader install/update regression suite**

Run:

```bash
python3 scripts/test-distribution-install.py
python3 scripts/test-ai-pull.py
python3 scripts/test-compat-regression.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/check-skill-update.sh scripts/upgrade-skill.sh scripts/test-skill-update.py scripts/sync-skill.sh scripts/list-installed.sh
git commit -m "feat: add source-aware skill upgrades"
```

### Task 6: Document the new machine-facing flow and wire it into CI

**Files:**
- Create: `docs/ai/discovery.md`
- Modify: `README.md:122-205`
- Modify: `docs/ai/agent-operations.md:45-60`
- Modify: `docs/multi-registry.md:96-127`
- Modify: `docs/distribution-manifests.md`
- Modify: `scripts/check-all.sh:24-29`

**Step 1: Write the failing discoverability check**

Run this search before editing docs:

```bash
rg -n 'resolve-skill|install-by-name|check-skill-update|upgrade-skill|discovery-index' README.md docs/ai docs
```

Expected: FAIL or sparse output because the new commands and discovery index are not yet documented.

**Step 2: Add the machine-facing documentation**

Create `docs/ai/discovery.md` with these sections:

```md
# Discovery and Install Protocol

## Commands
## Resolution policy
## Confirmation rules
## Output JSON
## Failure states
## Forbidden assumptions
```

Document these rules explicitly:

- private registry is searched first
- external-only matches require confirmation
- by-name install still uses immutable release artifacts only
- update checks are non-mutating
- upgrades use the recorded source registry unless the caller explicitly chooses otherwise

Update:

- `README.md` quick-start examples to include `scripts/resolve-skill.sh`, `scripts/install-by-name.sh`, and `scripts/check-skill-update.sh`
- `docs/ai/agent-operations.md` quick decision guide to point agents at `resolve-skill.sh` and `install-by-name.sh`
- `docs/multi-registry.md` to explain how synced external registries contribute to discovery but remain confirmation-gated for installation
- `docs/distribution-manifests.md` to explain that by-name install still resolves to a specific immutable distribution manifest before materialization

**Step 3: Wire the new tests into CI**

Update `scripts/check-all.sh` to run the new focused tests in the AI-wrapper section:

```bash
python3 scripts/test-discovery-index.py
python3 scripts/test-resolve-skill.py
python3 scripts/test-install-by-name.py
python3 scripts/test-skill-update.py
```

Also include `catalog/discovery-index.json` in both normalization loops and in the diff output when catalogs drift.

**Step 4: Run the full local validation suite**

Run:

```bash
./scripts/check-all.sh
```

Expected: PASS.

If environment-specific release/signing prerequisites block the full suite, re-run with the existing skip flags and record the skipped subset in the implementation notes.

**Step 5: Commit**

```bash
git add docs/ai/discovery.md README.md docs/ai/agent-operations.md docs/multi-registry.md docs/distribution-manifests.md scripts/check-all.sh
git commit -m "docs: add discovery and install workflow"
```

## Execution notes

- Keep new behavior additive. Existing `scripts/install-skill.sh`, `scripts/pull-skill.sh`, and install-manifest consumers should keep working for current users.
- Favor pure-Python helpers for ranking, validation, and manifest transforms; use shell only for orchestration.
- When a task uncovers a bug or ambiguous current behavior, stop and use `@superpowers:systematic-debugging` before changing unrelated logic.
- Do not add a hosted service, database, or UI in this pass.

## Suggested implementation order

1. `catalog/discovery-index.json`
2. registry-aware `pull-skill.sh`
3. `resolve-skill.sh`
4. `install-by-name.sh`
5. `check-skill-update.sh` and `upgrade-skill.sh`
6. docs and CI
