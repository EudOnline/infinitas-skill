# Skill Recommendation Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an AI-usable recommendation layer that can rank and justify skill choices using explicit metadata, compatibility evidence, trust state, and verification freshness.

**Architecture:** Build on the existing `catalog/discovery-index.json`, `catalog/ai-index.json`, `search-skills.sh`, and explain-style install surfaces instead of inventing a new backend. Extend generated catalog fields with recommendation metadata, add a small Python recommendation library plus a thin CLI wrapper, then document and test a stable “search vs recommend vs inspect” consumer workflow.

**Tech Stack:** Bash CLI wrappers, Python 3.11 helper libraries, generated JSON catalogs, current regression style in `scripts/test-*.py`, and Markdown docs.

---

## Preconditions

- Work in a dedicated worktree.
- Use `@superpowers:test-driven-development` for every behavior change.
- Use `@superpowers:verification-before-completion` before each completion claim or commit.
- Keep recommendation outputs additive; do not rename or break existing search / resolve / install fields.
- Preserve the current safety contract:
  - private registry still outranks external registries
  - external-only matches still require confirmation to install
  - recommendation must not bypass immutable release verification

## Scope decisions

- Recommendation quality should come from explicit metadata and verification history, not fuzzy installation shortcuts.
- Phase 6 should focus on recommendation and decision support, not new hosted control-plane machinery.
- `search-skills.sh` remains the broad filter command; `recommend-skill.sh` is the ranked “best fit” command.
- The first version should rank deterministically using a small set of explicit factors:
  - private vs external source
  - exact / alias / summary match strength
  - target-agent compatibility
  - trust state
  - maturity
  - quality score
  - verification freshness

### Task 1: Add failing recommendation coverage

**Files:**
- Create: `scripts/test-recommend-skill.py`
- Reference: `scripts/search_inspect_lib.py`
- Reference: `scripts/discovery_index_lib.py`
- Reference: `scripts/discovery_resolver_lib.py`
- Reference: `catalog/discovery-index.json`

**Step 1: Write the failing test**

Create `scripts/test-recommend-skill.py` with focused scenarios that:

- run `scripts/recommend-skill.sh "operate in this repo" --target-agent codex`
- expect a single top recommendation containing:
  - `qualified_name`
  - `score`
  - `recommendation_reason`
  - `ranking_factors`
  - `trust_state`
  - `verified_support`
- seed at least one lower-quality or external candidate in a temp repo and assert the private, higher-quality match wins
- assert external-only recommendation results still include `install_requires_confirmation: true`
- assert the response never includes raw skill source filesystem paths

Use assertion shapes like:

```python
payload = json.loads(run(['./scripts/recommend-skill.sh', 'operate in this repo', '--target-agent', 'codex'], cwd=ROOT).stdout)
results = payload.get('results') or []
if not results:
    fail('expected at least one recommendation result')
top = results[0]
for key in ['qualified_name', 'score', 'recommendation_reason', 'ranking_factors']:
    if key not in top:
        fail(f'missing recommendation field {key!r}')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-recommend-skill.py
```

Expected: FAIL because `scripts/recommend-skill.sh` and its ranking logic do not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-recommend-skill.py
git commit -m "test: add recommendation coverage"
```

### Task 2: Extend generated catalog fields for ranking

**Files:**
- Modify: `scripts/ai_index_lib.py`
- Modify: `scripts/discovery_index_lib.py`
- Modify: `scripts/test-ai-index.py`
- Modify: `scripts/test-discovery-index.py`
- Reference: `catalog/compatibility.json`
- Reference: `catalog/compatibility-evidence/`

**Step 1: Write the failing catalog assertions**

Extend `scripts/test-ai-index.py` and `scripts/test-discovery-index.py` so they assert generated recommendation surfaces include:

- `maturity`
- `quality_score`
- `last_verified_at`
- `capabilities`

Also assert:

- `last_verified_at` is derived from the newest verified-support timestamp when evidence exists
- these fields stay stable for both local and hosted-backed discovery generation

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
```

Expected: FAIL because recommendation metadata is not generated yet.

**Step 3: Implement the minimal metadata generation**

Update `scripts/ai_index_lib.py` so each skill entry includes:

- `maturity`
- `quality_score`
- `capabilities`
- `last_verified_at`

Implementation guidance:

- read `maturity`, `quality_score`, and `capabilities` from `_meta.json` if present
- default conservatively when metadata is absent
- derive `last_verified_at` from the newest `checked_at` value in `verified_support`

Update `scripts/discovery_index_lib.py` so normalized discovery entries carry the same fields for ranking without reopening the AI index.

**Step 4: Re-run the focused tests**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/ai_index_lib.py scripts/discovery_index_lib.py scripts/test-ai-index.py scripts/test-discovery-index.py catalog/ai-index.json catalog/discovery-index.json
git commit -m "feat: expose recommendation metadata in generated catalogs"
```

### Task 3: Implement `recommend-skill.sh` and ranking helpers

**Files:**
- Create: `scripts/recommend_skill_lib.py`
- Create: `scripts/recommend-skill.sh`
- Modify: `scripts/test-recommend-skill.py`
- Reference: `scripts/search_inspect_lib.py`
- Reference: `scripts/discovery_index_lib.py`

**Step 1: Implement the failing behavior first**

Keep `scripts/test-recommend-skill.py` focused on:

- deterministic top result ordering
- stable JSON shape
- target-agent filtering
- external confirmation visibility

Do not broaden the test before the first minimal ranking implementation passes.

**Step 2: Implement the minimal recommendation library**

Create `scripts/recommend_skill_lib.py` with helpers like:

```python
def recommend_skills(root: Path, task: str, target_agent: str | None = None, limit: int = 5) -> dict:
    ...

