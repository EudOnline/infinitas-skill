# Search Discovery And Consumer UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the registry easier to consume by adding explicit search and inspect commands, clearer install and upgrade explanations, and docs that treat verified distribution as the default consumer path.

**Architecture:** Reuse the generated `catalog/ai-index.json`, `catalog/discovery-index.json`, install manifests, and verified distribution manifests as the only discovery and explanation sources. Add thin CLI wrappers plus small Python helpers that expose search, inspect, and explain views without introducing a new backend, then thread those stable views through install, update, and upgrade flows so policy decisions become inspectable instead of implicit.

**Tech Stack:** Bash CLI wrappers, Python 3.11 helper libraries, JSON catalogs and install manifests, existing discovery/install scripts, existing regression style in `scripts/test-*.py`, Markdown docs.

---

### Task 1: Add failing coverage for search and inspect commands

**Files:**
- Create: `scripts/test-search-inspect.py`
- Create: `scripts/search-skills.sh`
- Create: `scripts/inspect-skill.sh`
- Reference: `scripts/resolve-skill.sh`
- Reference: `scripts/discovery_resolver_lib.py`
- Reference: `catalog/discovery-index.json`
- Reference: `catalog/ai-index.json`

**Step 1: Write the failing test**

Create `scripts/test-search-inspect.py` with focused scenarios that:

- run `scripts/search-skills.sh operate`
- expect results to include:
  - `qualified_name`
  - `publisher`
  - `latest_version`
  - `trust_state`
  - `verified_support`
- run `scripts/search-skills.sh --publisher lvxiaoer --agent codex`
- expect filtering to narrow results without scraping raw file paths
- run `scripts/inspect-skill.sh lvxiaoer/operate-infinitas-skill`
- expect stable JSON containing:
  - compatibility summary
  - dependency summary
  - release provenance refs
  - distribution manifest refs
  - trust state

Use simple assertion shapes like:

```python
result = run(['./scripts/search-skills.sh', 'operate'], cwd=ROOT)
payload = json.loads(result.stdout)
if not payload.get('results'):
    fail('expected at least one search result')
first = payload['results'][0]
for key in ['qualified_name', 'latest_version', 'trust_state']:
    if key not in first:
        fail(f'missing search field {key}')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-search-inspect.py
```

Expected: FAIL because `search-skills.sh` and `inspect-skill.sh` do not exist yet.

**Step 3: Commit**

```bash
git add scripts/test-search-inspect.py
git commit -m "test: add search and inspect coverage"
```

### Task 2: Add catalog fields for tags, compatibility, publisher, and trust state

**Files:**
- Modify: `scripts/ai_index_lib.py`
- Modify: `scripts/discovery_index_lib.py`
- Modify: `scripts/build-catalog.sh`
- Modify: `scripts/test-ai-index.py`
- Modify: `scripts/test-discovery-index.py`
- Reference: `catalog/compatibility.json`
- Reference: `catalog/distributions.json`

**Step 1: Write the failing catalog assertions**

Extend `scripts/test-ai-index.py` and `scripts/test-discovery-index.py` so they assert generated search surfaces include:

- `publisher`
- `tags`
- `compatibility.verified_support`
- `trust_state`
- `attestation_formats`
- `distribution_manifest_path`

Also assert the data is stable for both local and hosted-backed discovery generation.

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
```

Expected: FAIL because the current generated entries do not yet expose all consumer-facing search and trust fields.

**Step 3: Extend AI index generation**

Update `scripts/ai_index_lib.py` so each skill entry includes:

- `publisher`
- `tags`
- `trust_state`
- per-version `attestation_formats`
- per-version `distribution_manifest_path`
- compatibility data shaped for direct CLI consumption

Keep the current immutable-install policy contract unchanged.

**Step 4: Extend discovery index generation**

Update `scripts/discovery_index_lib.py` so normalized discovery entries carry:

- `publisher`
- `tags`
- `trust_state`
- `verified_support`
- `attestation_formats`

This lets search work without opening the AI index separately for every result.

**Step 5: Re-run the focused tests**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/ai_index_lib.py scripts/discovery_index_lib.py scripts/test-ai-index.py scripts/test-discovery-index.py
git commit -m "feat: expose search and trust fields in generated catalogs"
```

### Task 3: Implement `search-skills.sh` and `inspect-skill.sh`

**Files:**
- Create: `scripts/search_inspect_lib.py`
- Create: `scripts/search-skills.sh`
- Create: `scripts/inspect-skill.sh`
- Modify: `scripts/test-search-inspect.py`
- Reference: `scripts/discovery_resolver_lib.py`
- Reference: `scripts/installed_skill_lib.py`

**Step 1: Implement a search/inspect helper library**

Create `scripts/search_inspect_lib.py` with helpers like:

```python
def search_skills(root: Path, query: str | None, publisher: str | None, agent: str | None, tag: str | None) -> dict:
    ...

def inspect_skill(root: Path, qualified_name: str) -> dict:
    ...
```

Behavior:

- search reads the generated discovery index
- inspect reads the AI index plus distribution metadata
- both return stable JSON, not raw internal file formats

**Step 2: Add thin shell wrappers**

Create `scripts/search-skills.sh` supporting:

- free-text query
- `--publisher`
- `--agent`
- `--tag`
- `--json` default behavior

Create `scripts/inspect-skill.sh` supporting:

- qualified or unique unqualified names
- `--version`
- `--json` default behavior

**Step 3: Re-run the new command tests**

Run:

```bash
python3 scripts/test-search-inspect.py
```

Expected: PASS.

**Step 4: Commit**

```bash
git add scripts/search_inspect_lib.py scripts/search-skills.sh scripts/inspect-skill.sh scripts/test-search-inspect.py
git commit -m "feat: add registry search and inspect commands"
```

