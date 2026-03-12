# Sustainable Triple-Agent Compatibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a sustainable compatibility system for `infinitas-skill` where skills are authored once, rendered for Claude/Codex/OpenClaw via platform adapters, and marked compatible only when fresh verification evidence exists.

**Architecture:** Introduce a canonical skill source model and platform profiles, add a dual-read loader for canonical and legacy skills, implement a shared renderer engine, refactor OpenClaw export to use normalized renderer output, add Codex and Claude exporters plus compatibility verifiers, and regenerate `catalog/compatibility.json` from evidence instead of author-declared tags. Keep phase 1 additive and dependency-free: readers accept the current registry layout, writers may continue to emit existing release/governance structures, and new compatibility infrastructure layers in alongside the current system.

**Tech Stack:** Bash, Python 3.11, JSON Schema draft 2020-12, existing release/install scripts, current OpenClaw bridge tooling, temp-repo style Python tests, generated catalogs, and the current `scripts/check-all.sh` validation flow.

---

## Preconditions

- Create a dedicated worktree before implementation.
- Standardize on `Python 3.11` for all new scripts and tests.
- Keep the first pass dependency-free; do not require `PyYAML` or other third-party packages.
- Preserve current OpenClaw import/export behavior during migration unless an explicit verification test is updated.
- Do not remove `_meta.json`, `skills/incubating`, `skills/active`, `skills/archived`, or current release manifests in this plan.
- Treat existing `_meta.json.agent_compatible` as a legacy declaration during implementation, not the long-term source of truth.

## Scope decisions

- Implement the **canonical model** using JSON metadata files in phase 1 to keep the toolchain dependency-free.
- Keep canonical instructions bodies in Markdown files separate from metadata.
- Add platform overlays and profiles as machine-readable JSON.
- Rendered platform outputs belong under `build/` or release/export targets and should be treated as generated artifacts.
- Compatibility catalog output must distinguish **declared** support from **verified** support.
- Public-ready OpenClaw export must add structural validation for license and text-only constraints before it can be claimed publishable.

## Non-goals

- Do not build a hosted registry service.
- Do not redesign the immutable release artifact model.
- Do not require exact feature parity when a platform truly lacks a capability.
- Do not remove existing OpenClaw bridge commands.
- Do not implement automatic public `clawhub publish`.

## Delivery phases

- **Phase 1:** canonical schema + platform profiles + dual-read loader
- **Phase 2:** shared renderer engine + deterministic generated outputs
- **Phase 3:** OpenClaw renderer integration + publish-grade checks
- **Phase 4:** Codex adapter + verifier
- **Phase 5:** Claude adapter + verifier
- **Phase 6:** compatibility evidence + contract-watch + CI wiring

### Task 1: Add canonical schema and platform profiles

**Files:**
- Create: `schemas/skill-canonical.schema.json`
- Create: `schemas/platform-profile.schema.json`
- Create: `profiles/claude.json`
- Create: `profiles/codex.json`
- Create: `profiles/openclaw.json`
- Create: `scripts/test-canonical-contracts.py`
- Modify: `README.md`
- Modify: `docs/compatibility-contract.md`
- Modify: `docs/compatibility-matrix.md`

**Step 1: Write the failing schema/profile test**

Create `scripts/test-canonical-contracts.py` with checks shaped like:

```python
payload = json.loads((repo / 'profiles' / 'codex.json').read_text())
assert payload['platform'] == 'codex'
assert payload['runtime']['skill_dir_candidates']

schema = json.loads((repo / 'schemas' / 'skill-canonical.schema.json').read_text())
assert schema['$schema'] == 'https://json-schema.org/draft/2020-12/schema'
assert 'tool_intents' in schema['properties']
```

