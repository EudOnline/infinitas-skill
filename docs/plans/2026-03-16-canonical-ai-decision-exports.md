# Canonical AI Decision Metadata Exports Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Export the new AI decision metadata from `_meta.json` into canonical AI/discovery indexes and surface it through search, inspect, and recommendation outputs.

**Architecture:** Keep `_meta.json` as the single author-owned source of truth. Extend `scripts/ai_index_lib.py` to extract the new decision fields, let `scripts/discovery_index_lib.py` forward them without recomputing author intent, and update search/inspect/recommend output layers to expose the fields that agents actually need for selection. Keep the change additive and file-backed by reusing the existing generated-index pipeline instead of adding another metadata store.

**Tech Stack:** Python catalog builders, Bash CLI wrappers, JSON schemas, Markdown docs, and focused regression tests under `scripts/test-*.py`.

---

## Preconditions

- Work in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep 12-02 focused on canonical export and surface behavior:
  - do not add new ranking heuristics yet
  - do not add new real skills yet
  - do not revisit wrapper result schema work from 12-01

## Scope decisions

- Recommended approach: export `use_when`, `avoid_when`, `capabilities`, and `runtime_assumptions` from `ai_index_lib.py`, then let discovery and downstream surfaces consume those canonical fields.
- Recommended approach: update `search`, `inspect`, and `recommend` outputs so callers can see the decision metadata without reopening raw catalogs.
- Recommended approach: treat `runtime_assumptions` as a surfaced field, even though it is not yet used in ranking, because it affects install/use suitability and should travel with decision metadata.
- Rejected approach: re-read `_meta.json` independently inside search/recommend helpers, because that would create a second source of truth outside generated indexes.
- Rejected approach: add ranking changes in the same slice, because 12-03 already owns comparative ranking refinements.

### Task 1: Add failing coverage for canonical decision metadata export

**Files:**
- Modify: `scripts/test-ai-index.py`
- Modify: `scripts/test-discovery-index.py`
- Modify: `scripts/test-search-inspect.py`
- Modify: `scripts/test-recommend-skill.py`

**Step 1: Extend fixture metadata with decision fields**

Update the fixture `_meta.json` payloads in the tests so they include:

```python
'use_when': ['Need to operate inside this repository'],
'avoid_when': ['Need unrelated public publishing help'],
'runtime_assumptions': ['A local repo checkout is available'],
```

Keep existing `capabilities`, `maturity`, and `quality_score` coverage.

**Step 2: Assert the exported/indexed values**

Add assertions that:

- `catalog/ai-index.json` contains `use_when`, `avoid_when`, and `runtime_assumptions`
- `catalog/discovery-index.json` contains the same fields for local and external fixtures
- `search-skills.sh` results expose the new decision metadata
- `inspect-skill.sh` returns a decision-metadata view
- `recommend-skill.sh` results expose the canonical metadata used for selection

**Step 3: Run the focused tests to verify RED**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
python3 scripts/test-search-inspect.py
python3 scripts/test-recommend-skill.py
```

Expected: FAIL because the canonical export path still drops or hides the new metadata.

### Task 2: Implement canonical exports and surface the metadata

**Files:**
- Modify: `scripts/ai_index_lib.py`
- Modify: `scripts/discovery_index_lib.py`
- Modify: `scripts/search_inspect_lib.py`
- Modify: `scripts/recommend_skill_lib.py`
- Modify: `schemas/ai-index.schema.json`
- Modify: `schemas/discovery-index.schema.json`
- Modify: `docs/ai/search-and-inspect.md`
- Modify: `docs/ai/recommend.md`

**Step 1: Export the fields from `_meta.json` into `ai-index`**

Add helper extraction in `scripts/ai_index_lib.py` for:

- `use_when`
- `avoid_when`
- `runtime_assumptions`

Then emit them into each skill entry using the canonical `_meta.json` values rather than hardcoded empty arrays.

**Step 2: Carry the fields into discovery and user-facing outputs**

Update `scripts/discovery_index_lib.py` to normalize and validate `runtime_assumptions` alongside the already-forwarded decision fields.

Update `scripts/search_inspect_lib.py` so:

- search results include `use_when`, `avoid_when`, `capabilities`, `runtime_assumptions`, `maturity`, and `quality_score`
- inspect results include a `decision_metadata` object with the canonical fields

Update `scripts/recommend_skill_lib.py` so recommendation results expose:

- `use_when`
- `avoid_when`
- `capabilities`
- `runtime_assumptions`
- `maturity`
- `quality_score`

Do not change ranking math yet; only surface the metadata already used or relevant to selection.

**Step 3: Extend schema validation**

Update `schemas/ai-index.schema.json` and `schemas/discovery-index.schema.json` plus the in-code validators so the new `runtime_assumptions` arrays are part of the stable contract.

**Step 4: Update operator/agent docs**

Refresh `docs/ai/search-and-inspect.md` and `docs/ai/recommend.md` so they mention the new decision fields and how callers should interpret them.

**Step 5: Re-run the focused tests to verify GREEN**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
python3 scripts/test-search-inspect.py
python3 scripts/test-recommend-skill.py
```

Expected: PASS.

### Task 3: Final verification and commit

**Step 1: Run the full 12-02 verification set**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
python3 scripts/test-search-inspect.py
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-docs.py
python3 scripts/test-recommend-docs.py
git diff --check
```

Expected: PASS.

**Step 2: Commit**

```bash
git add docs/plans/2026-03-16-canonical-ai-decision-exports.md \
  docs/ai/search-and-inspect.md docs/ai/recommend.md \
  schemas/ai-index.schema.json schemas/discovery-index.schema.json \
  scripts/ai_index_lib.py scripts/discovery_index_lib.py scripts/search_inspect_lib.py scripts/recommend_skill_lib.py \
  scripts/test-ai-index.py scripts/test-discovery-index.py scripts/test-search-inspect.py scripts/test-recommend-skill.py
git commit -m "feat: export canonical AI decision metadata"
```
