# AI Decision Metadata and Result Contracts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make AI-facing skill selection metadata and wrapper JSON contracts first-class so the registry can explain what a skill is for and keep `publish-skill` / `pull-skill` outputs schema-stable.

**Architecture:** Extend canonical author metadata in `_meta.json` and the skill templates to hold decision-useful fields already expected by AI surfaces, then teach the focused validators to enforce those fields instead of allowing silent drift. Keep the work file-backed and dependency-free by adding dedicated JSON schema files plus repo-local validation helpers and tests rather than introducing a new runtime dependency.

**Tech Stack:** Bash wrapper scripts, Python validation helpers, JSON schemas, Markdown docs, and existing AI protocol regression tests.

---

## Preconditions

- Work in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep 12-01 focused on canonical metadata and contract validation:
  - do not add new recommendation heuristics yet
  - do not add new real skills yet
  - do not add hosted services or background refresh automation

## Scope decisions

- Recommended approach: treat AI decision metadata as source-of-truth author metadata, not hand-maintained catalog-only fields.
- Recommended approach: keep new decision guidance fields simple and shell-friendly:
  - arrays of short strings for `use_when`, `avoid_when`, `capabilities`, and `runtime_assumptions`
  - integer `quality_score`
  - free-form `maturity` string until a tighter enum is justified by multiple real skills
- Recommended approach: add dedicated result schemas for the stable JSON emitted on stdout by `publish-skill.sh` and `pull-skill.sh`, plus regression tests that validate real command output against those schemas.
- Rejected approach: invent a second AI metadata file outside `_meta.json`, because it would duplicate author intent and make generated indexes harder to trust.
- Rejected approach: add `jsonschema` as a runtime dependency, because the repo currently relies on lightweight Python validators and schema files primarily for contract clarity plus CI/editor integration.

### Task 1: Add failing coverage for AI decision metadata validation

**Files:**
- Modify: `scripts/test-skill-meta-compat.py`
- Reference: `scripts/validate-registry.py`
- Reference: `scripts/check-skill.sh`

**Step 1: Extend the compatibility test with valid AI decision metadata**

Add a scenario that writes the new fields into `templates/basic-skill/_meta.json` and expects validation success:

```python
payload['maturity'] = 'stable'
payload['quality_score'] = 88
payload['capabilities'] = ['repo-operations', 'release-guidance']
payload['use_when'] = ['Need to operate inside the infinitas-skill repository']
payload['avoid_when'] = ['Need a general-purpose public publishing workflow']
payload['runtime_assumptions'] = ['Git checkout is available', 'Repository scripts may be executed']
write_json(meta_path, payload)
run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
```

**Step 2: Add a failing-type scenario**

Add a second scenario that proves the current validators are too loose until implementation lands:

```python
payload['use_when'] = 'Need repo operations'
write_json(meta_path, payload)
result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
combined = result.stdout + result.stderr
if 'use_when' not in combined:
    fail(f'expected validation failure mentioning use_when\\n{combined}')
```

Repeat the same pattern for one non-string list member or an out-of-range `quality_score`.

**Step 3: Run the focused test to prove it fails before implementation**

Run:

```bash
python3 scripts/test-skill-meta-compat.py
```

Expected: FAIL because the new bad-type scenario is not rejected yet.

### Task 2: Extend the metadata validators and schema

**Files:**
- Modify: `schemas/skill-meta.schema.json`
- Modify: `scripts/validate-registry.py`
- Modify: `scripts/check-skill.sh`

**Step 1: Add the new schema properties**

Extend `schemas/skill-meta.schema.json` with:

- `maturity`: non-empty string
- `quality_score`: integer, `0-100`
- `capabilities`: array of non-empty strings
- `use_when`: array of non-empty strings
- `avoid_when`: array of non-empty strings
- `runtime_assumptions`: array of non-empty strings

Keep the properties optional so legacy skills continue to validate.

**Step 2: Mirror the same rules in the hand-rolled validators**

In both `scripts/validate-registry.py` and `scripts/check-skill.sh`, add explicit checks that:

- each list field is an array of non-empty strings
- `quality_score` is an integer between `0` and `100`
- `maturity` is a non-empty string when present

Use clear failure messages such as:

```python
fail(f'{skill_dir}: use_when must be an array of non-empty strings')
```

and:

```python
print('FAIL: quality_score must be an integer between 0 and 100', file=sys.stderr)
```

**Step 3: Re-run the focused compatibility test**

Run:

```bash
python3 scripts/test-skill-meta-compat.py
```

Expected: PASS.

### Task 3: Update templates, the example skill, and metadata docs