Also add assertions that `README.md` and `docs/compatibility-matrix.md` mention `declared` vs `verified` compatibility terminology.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-canonical-contracts.py
```

Expected: FAIL because the schemas/profiles do not exist yet.

**Step 3: Add the canonical schema**

Create `schemas/skill-canonical.schema.json` with required fields shaped like:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://openai.invalid/infinitas-skill/skill-canonical.schema.json",
  "type": "object",
  "required": [
    "schema_version",
    "name",
    "summary",
    "description",
    "instructions_body",
    "tool_intents",
    "verification"
  ]
}
```

Include properties for:

- `schema_version`
- `name`
- `summary`
- `description`
- `triggers`
- `examples`
- `instructions_body`
- `tool_intents.required`
- `tool_intents.optional`
- `degrades_to`
- `distribution`
- `verification`

**Step 4: Add the platform profile schema and three initial profiles**

Create `schemas/platform-profile.schema.json` and profile files with at least these sections:

```json
{
  "schema_version": 1,
  "platform": "codex",
  "runtime": {
    "skill_dir_candidates": [".agents/skills", "~/.agents/skills"],
    "entrypoint": "SKILL.md"
  },
  "capabilities": {
    "supports_subagents": true,
    "supports_commands": false
  },
  "constraints": {
    "text_only_public_bundle": false
  },
  "contract": {
    "sources": ["https://platform.openai.com/docs/codex/overview#skills"],
    "last_verified": "2026-03-12"
  }
}
```

Match the same structure for `claude` and `openclaw`, with OpenClaw explicitly setting public text-only and license constraints.

**Step 5: Update docs to introduce the new terminology**

Add a short section to `README.md` and `docs/compatibility-matrix.md` that distinguishes:

- declared support
- verified support
- compatibility evidence

In `docs/compatibility-contract.md`, add a note that platform compatibility is now evidence-backed and may differ from author declaration during the migration window.

**Step 6: Re-run the focused test**

Run:

```bash
python3 scripts/test-canonical-contracts.py
```

Expected: PASS.

**Step 7: Commit**

```bash
git add schemas/skill-canonical.schema.json schemas/platform-profile.schema.json profiles/claude.json profiles/codex.json profiles/openclaw.json scripts/test-canonical-contracts.py README.md docs/compatibility-contract.md docs/compatibility-matrix.md
git commit -m "feat: add canonical skill and platform profile contracts"
```

### Task 2: Add dual-read canonical and legacy skill loader

**Files:**
- Create: `scripts/canonical_skill_lib.py`
- Create: `scripts/test-canonical-skill.py`
- Modify: `scripts/validate-registry.py`
- Modify: `scripts/check-skill.sh`
- Modify: `scripts/schema_version_lib.py`

**Step 1: Write the failing loader test**

Create `scripts/test-canonical-skill.py` covering two source modes:

```python
def test_loads_canonical_skill_source():
    canonical = load_skill_source(repo / 'skills-src' / 'demo-skill')
    assert canonical['name'] == 'demo-skill'
    assert canonical['source_mode'] == 'canonical'


def test_loads_legacy_registry_skill_source():
    legacy = load_skill_source(repo / 'skills' / 'incubating' / 'demo-skill')
    assert legacy['name'] == 'demo-skill'
    assert legacy['source_mode'] == 'legacy'
    assert legacy['instructions_body_path'].name == 'SKILL.md'
```

Also assert that unsupported canonical schema versions fail with a clear message.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-canonical-skill.py
```

Expected: FAIL because the loader library does not exist yet.

**Step 3: Implement a normalized in-memory model**

Add `scripts/canonical_skill_lib.py` with functions shaped like:

```python
def load_skill_source(path: Path) -> dict:
    ...


def load_canonical_skill(path: Path) -> dict:
    ...


def load_legacy_skill(path: Path) -> dict:
    ...


def validate_canonical_payload(payload: dict) -> list[str]:
    ...
```

Required normalized fields:

- `name`
- `summary`
- `description`
- `instructions_body_path`
- `tool_intents`
- `platform_overrides`
- `distribution`
- `verification`
- `source_mode`

For legacy `skills/<stage>/<name>` folders, derive these fields from:

- `_meta.json`
- `SKILL.md`
- existing tests/entrypoints metadata

**Step 4: Wire validation into the existing registry checker**

Update `scripts/validate-registry.py` and `scripts/check-skill.sh` so they can validate either:

- legacy registry folders
- canonical `skills-src/<name>` folders

The current registry validation behavior must remain unchanged for legacy skills.

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-canonical-skill.py
```