### Task 4: Add explain-style install and upgrade output

**Files:**
- Create: `scripts/explain_install_lib.py`
- Modify: `scripts/resolve-skill.sh`
- Modify: `scripts/install-by-name.sh`
- Modify: `scripts/check-skill-update.sh`
- Modify: `scripts/upgrade-skill.sh`
- Modify: `scripts/pull-skill.sh`
- Create: `scripts/test-explain-install.py`

**Step 1: Write the failing explanation test**

Create `scripts/test-explain-install.py` with scenarios that:

- resolve a private match and expect an explanation payload containing:
  - why this skill won
  - which registry was used
  - whether confirmation is required
  - which version was chosen
- resolve an external match and expect `policy_reasons`
- run `check-skill-update.sh` and expect an `explanation` section for update availability
- run `upgrade-skill.sh --mode confirm` and expect a plan describing:
  - from version
  - to version
  - why cross-source upgrades are blocked

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-explain-install.py
```

Expected: FAIL because current outputs are concise state payloads without explicit decision traces.

**Step 3: Implement shared explanation helpers**

Create `scripts/explain_install_lib.py` that can build explanation fragments like:

- `selection_reason`
- `policy_reasons`
- `version_reason`
- `next_actions`

Keep the output additive so existing machine consumers are not broken.

**Step 4: Thread explanations through CLI outputs**

Update the resolver and install/upgrade scripts so they include:

- `explanation`
- `policy_reasons`
- `selection_reason`
- `version_reason`

Prefer payload additions over state renames.

**Step 5: Re-run the focused test**

Run:

```bash
python3 scripts/test-explain-install.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/explain_install_lib.py scripts/resolve-skill.sh scripts/install-by-name.sh scripts/check-skill-update.sh scripts/upgrade-skill.sh scripts/pull-skill.sh scripts/test-explain-install.py
git commit -m "feat: explain install and upgrade decisions"
```

### Task 5: Expose inspectable trust, compatibility, and dependency views

**Files:**
- Modify: `scripts/search_inspect_lib.py`
- Modify: `scripts/inspect-skill.sh`
- Modify: `scripts/test-search-inspect.py`
- Modify: `scripts/test-distribution-install.py`
- Reference: `catalog/provenance/`
- Reference: `catalog/distributions/`

**Step 1: Write the failing inspect-detail assertions**

Extend `scripts/test-search-inspect.py` so `inspect-skill.sh` must expose:

- dependency root and steps summary
- release provenance path
- attestation formats
- distribution manifest path
- verified compatibility summary per platform
- trust state derived from manifest and attestation policy

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-search-inspect.py
```

Expected: FAIL because inspect output is still too shallow.

**Step 3: Expand inspect output**

Update `scripts/search_inspect_lib.py` and `scripts/inspect-skill.sh` so inspect output includes a stable top-level structure like:

```json
{
  "qualified_name": "lvxiaoer/operate-infinitas-skill",
  "latest_version": "0.1.1",
  "compatibility": {...},
  "distribution": {...},
  "provenance": {...},
  "dependencies": {...},
  "trust_state": "verified"
}
```

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-search-inspect.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/search_inspect_lib.py scripts/inspect-skill.sh scripts/test-search-inspect.py scripts/test-distribution-install.py
git commit -m "feat: add inspectable trust and dependency views"
```

### Task 6: Update docs so verified distribution is the default consumer experience

**Files:**
- Modify: `README.md`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/ai/pull.md`
- Modify: `docs/ai/agent-operations.md`
- Create: `docs/ai/search-and-inspect.md`
- Create: `scripts/test-search-docs.py`

**Step 1: Write the failing doc test**

Create `scripts/test-search-docs.py` that asserts docs mention:

- `scripts/search-skills.sh`
- `scripts/inspect-skill.sh`
- explain-style resolver/install output
- verified distribution manifests as the default consumer path
- trust state, compatibility, and provenance inspection

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-search-docs.py
```

Expected: FAIL because Phase 5 consumer docs do not exist yet.

**Step 3: Update user-facing docs**

Document:

- how to search by query, publisher, agent, and tag
- how to inspect a skill before install
- how install and upgrade explanations should be read
- why verified distributions, not working-tree folders, are the default consumer path

Include concrete command examples such as:

```bash
scripts/search-skills.sh operate
scripts/search-skills.sh --publisher lvxiaoer --agent codex
scripts/inspect-skill.sh lvxiaoer/operate-infinitas-skill
scripts/install-by-name.sh operate-infinitas-skill ~/.openclaw/skills --mode confirm
```

**Step 4: Re-run the doc test**

Run:

```bash
python3 scripts/test-search-docs.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/ai/discovery.md docs/ai/pull.md docs/ai/agent-operations.md docs/ai/search-and-inspect.md scripts/test-search-docs.py
git commit -m "docs: add search and consumer UX guidance"
```

### Task 7: Run final Phase 5 verification

**Files:**
- Reference: `scripts/test-search-inspect.py`
- Reference: `scripts/test-ai-index.py`
- Reference: `scripts/test-discovery-index.py`
- Reference: `scripts/test-explain-install.py`
- Reference: `scripts/test-distribution-install.py`
- Reference: `scripts/test-search-docs.py`

**Step 1: Run the focused Phase 5 suite**

Run:

```bash
python3 scripts/test-search-inspect.py
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
python3 scripts/test-explain-install.py
python3 scripts/test-distribution-install.py
python3 scripts/test-search-docs.py
```

Expected: PASS.

**Step 2: Run broader regression**

Run:

```bash
scripts/check-all.sh
```

Expected: PASS.

**Step 3: Commit final cleanups**

```bash
git add .
git commit -m "feat: complete v10 phase 5 consumer ux"
```
