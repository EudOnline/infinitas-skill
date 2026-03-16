# Decision Metadata Canonicalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce duplicated decision metadata handling by introducing one canonical helper path from `_meta.json` into generated indexes and AI-facing consumer outputs, and document that canonical source clearly.

**Architecture:** Add a small shared Python helper for decision metadata normalization and field projection, then refactor `ai_index_lib.py`, `discovery_index_lib.py`, `search_inspect_lib.py`, and `recommend_skill_lib.py` to use it instead of manually copying the same fields. Keep the surface contract additive and unchanged wherever possible, then update docs to state `_meta.json` is the canonical author-owned source and downstream indexes or wrappers mirror it.

**Tech Stack:** Python 3.11 helper libraries, current `scripts/test-*.py` regression style, generated JSON catalog flows, and Markdown docs.

---

## Preconditions

- Work in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`.
- Use `@superpowers:test-driven-development` before each production change.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep 12-08 narrow:
  - do not change recommendation ordering; 12-07 already handled comparative signals
  - do not rename existing decision metadata fields
  - do not broaden into the stable usage guide; that belongs to 12-09

## Scope decisions

- Recommended approach: centralize normalization and field projection in one helper module rather than duplicating field copies in multiple surfaces.
- Recommended approach: preserve current output shapes while reducing repeated logic and clarifying canonical ownership in docs.
- Rejected approach: move decision metadata out of `_meta.json`, because the author-owned source is already established.
- Rejected approach: solve 12-08 with docs only, because there is clear code duplication across indexes and consumer outputs today.

### Task 1: Add failing canonical decision-metadata coverage

**Files:**
- Create: `scripts/test-decision-metadata-lib.py`
- Modify: `scripts/test-recommend-docs.py`

**Step 1: Add helper-level failing tests**

Create `scripts/test-decision-metadata-lib.py` with focused cases that assert a shared helper can:

- normalize `_meta.json` decision metadata into one stable dict
- sanitize string arrays for `use_when`, `avoid_when`, `capabilities`, and `runtime_assumptions`
- preserve `maturity` and `quality_score`
- project the same field set back out of AI/discovery entries for search, recommend, and inspect surfaces

**Step 2: Add docs-level failing assertions**

Extend `scripts/test-recommend-docs.py` so the docs explicitly mention:

- `_meta.json` as the canonical source of decision metadata
- generated indexes and AI wrappers mirroring those fields

**Step 3: Run focused tests to verify RED**

Run:

```bash
python3 scripts/test-decision-metadata-lib.py
python3 scripts/test-recommend-docs.py
```

Expected: FAIL because the helper does not exist yet and the docs do not yet describe the canonical source clearly.

### Task 2: Implement the shared decision-metadata helper and refactor consumers

**Files:**
- Create: `scripts/decision_metadata_lib.py`
- Modify: `scripts/ai_index_lib.py`
- Modify: `scripts/discovery_index_lib.py`
- Modify: `scripts/search_inspect_lib.py`
- Modify: `scripts/recommend_skill_lib.py`
- Modify: `scripts/test-search-inspect.py`
- Modify: `scripts/test-recommend-skill.py`

**Step 1: Implement the helper**

Create a helper with narrow, reusable functions such as:

- normalize author-source metadata from `_meta.json`
- project decision metadata fields from generated entries
- apply consistent defaults for `maturity` and `quality_score`

The helper should own the stable field list:

- `use_when`
- `avoid_when`
- `capabilities`
- `runtime_assumptions`
- `maturity`
- `quality_score`

**Step 2: Refactor generated indexes and consumer surfaces**

Update:

- `scripts/ai_index_lib.py` to source canonical metadata through the helper
- `scripts/discovery_index_lib.py` to project the same helper-owned fields
- `scripts/search_inspect_lib.py` to build search results and inspect `decision_metadata` from the helper
- `scripts/recommend_skill_lib.py` to reuse the same field projection for recommendation results

Keep external behavior stable unless a test clearly requires a small additive improvement.

**Step 3: Re-run focused and existing regression tests**

Run:

```bash
python3 scripts/test-decision-metadata-lib.py
python3 scripts/test-search-inspect.py
python3 scripts/test-recommend-skill.py
```

Expected: PASS.

### Task 3: Document the canonical source clearly

**Files:**
- Modify: `docs/ai/recommend.md`
- Modify: `docs/ai/search-and-inspect.md`
- Modify: `docs/metadata-schema.md`

**Step 1: Update docs**

Document that:

- `_meta.json` is the canonical author-owned source for decision metadata
- generated AI/discovery indexes mirror those fields for stable consumer workflows
- search, recommend, and inspect outputs should be treated as projections of the same canonical metadata, not separate authored copies

**Step 2: Re-run docs checks**

Run:

```bash
python3 scripts/test-recommend-docs.py
python3 scripts/test-search-docs.py
```

Expected: PASS.

### Task 4: Final verification and commit

**Step 1: Run the final 12-08 regression set**

Run:

```bash
python3 scripts/test-decision-metadata-lib.py
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
python3 scripts/test-recommend-docs.py
python3 scripts/test-search-docs.py
python3 scripts/test-ai-workflow-drills.py
python3 scripts/test-install-by-name.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-publish.py
git diff --check
```

Expected: PASS.

**Step 2: Commit**

```bash
git add docs/ai/recommend.md docs/ai/search-and-inspect.md docs/metadata-schema.md \
  docs/plans/2026-03-16-decision-metadata-canonicalization.md \
  scripts/decision_metadata_lib.py scripts/ai_index_lib.py scripts/discovery_index_lib.py \
  scripts/search_inspect_lib.py scripts/recommend_skill_lib.py \
  scripts/test-decision-metadata-lib.py scripts/test-recommend-docs.py
git commit -m "refactor: centralize decision metadata handling"
```