Expected: PASS.

**Step 6: Run a regression check on legacy validation**

Run:

```bash
python3 scripts/test-skill-meta-compat.py
```

Expected: PASS, confirming the new loader did not break current metadata compatibility.

**Step 7: Commit**

```bash
git add scripts/canonical_skill_lib.py scripts/test-canonical-skill.py scripts/validate-registry.py scripts/check-skill.sh scripts/schema_version_lib.py
git commit -m "feat: add dual-read canonical skill loader"
```

### Task 3: Add a shared renderer engine

**Files:**
- Create: `scripts/render_skill_lib.py`
- Create: `scripts/render-skill.py`
- Create: `scripts/test-render-skill.py`
- Create: `build/.gitkeep`
- Modify: `scripts/check-all.sh`

**Step 1: Write the failing renderer test**

Create `scripts/test-render-skill.py` with temp-repo fixtures that render a canonical skill to all three platforms:

```python
result = run([sys.executable, str(repo / 'scripts' / 'render-skill.py'), '--skill-dir', str(skill_dir), '--platform', 'codex', '--out', str(out_dir)])
assert (out_dir / 'SKILL.md').is_file()
assert 'description:' in (out_dir / 'SKILL.md').read_text()

result = run([sys.executable, str(repo / 'scripts' / 'render-skill.py'), '--skill-dir', str(skill_dir), '--platform', 'openclaw', '--out', str(out_dir)])
assert (out_dir / 'SKILL.md').is_file()
assert 'metadata.openclaw' in (out_dir / 'SKILL.md').read_text()
```

Also add a Claude case that verifies the output uses the Claude skill folder shape.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-render-skill.py
```

Expected: FAIL because no shared renderer exists yet.

**Step 3: Implement the renderer library**

Add `scripts/render_skill_lib.py` with functions shaped like:

```python
def render_skill(source: dict, platform: str, out_dir: Path, profile: dict) -> dict:
    ...


def render_skill_markdown(source: dict, platform: str, profile: dict) -> str:
    ...


def apply_tool_intent_mapping(source: dict, platform: str, profile: dict) -> dict:
    ...
```

Required renderer behavior:

- load normalized skill data via `canonical_skill_lib.py`
- load the matching profile from `profiles/<platform>.json`
- create deterministic output directories
- write `SKILL.md`
- optionally write supporting files referenced by the source
- return a JSON payload with `platform`, `out_dir`, and `files`

**Step 4: Add the CLI wrapper**

Create `scripts/render-skill.py` with flags:

```bash
python3 scripts/render-skill.py --skill-dir skills-src/demo-skill --platform codex --out build/codex/demo-skill
```

The command should emit JSON only.

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-render-skill.py
```

Expected: PASS.

**Step 6: Add the renderer to the broad validation flow**

Update `scripts/check-all.sh` to run:

```bash
python3 scripts/test-render-skill.py
```

before catalog generation.

**Step 7: Commit**

```bash
git add scripts/render_skill_lib.py scripts/render-skill.py scripts/test-render-skill.py build/.gitkeep scripts/check-all.sh
git commit -m "feat: add shared skill renderer"
```

### Task 4: Refactor OpenClaw export onto the renderer and harden publish compatibility

**Files:**
- Modify: `scripts/export-openclaw-skill.sh`
- Modify: `scripts/openclaw_bridge_lib.py`
- Create: `scripts/check-openclaw-compat.py`
- Modify: `scripts/test-openclaw-export.py`
- Modify: `docs/ai/openclaw.md`
- Modify: `docs/ai/publish.md`

**Step 1: Add the failing OpenClaw compatibility assertions**

Extend `scripts/test-openclaw-export.py` with assertions for:

