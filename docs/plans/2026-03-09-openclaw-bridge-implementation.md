# OpenClaw Bridge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `infinitas-skill` the canonical source of truth for OpenClaw-compatible skills, with a deterministic bridge for importing OpenClaw-authored skills into the registry and exporting released skills back into OpenClaw / ClawHub-compatible folders.

**Architecture:** Keep the private registry authoritative. Add a thin interoperability layer that parses and validates OpenClaw/ClawHub-style `SKILL.md` frontmatter, imports local OpenClaw skill folders into `skills/incubating/`, and exports approved registry skills from immutable release artifacts into standalone folders. Do not publish to public registries by default, and do not let AI install directly from editable source.

**Tech Stack:** Bash, Python 3.9+, existing registry scripts, generated catalogs, JSON outputs for AI wrappers.

---

## Constraints and non-goals

- The default flow stays **private + fully automatic** inside this repository.
- OpenClaw local install must continue to prefer immutable release artifacts via `scripts/pull-skill.sh`.
- Public publication to ClawHub is **explicit opt-in only** because ClawHub publish is public and MIT-0 licensed.
- Do not make OpenClaw or other agents scrape internal scripts; teach them a small contract surface instead.
- Do not add a second source of truth for skill content. `SKILL.md` + `_meta.json` remain authoritative.

## External facts this plan assumes

- OpenClaw runtime skills live under `~/.openclaw/workspace/skills/<skill>/SKILL.md`.
- ClawHub CLI installs into `<workdir>/<dir>/<slug>` and publishes with `clawhub publish <path>`.
- ClawHub `sync` scans local skill roots and can discover OpenClaw/Clawdbot skill directories.

---

### Task 1: Formalize the OpenClaw-facing contract

**Files:**
- Create: `docs/ai/openclaw.md`
- Modify: `README.md`
- Modify: `docs/ai/publish.md`
- Modify: `docs/ai/pull.md`

**Step 1: Write the contract skeleton**

Document these rules:

- OpenClaw may **read** only `README.md`, `docs/ai/openclaw.md`, `docs/ai/publish.md`, `docs/ai/pull.md`, and `catalog/ai-index.json`.
- OpenClaw-created skills must be imported into `skills/incubating/` before they can be reviewed, released, or reinstalled.
- AI must not install directly from `skills/incubating/` or `skills/active/`.
- Public ClawHub publication is optional and requires an explicit operator action.

**Step 2: Add the operator workflow**

Write the canonical lifecycle:

1. Prototype in OpenClaw local workspace.
2. Import into registry incubating state.
3. Validate and review.
4. Publish immutable private release.
5. Pull into `~/.openclaw/skills`.
6. Optionally export the released artifact for `clawhub publish`.

**Step 3: Verify docs only mention supported commands**

Run:

```bash
rg -n "import-openclaw|export-openclaw|publish-clawhub|~/.openclaw" README.md docs/ai
```

Expected:
- every command is either implemented in this plan or explicitly labeled optional/manual
- every OpenClaw path is consistent with the documented runtime model

**Step 4: Commit**

```bash
git add README.md docs/ai/openclaw.md docs/ai/publish.md docs/ai/pull.md
git commit -m "docs: define openclaw bridge contract"
```

---

### Task 2: Add import coverage first

**Files:**
- Create: `scripts/test-openclaw-import.py`
- Create: `scripts/import-openclaw-skill.sh`
- Create: `scripts/openclaw_bridge_lib.py`

**Step 1: Write the failing import test**

Cover two cases:

```python
def test_confirm_mode_returns_non_mutating_plan():
    ...

def test_auto_mode_copies_skill_into_incubating_and_scaffolds_registry_files():
    ...
```

The fixture should create a temporary OpenClaw-style folder containing only:

- `SKILL.md`
- optional support files

The expected imported output should include:

- `skills/incubating/<slug>/SKILL.md`
- `skills/incubating/<slug>/_meta.json`
- `skills/incubating/<slug>/reviews.json`
- `skills/incubating/<slug>/tests/smoke.md`

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-openclaw-import.py
```

Expected:
- FAIL because `scripts/import-openclaw-skill.sh` does not exist yet

**Step 3: Implement the minimal import path**

Add a shared library with functions shaped like:

```python
def parse_skill_frontmatter(skill_md_path: Path) -> dict:
    ...

def derive_registry_meta(frontmatter: dict, owner: str, publisher: str | None) -> dict:
    ...

def scaffold_imported_skill(source_dir: Path, target_dir: Path, meta: dict) -> dict:
    ...
```

Behavior requirements:

- accept either a direct skill folder or an installed OpenClaw skill path
- parse `name` and `description` from `SKILL.md` frontmatter
- preserve the original `SKILL.md`
- generate `_meta.json` defaults consistent with current templates
- set `status` to `incubating` and `review_state` to `draft`
- support `--mode confirm` and emit JSON only
- support `--force` for replacing an existing incubating target

**Step 4: Run the test to verify it passes**

Run:

```bash
python3 scripts/test-openclaw-import.py
```

Expected:
- PASS with both confirm and auto flows succeeding

**Step 5: Commit**

```bash
git add scripts/test-openclaw-import.py scripts/import-openclaw-skill.sh scripts/openclaw_bridge_lib.py
git commit -m "feat: import openclaw skills into registry"
```

---

### Task 3: Add released-artifact export coverage

**Files:**
- Create: `scripts/test-openclaw-export.py`
- Create: `scripts/export-openclaw-skill.sh`
- Modify: `scripts/openclaw_bridge_lib.py`

**Step 1: Write the failing export test**

Cover two cases:

```python
def test_confirm_mode_returns_release_export_plan():
    ...