def rank_recommendation(item: dict, *, task: str, target_agent: str | None) -> tuple:
    ...
```

Initial ranking order should be deterministic and explicit:

1. private registry over external registry
2. target-agent compatible entries over incompatible ones
3. query hit in `name` / `qualified_name` / `tags` / `use_when` / `capabilities`
4. higher `trust_state`
5. higher `maturity`
6. higher `quality_score`
7. newer `last_verified_at`

Each result should include:

- `qualified_name`
- `publisher`
- `summary`
- `source_registry`
- `latest_version`
- `trust_state`
- `verified_support`
- `install_requires_confirmation`
- `score`
- `recommendation_reason`
- `ranking_factors`

**Step 3: Add the thin shell wrapper**

Create `scripts/recommend-skill.sh` supporting:

- free-text task description
- `--target-agent`
- `--limit`
- `--json` default behavior

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-recommend-skill.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/recommend_skill_lib.py scripts/recommend-skill.sh scripts/test-recommend-skill.py
git commit -m "feat: add skill recommendation command"
```

### Task 4: Add explanation-friendly recommendation output

**Files:**
- Modify: `scripts/recommend_skill_lib.py`
- Modify: `scripts/recommend-skill.sh`
- Modify: `scripts/test-recommend-skill.py`

**Step 1: Write the failing explanation assertions**

Extend `scripts/test-recommend-skill.py` so the top result must include a machine-readable explanation shape:

- `recommendation_reason`
- `ranking_factors.match_strength`
- `ranking_factors.compatibility`
- `ranking_factors.trust`
- `ranking_factors.quality`
- `ranking_factors.verification_freshness`

Also assert the response contains a top-level `explanation` section that states why the first result outranked the next result.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-recommend-skill.py
```

Expected: FAIL because the first implementation will likely have only basic ranking output.

**Step 3: Implement additive explanation fields**

Update `scripts/recommend_skill_lib.py` so the payload includes:

- per-result `recommendation_reason`
- per-result `ranking_factors`
- top-level `explanation` summarizing the winner

Keep the output additive and stable for machine consumers.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-recommend-skill.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/recommend_skill_lib.py scripts/recommend-skill.sh scripts/test-recommend-skill.py
git commit -m "feat: explain recommendation ranking"
```

### Task 5: Document search vs recommend vs inspect

**Files:**
- Modify: `README.md`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/ai/search-and-inspect.md`
- Create: `docs/ai/recommend.md`
- Create: `scripts/test-recommend-docs.py`

**Step 1: Write the failing doc test**

Create `scripts/test-recommend-docs.py` that asserts docs mention:

- `scripts/recommend-skill.sh`
- how recommendation differs from `scripts/search-skills.sh`
- recommendation explanation output
- recommendation factors such as trust state, compatibility, maturity, and verification freshness

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-recommend-docs.py
```

Expected: FAIL because recommendation docs do not exist yet.

**Step 3: Update the docs**

Document:

- when to use `search-skills.sh`
- when to use `recommend-skill.sh`
- when to use `inspect-skill.sh`
- how to read `recommendation_reason` and `ranking_factors`

Include examples such as:

```bash
scripts/recommend-skill.sh "Need a codex skill for repository operations"
scripts/recommend-skill.sh "Need an OpenClaw publishing helper" --target-agent openclaw
scripts/search-skills.sh operate --agent codex
scripts/inspect-skill.sh lvxiaoer/operate-infinitas-skill
```

**Step 4: Re-run the doc test**

Run:

```bash
python3 scripts/test-recommend-docs.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/ai/discovery.md docs/ai/search-and-inspect.md docs/ai/recommend.md scripts/test-recommend-docs.py
git commit -m "docs: add recommendation workflow guidance"
```

### Task 6: Wire recommendation coverage into `check-all.sh`

**Files:**
- Modify: `scripts/check-all.sh`
- Create: `scripts/test-check-all-phase6.py`

**Step 1: Write the failing coverage test**

Create `scripts/test-check-all-phase6.py` that asserts `scripts/check-all.sh` runs:

- `python3 scripts/test-recommend-skill.py`
- `python3 scripts/test-recommend-docs.py`

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-check-all-phase6.py
```

Expected: FAIL because the new tests are not wired in yet.

**Step 3: Update the full validation entrypoint**

Modify `scripts/check-all.sh` so the new recommendation tests run in the AI-wrapper / doc contract sections, matching the current Phase 5 pattern.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-check-all-phase6.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/check-all.sh scripts/test-check-all-phase6.py
git commit -m "test: run recommendation coverage in check-all"
```

### Task 7: Run final Phase 6 verification

**Files:**
- No new files expected

**Step 1: Run the focused recommendation checks**

Run:

```bash
python3 scripts/test-recommend-skill.py
python3 scripts/test-recommend-docs.py
python3 scripts/test-check-all-phase6.py
```

Expected: PASS.

**Step 2: Run the full repository verification**

Run:

```bash
scripts/check-all.sh
```

Expected: PASS, except the existing hosted E2E dependency skip remains acceptable if the Python environment still lacks `fastapi/httpx/jinja2/sqlalchemy`.

**Step 3: Inspect final worktree state**

Run:

```bash
git status --short
git log --oneline -6
```

Expected:

- only the intended Phase 6 files changed
- the commit stack is clean and Phase 6 commits are easy to review independently

**Step 4: Decide branch completion flow**

After verification, use `@superpowers:finishing-a-development-branch` to decide whether to keep stacking commits, squash for merge, or open a PR.