- normalized `metadata.openclaw.requires` in exported `SKILL.md`
- explicit text-only bundle rejection for public-ready mode
- explicit license-policy rejection for non-MIT-0 public export

Suggested assertion shape:

```python
skill_md = (export_dir / 'SKILL.md').read_text(encoding='utf-8')
assert 'metadata.openclaw' in skill_md
assert 'requires:' in skill_md
```

Add one failing fixture that includes a binary file and expect the checker to fail in public-ready mode.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-openclaw-export.py
```

Expected: FAIL because current export only materializes release files and does not normalize or validate public constraints.

**Step 3: Refactor the export flow to call the shared renderer**

Update `scripts/openclaw_bridge_lib.py` so export goes through the renderer instead of directly copying release contents.

Required behavior:

- resolve the released version as today
- load or derive a normalized source model
- render an OpenClaw-compatible directory
- preserve immutable release provenance fields in the JSON result
- add a `public_ready` boolean and `validation_errors` list

**Step 4: Add the OpenClaw compatibility checker**

Create `scripts/check-openclaw-compat.py` with checks for:

- valid `SKILL.md` frontmatter
- required `metadata.openclaw` structure
- text-only files when `--public-ready` is set
- size budget when `--public-ready` is set
- MIT-0 license policy when `--public-ready` is set

**Step 5: Re-run the focused tests**

Run:

```bash
python3 scripts/test-openclaw-export.py
python3 scripts/check-openclaw-compat.py --help
```

Expected:
- export test PASS
- checker help exits successfully

**Step 6: Update the OpenClaw docs**

Clarify in `docs/ai/openclaw.md` and `docs/ai/publish.md` that:

- export is normalized, not just copied
- `public_ready` is a validated state
- manual `clawhub publish` remains explicit and separate

**Step 7: Commit**

```bash
git add scripts/export-openclaw-skill.sh scripts/openclaw_bridge_lib.py scripts/check-openclaw-compat.py scripts/test-openclaw-export.py docs/ai/openclaw.md docs/ai/publish.md
git commit -m "feat: normalize and validate openclaw exports"
```

### Task 5: Add a Codex exporter and verifier

**Files:**
- Create: `scripts/export-codex-skill.sh`
- Create: `scripts/check-codex-compat.py`
- Create: `scripts/test-codex-export.py`
- Modify: `README.md`
- Modify: `docs/compatibility-matrix.md`

**Step 1: Write the failing Codex export test**

Create `scripts/test-codex-export.py` with cases like:

```python
result = run([str(repo / 'scripts' / 'export-codex-skill.sh'), '--skill-dir', str(skill_dir), '--out', str(out_dir)], cwd=repo)
payload = json.loads(result.stdout)
assert payload['platform'] == 'codex'
assert (out_dir / 'SKILL.md').is_file()
assert 'name:' in (out_dir / 'SKILL.md').read_text(encoding='utf-8')
```

Also assert that the compatibility checker accepts the rendered output:

```python
run([sys.executable, str(repo / 'scripts' / 'check-codex-compat.py'), '--skill-dir', str(out_dir)], cwd=repo)
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-codex-export.py
```

Expected: FAIL because no Codex exporter or checker exists yet.

**Step 3: Implement the Codex exporter**

Create `scripts/export-codex-skill.sh` as a thin wrapper around `scripts/render-skill.py`.

Required behavior:

- render to a Codex-compatible skill folder
- emit JSON only
- include `platform`, `out_dir`, `files`, and `profile_version`
- optionally emit a suggested `AGENTS.md` fallback snippet path if the skill requests it via overlay

**Step 4: Implement the Codex compatibility checker**

Create `scripts/check-codex-compat.py` that verifies:

- valid `SKILL.md` frontmatter with `name` and `description`
- rendered directory shape matches the Codex profile
- optional `agents/openai.yaml` validates if emitted
- no unresolved tool-intent placeholders remain in rendered output

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-codex-export.py
```

Expected: PASS.

**Step 6: Update docs to reflect verified Codex support**