**Files:**
- Modify: `templates/basic-skill/_meta.json`
- Modify: `templates/scripted-skill/_meta.json`
- Modify: `templates/reference-heavy-skill/_meta.json`
- Modify: `skills/active/operate-infinitas-skill/_meta.json`
- Modify: `docs/metadata-schema.md`

**Step 1: Add the new fields to templates**

Add the optional fields to each template with safe starter defaults:

```json
"maturity": "prototype",
"quality_score": 0,
"capabilities": [],
"use_when": [],
"avoid_when": [],
"runtime_assumptions": []
```

Keep the templates honest: use empty arrays for guidance fields instead of fake text.

**Step 2: Populate the shipped example skill with meaningful guidance**

Update `skills/active/operate-infinitas-skill/_meta.json` with concrete decision metadata such as:

```json
"maturity": "stable",
"quality_score": 90,
"capabilities": [
  "repo-operations",
  "release-guidance",
  "registry-debugging"
],
"use_when": [
  "Need to operate inside the infinitas-skill repository",
  "Need guidance on registry workflows, planning files, or release discipline"
],
"avoid_when": [
  "Need a general-purpose Git helper outside this repository"
],
"runtime_assumptions": [
  "A Git checkout of infinitas-skill is available",
  "Repository scripts can be executed from the workspace"
]
```

**Step 3: Document the new authoring contract**

Update `docs/metadata-schema.md` so the example shape and field notes explain:

- what each new field means
- that they drive AI selection and recommendation surfaces
- that empty arrays are allowed but weaken selection quality

**Step 4: Run focused verification**

Run:

```bash
scripts/check-skill.sh skills/active/operate-infinitas-skill
python3 scripts/validate-registry.py
```

Expected: PASS.

### Task 4: Add result schemas and validate publish/pull outputs

**Files:**
- Create: `schemas/publish-result.schema.json`
- Create: `schemas/pull-result.schema.json`
- Create: `scripts/result_schema_lib.py`
- Modify: `scripts/test-ai-publish.py`
- Modify: `scripts/test-ai-pull.py`
- Modify: `docs/ai/publish.md`
- Modify: `docs/ai/pull.md`

**Step 1: Add failing schema-validation assertions to the AI wrapper tests**

Teach `scripts/test-ai-publish.py` and `scripts/test-ai-pull.py` to validate the real command JSON against helper functions from `scripts/result_schema_lib.py`.

Use a shape like:

```python
from result_schema_lib import validate_publish_result, validate_pull_result

errors = validate_publish_result(payload)
if errors:
    fail('publish result schema errors:\\n' + '\\n'.join(errors))
```

and the pull equivalent.

**Step 2: Implement schema files and lightweight validators**

Add dedicated schema files that describe the stable stdout JSON for:

- preview publish output (`state: planned`)
- successful publish output (`ok: true`, `state: published`)
- successful pull output (`ok: true`, `state: installed`)
- failure payload fields that are already part of the stable contract

Mirror those shapes in `scripts/result_schema_lib.py` with dependency-free validators, following the same style as `scripts/ai_index_lib.py` and `scripts/discovery_index_lib.py`.

**Step 3: Document the schemas in the AI protocol docs**

Update `docs/ai/publish.md` and `docs/ai/pull.md` to point readers at the new schema files and clarify that stable integration consumers should validate stdout JSON against them.

**Step 4: Run focused verification**

Run:

```bash
python3 scripts/test-ai-publish.py
python3 scripts/test-ai-pull.py
```

Expected: PASS.

### Task 5: Final verification and commit

**Step 1: Run the Phase 1 focused regression set**

Run:

```bash
python3 scripts/test-skill-meta-compat.py
python3 scripts/test-ai-index.py
python3 scripts/test-ai-publish.py
python3 scripts/test-ai-pull.py
git diff --check
```

Expected: PASS with no diff-format errors.

**Step 2: Commit**

```bash
git add schemas/skill-meta.schema.json schemas/publish-result.schema.json schemas/pull-result.schema.json \
  scripts/validate-registry.py scripts/check-skill.sh scripts/result_schema_lib.py \
  scripts/test-skill-meta-compat.py scripts/test-ai-index.py scripts/test-ai-publish.py scripts/test-ai-pull.py \
  templates/basic-skill/_meta.json templates/scripted-skill/_meta.json templates/reference-heavy-skill/_meta.json \
  skills/active/operate-infinitas-skill/_meta.json docs/metadata-schema.md docs/ai/publish.md docs/ai/pull.md
git commit -m "feat: add AI decision metadata contracts"
```