def test_auto_mode_materializes_release_bundle_as_openclaw_folder():
    ...
```

The test fixture should reuse the release-oriented setup pattern already used by `scripts/test-ai-publish.py`:

- create a temporary repo
- create one approved active skill
- build catalog
- produce a released immutable distribution
- export that release into a temporary output directory

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-openclaw-export.py
```

Expected:
- FAIL because `scripts/export-openclaw-skill.sh` does not exist yet

**Step 3: Implement the minimal export path**

Expose a command with this shape:

```bash
scripts/export-openclaw-skill.sh <skill-name> --version <semver> --out <dir> [--mode confirm]
```

Behavior requirements:

- resolve the release through `catalog/ai-index.json` or distribution manifest data
- refuse export when the requested version is not installable
- materialize the exact released files into `<dir>/<skill-name>`
- emit JSON with `bundle_path`, `manifest_path`, `export_dir`, and a suggested manual `clawhub publish` command
- do **not** publish to ClawHub automatically

**Step 4: Run the test to verify it passes**

Run:

```bash
python3 scripts/test-openclaw-export.py
```

Expected:
- PASS with confirm and auto flows succeeding

**Step 5: Commit**

```bash
git add scripts/test-openclaw-export.py scripts/export-openclaw-skill.sh scripts/openclaw_bridge_lib.py
git commit -m "feat: export released skills for openclaw and clawhub"
```

---

### Task 4: Validate frontmatter and enrich the AI index

**Files:**
- Modify: `scripts/validate-registry.py`
- Modify: `scripts/build-catalog.sh`
- Modify: `scripts/ai_index_lib.py`
- Modify: `schemas/ai-index.schema.json`
- Modify: `scripts/test-ai-index.py`
- Modify: `catalog/ai-index.json`

**Step 1: Write the failing assertions first**

Add coverage for:

- `SKILL.md` frontmatter `name` matching `_meta.json.name`
- `description` existing when a skill is marked installable
- AI index emitting an explicit interop section for OpenClaw export/pull guidance

Suggested assertion shape:

```python
assert payload["skills"][0]["interop"]["openclaw"]["import_supported"] is True
assert payload["skills"][0]["interop"]["openclaw"]["export_supported"] is True
assert payload["install_policy"]["direct_source_install_allowed"] is False
```

**Step 2: Run the focused test to verify it fails**

Run:

```bash
python3 scripts/test-ai-index.py
```

Expected:
- FAIL because the new `interop.openclaw` fields are not emitted yet

**Step 3: Implement the minimal catalog/index enrichment**

Add repo-generated fields shaped like:

```json
{
  "interop": {
    "openclaw": {
      "runtime_targets": [
        "~/.openclaw/skills",
        "~/.openclaw/workspace/skills"
      ],
      "import_supported": true,
      "export_supported": true,
      "public_publish": {
        "clawhub": {
          "supported": true,
          "default": false
        }
      }
    }
  }
}
```

Validation rules:

- frontmatter name and `_meta.json.name` must match
- missing frontmatter should fail validation for installable skills
- AI index must keep immutable-only policy unchanged

**Step 4: Rebuild and rerun**

Run:

```bash
scripts/build-catalog.sh
python3 scripts/test-ai-index.py
python3 scripts/validate-registry.py
```

Expected:
- AI index regenerates cleanly
- index tests pass
- registry validation passes

**Step 5: Commit**

```bash
git add scripts/validate-registry.py scripts/build-catalog.sh scripts/ai_index_lib.py schemas/ai-index.schema.json scripts/test-ai-index.py catalog/ai-index.json
git commit -m "feat: expose openclaw interop in ai index"
```

---

### Task 5: Integrate with the full verification suite and handoff docs

**Files:**
- Modify: `scripts/check-all.sh`
- Modify: `README.md`
- Modify: `docs/platform-review-memo.md`

**Step 1: Add the new tests to the suite**

Run these in `scripts/check-all.sh` after the current AI wrapper checks:

```bash
python3 scripts/test-openclaw-import.py
python3 scripts/test-openclaw-export.py
```

**Step 2: Document the safe operator handoff**

Update `README.md` with two explicit workflows:

- **Private default:** OpenClaw prototype → import → review → release → `scripts/pull-skill.sh`
- **Public optional:** export released folder → manual `clawhub publish <export-dir>`

Also update `docs/platform-review-memo.md` so the roadmap tracks bridge readiness instead of only abstract interoperability.

**Step 3: Run the full verification suite**

Run:

```bash
./scripts/check-all.sh
```

Expected:
- exit code 0
- final output includes `OK: full registry check passed`

**Step 4: Commit**

```bash
git add scripts/check-all.sh README.md docs/platform-review-memo.md
git commit -m "test: verify openclaw bridge end to end"
```

---

## Execution order

Implement Tasks 2 → 3 → 4 first, because the bridge behavior needs tests before the public-facing docs are finalized. Then do Tasks 1 and 5 to align the operator/AI contract with the tested behavior.

## Definition of done

The feature is complete when all of the following are true:

- an OpenClaw-authored local skill can be imported into `skills/incubating/` deterministically
- a released registry skill can be exported into a standalone OpenClaw/ClawHub-compatible folder
- `catalog/ai-index.json` tells an AI exactly how to import, export, and pull without allowing direct source installs
- `README.md` makes the private-default and public-optional split unambiguous
- `./scripts/check-all.sh` passes from a clean checkout

## Recommended first execution slice

Start with Task 2 only. It gives the platform the missing ingest path from OpenClaw into the private registry, which is the biggest blocker to making the repo genuinely useful as an AI-operated skill home.