Add a short note in `README.md` and `docs/compatibility-matrix.md` that Codex compatibility is now determined by `check-codex-compat.py` and evidence files, not only author declaration.

**Step 7: Commit**

```bash
git add scripts/export-codex-skill.sh scripts/check-codex-compat.py scripts/test-codex-export.py README.md docs/compatibility-matrix.md
git commit -m "feat: add codex export and verification"
```

### Task 6: Add a Claude exporter and verifier

**Files:**
- Create: `scripts/export-claude-skill.sh`
- Create: `scripts/check-claude-compat.py`
- Create: `scripts/test-claude-export.py`
- Modify: `README.md`
- Create: `docs/platform-contracts/claude.md`

**Step 1: Write the failing Claude export test**

Create `scripts/test-claude-export.py` with cases like:

```python
result = run([str(repo / 'scripts' / 'export-claude-skill.sh'), '--skill-dir', str(skill_dir), '--out', str(out_dir)], cwd=repo)
payload = json.loads(result.stdout)
assert payload['platform'] == 'claude'
assert (out_dir / 'SKILL.md').is_file()
assert 'description:' in (out_dir / 'SKILL.md').read_text(encoding='utf-8')
```

If Claude-specific overlays request a command wrapper, assert the wrapper file exists.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-claude-export.py
```

Expected: FAIL because no Claude exporter or checker exists yet.

**Step 3: Implement the Claude exporter**

Create `scripts/export-claude-skill.sh` as a thin renderer wrapper.

Required behavior:

- render a Claude-compatible skill folder
- optionally render command/subagent wrappers if requested by overlay
- emit JSON with `platform`, `out_dir`, `files`, and wrapper details

**Step 4: Implement the Claude compatibility checker**

Create `scripts/check-claude-compat.py` that verifies:

- valid `SKILL.md` frontmatter
- Claude profile directory shape
- wrapper file presence when declared in overlay
- no unresolved tool-intent placeholders remain

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-claude-export.py
```

Expected: PASS.

**Step 6: Update the repository docs**

Document in `README.md` and `docs/platform-contracts/claude.md`:

- generated Claude skill output path
- how Claude support is verified
- any known degraded states during migration

**Step 7: Commit**

```bash
git add scripts/export-claude-skill.sh scripts/check-claude-compat.py scripts/test-claude-export.py README.md docs/platform-contracts/claude.md
git commit -m "feat: add claude export and verification"
```

### Task 7: Add compatibility evidence and regenerate the compatibility catalog from verification

**Files:**
- Create: `scripts/compatibility_evidence_lib.py`
- Create: `scripts/test-compatibility-evidence.py`
- Create: `catalog/compatibility-evidence/.gitkeep`
- Modify: `scripts/build-catalog.sh`
- Modify: `catalog/compatibility.json`
- Modify: `scripts/validate-registry.py`
- Modify: `schemas/ai-index.schema.json`

**Step 1: Write the failing evidence test**

Create `scripts/test-compatibility-evidence.py` with fixtures that simulate:

- author-declared support for all three platforms
- verified support only for OpenClaw and Codex

Expected shape:

```python
catalog = json.loads((repo / 'catalog' / 'compatibility.json').read_text())
entry = catalog['skills'][0]
assert entry['declared_support'] == ['claude', 'codex', 'openclaw']
assert entry['verified_support']['codex']['state'] == 'adapted'
assert entry['verified_support']['claude']['state'] == 'unknown'
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-compatibility-evidence.py
```

Expected: FAIL because the compatibility catalog currently comes only from `_meta.json.agent_compatible`.

**Step 3: Implement compatibility evidence helpers**

Add `scripts/compatibility_evidence_lib.py` with functions shaped like:

```python
def write_compatibility_evidence(path: Path, payload: dict) -> None:
    ...


def load_compatibility_evidence(root: Path) -> list[dict]:
    ...


def merge_declared_and_verified_support(skill_entry: dict, evidence: list[dict]) -> dict:
    ...
```

**Step 4: Regenerate `catalog/compatibility.json` from evidence**

Update `scripts/build-catalog.sh` so the compatibility export contains both:

- `declared_support`
- `verified_support`

while preserving backward-compatible top-level stage counts during the transition.

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-compatibility-evidence.py
```

Expected: PASS.

**Step 6: Rebuild catalogs and inspect the result**

Run:

```bash
scripts/build-catalog.sh
python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('catalog/compatibility.json').read_text())
print(payload.keys())
PY
```

Expected: output includes the new compatibility structure.

**Step 7: Commit**

```bash
git add scripts/compatibility_evidence_lib.py scripts/test-compatibility-evidence.py catalog/compatibility-evidence/.gitkeep scripts/build-catalog.sh scripts/validate-registry.py schemas/ai-index.schema.json catalog/compatibility.json
git commit -m "feat: derive compatibility catalog from verification evidence"
```

### Task 8: Add platform contract-watch docs and CI wiring

**Files:**
- Create: `docs/platform-contracts/claude.md`
- Create: `docs/platform-contracts/codex.md`
- Create: `docs/platform-contracts/openclaw.md`
- Create: `scripts/check-platform-contracts.py`
- Create: `scripts/test-platform-contracts.py`
- Modify: `scripts/check-all.sh`
- Modify: `README.md`

**Step 1: Write the failing contract-watch test**

Create `scripts/test-platform-contracts.py` with assertions like:

```python
run([sys.executable, str(repo / 'scripts' / 'check-platform-contracts.py')], cwd=repo)
```

and document fixtures that fail when:

- a platform contract doc is missing
- a contract doc lacks `Last verified date`
- a referenced upstream URL is missing from the document

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-platform-contracts.py
```

Expected: FAIL because the docs and script do not exist yet.

**Step 3: Add the contract docs**

Each document must contain these headings exactly:

```md
# Claude Platform Contract
## Stable assumptions
## Volatile assumptions
## Official sources
## Last verified
## Verification steps
## Known gaps
```

Use the equivalent title for Codex and OpenClaw.

**Step 4: Implement the contract checker**

Create `scripts/check-platform-contracts.py` to verify:

- all three contract docs exist
- all required headings are present
- the “Last verified” date parses
- each doc contains at least one HTTPS source URL
- optional freshness warning if the date is older than the configured threshold

Support flags:

```bash
python3 scripts/check-platform-contracts.py --max-age-days 30
```

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-platform-contracts.py
```

Expected: PASS.

**Step 6: Wire the new checks into the main validation flow**

Update `scripts/check-all.sh` to run all new focused tests in this order:

```bash
python3 scripts/test-canonical-contracts.py
python3 scripts/test-canonical-skill.py
python3 scripts/test-render-skill.py
python3 scripts/test-openclaw-export.py
python3 scripts/test-codex-export.py
python3 scripts/test-claude-export.py
python3 scripts/test-compatibility-evidence.py
python3 scripts/test-platform-contracts.py
```

Also add a small `README.md` section documenting the new compatibility pipeline.

**Step 7: Run the full compatibility-focused validation pass**

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

**Step 8: Commit**

```bash
git add docs/platform-contracts/claude.md docs/platform-contracts/codex.md docs/platform-contracts/openclaw.md scripts/check-platform-contracts.py scripts/test-platform-contracts.py scripts/check-all.sh README.md
git commit -m "feat: add platform contract watch and CI coverage"
```

## Handoff notes

- Prefer implementing Tasks 1-4 before touching catalog generation, because OpenClaw currently has the strongest runtime/export surface in this repository.
- Do not mark Claude or Codex as verified-compatible until their checker scripts and evidence files exist.
- If a platform lacks a capability required by a skill, write `degraded` or `unsupported` evidence rather than weakening the checker.
- Keep generated platform outputs out of author-edited source folders.
- If implementation reveals that JSON canonical metadata is too restrictive, update the design doc in a follow-up task rather than silently switching to YAML mid-stream.
