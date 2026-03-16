# Real Skill Inventory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multiple real registry-managed skills with distinct decision metadata, local release artifacts, and verified compatibility evidence so recommendation and discovery become meaningfully comparative.

**Architecture:** Reuse the existing basic skill template and the proven `operate-infinitas-skill` structure, but split the current all-in-one operator guidance into three narrower active skills: one for releasing immutable versions, one for discovering and installing released skills, and one for federation or audit operations. Keep `_meta.json` as the author-owned source of truth, produce local signed release artifacts with `scripts/release-skill.sh` plus `scripts/build-catalog.sh`, and record verified compatibility evidence so the generated indexes can rank real alternatives without inventing synthetic fixture content.

**Tech Stack:** Bash skill scaffolding and lifecycle scripts, Markdown skill instructions, `_meta.json` metadata, `reviews.json`, `catalog/compatibility-evidence/*`, generated `catalog/*.json`, and focused regression tests under `scripts/test-*.py`.

---

## Preconditions

- Work in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`.
- Keep v12 focused on AI ecosystem usefulness; do not add hosted services or ranking math changes here.
- Do not use `scripts/publish-skill.sh` for new branch-local skills in this slice, because it always requests `--push-tag`. Use local signed release commands that produce immutable artifacts without mutating the remote.
- Reuse the same skill style and contract shape already proven by `skills/active/operate-infinitas-skill`.

## Scope Decisions

- Recommended skill set:
  - `lvxiaoer/release-infinitas-skill` for validate/review/promote/release work
  - `lvxiaoer/consume-infinitas-skill` for search/recommend/inspect/pull/install or upgrade work
  - `lvxiaoer/federation-registry-ops` for registry-source, mirror, federation, and audit-export operations
- Recommended quality bar: each new skill must have non-empty `capabilities`, `use_when`, `avoid_when`, and `runtime_assumptions`, plus at least Codex and Claude compatibility evidence and a real release artifact in `catalog/distributions/...`.
- Rejected approach: add more synthetic fixture entries to `catalog/ai-index.json`, because 12-04 is explicitly about real registry skill inventory.
- Rejected approach: keep one giant `operate-infinitas-skill` and only tweak metadata, because recommendation needs multiple distinct choices with narrower applicability.

### Task 1: Add failing inventory and ranking coverage

**Files:**
- Create: `scripts/test-real-skill-inventory.py`
- Modify: `scripts/test-recommend-skill.py`
- Modify: `scripts/test-search-inspect.py`

**Step 1: Write the failing inventory test**

Create `scripts/test-real-skill-inventory.py` with assertions like:

```python
EXPECTED = {
    'lvxiaoer/operate-infinitas-skill',
    'lvxiaoer/release-infinitas-skill',
    'lvxiaoer/consume-infinitas-skill',
    'lvxiaoer/federation-registry-ops',
}

for qualified_name in EXPECTED:
    entry = entries_by_name[qualified_name]
    assert entry['use_when']
    assert entry['avoid_when']
    assert entry['runtime_assumptions']
    assert entry['capabilities']
    assert entry['verified_support']
```

**Step 2: Add comparative recommendation assertions**

Extend the existing recommendation/search tests so they expect:

```python
assert recommend('publish immutable release')['results'][0]['qualified_name'] == 'lvxiaoer/release-infinitas-skill'
assert recommend('install released skill')['results'][0]['qualified_name'] == 'lvxiaoer/consume-infinitas-skill'
assert recommend('debug federated registry')['results'][0]['qualified_name'] == 'lvxiaoer/federation-registry-ops'
```

Also assert search results expose these new real skills by name and publisher.

**Step 3: Run the focused tests to verify RED**

Run:

```bash
python3 scripts/test-real-skill-inventory.py
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
```

Expected: FAIL because the repository currently contains only `lvxiaoer/operate-infinitas-skill`.

### Task 2: Scaffold and author the release-focused skill

**Files:**
- Create: `skills/incubating/release-infinitas-skill/*`

**Step 1: Scaffold from the basic template**

Run:

```bash
scripts/new-skill.sh lvxiaoer/release-infinitas-skill basic
```

**Step 2: Replace template metadata**

Set `_meta.json` to include:

```json
{
  "publisher": "lvxiaoer",
  "qualified_name": "lvxiaoer/release-infinitas-skill",
  "summary": "Guide agents through validation, review, promotion, and immutable release of infinitas-skill registry skills.",
  "tags": ["release", "registry", "publishing"],
  "agent_compatible": ["codex", "claude", "claude-code"],
  "maturity": "stable",
  "quality_score": 88,
  "capabilities": ["skill-validation", "promotion", "immutable-release", "verified-support-recording"],
  "use_when": [
    "Need to validate or release a registry-managed skill",
    "Need to refresh immutable artifacts before others can install a skill"
  ],
  "avoid_when": [
    "Need to install a released skill into a runtime directory",
    "Need only search or inspect existing releases"
  ],
  "runtime_assumptions": [
    "A writable infinitas-skill repository checkout is available",
    "Signing configuration and allowed signers are already set up"
  ]
}
```

**Step 3: Write `SKILL.md`**

Cover:

- release lifecycle order: validate -> request review -> approve -> promote -> release -> build catalog -> record verified support
- when to use `scripts/check-skill.sh`, `scripts/request-review.sh`, `scripts/approve-skill.sh`, `scripts/promote-skill.sh`, `scripts/release-skill.sh`, and `scripts/record-verified-support.py`
- confirm-first and no-remote-push guidance for branch-local release rehearsal

**Step 4: Add `tests/smoke.md` and `CHANGELOG.md`**

Smoke scenario should mention a request like “publish a stable version other agents can pull.”

### Task 3: Scaffold and author the discovery/install-focused skill

**Files:**
- Create: `skills/incubating/consume-infinitas-skill/*`

**Step 1: Scaffold from the basic template**

Run:

```bash
scripts/new-skill.sh lvxiaoer/consume-infinitas-skill basic
```

**Step 2: Replace template metadata**

Set `_meta.json` to include:

```json
{
  "publisher": "lvxiaoer",
  "qualified_name": "lvxiaoer/consume-infinitas-skill",
  "summary": "Guide agents through search, recommendation, inspection, pull, install, and upgrade flows for released infinitas-skill artifacts.",
  "tags": ["discovery", "install", "upgrade"],
  "agent_compatible": ["openclaw", "codex", "claude", "claude-code"],
  "maturity": "stable",
  "quality_score": 89,
  "capabilities": ["search", "recommend", "inspect", "immutable-install", "upgrade-planning"],
  "use_when": [
    "Need to find the best released skill for a task",
    "Need to inspect or install a stable released skill"
  ],
  "avoid_when": [
    "Need to create a new release from source",
    "Need to debug registry federation or mirror policy"
  ],
  "runtime_assumptions": [
    "Generated catalog indexes are present or can be rebuilt",
    "Target runtime directories such as ~/.openclaw/skills are writable when install is requested"
  ]
}
```

**Step 3: Write `SKILL.md`**

Cover:

- `scripts/search-skills.sh`, `scripts/recommend-skill.sh`, `scripts/inspect-skill.sh`
- `scripts/install-by-name.sh`, `scripts/pull-skill.sh`, `scripts/check-skill-update.sh`, `scripts/upgrade-skill.sh`
- immutable-only install rules and confirm-first guidance

**Step 4: Add `tests/smoke.md` and `CHANGELOG.md`**

Smoke scenario should mention a request like “find the right skill and install the stable version into OpenClaw.”

### Task 4: Scaffold and author the federation or audit operations skill

**Files:**
- Create: `skills/incubating/federation-registry-ops/*`

**Step 1: Scaffold from the basic template**

Run:

```bash
scripts/new-skill.sh lvxiaoer/federation-registry-ops basic
```

**Step 2: Replace template metadata**

Set `_meta.json` to include:

```json
{
  "publisher": "lvxiaoer",
  "qualified_name": "lvxiaoer/federation-registry-ops",
  "summary": "Help agents inspect registry sources, federation rules, mirror behavior, and audit or inventory exports inside infinitas-skill.",
  "tags": ["federation", "audit", "registry-sources"],
  "agent_compatible": ["codex", "claude", "claude-code"],
  "maturity": "beta",
  "quality_score": 84,
  "capabilities": ["registry-source-debugging", "federation-policy", "inventory-export", "audit-export"],
  "use_when": [
    "Need to debug registry source, mirror, or federation behavior",
    "Need to inspect inventory or audit export artifacts"
  ],
  "avoid_when": [
    "Need to publish a new release",
    "Need to install a skill into a runtime directory"
  ],
  "runtime_assumptions": [
    "config/registry-sources.json and generated catalog exports are available",
    "The task is about registry operations inside infinitas-skill rather than a generic Git repo"
  ]
}
```

**Step 3: Write `SKILL.md`**

Cover:

- registry source inspection and trust debugging
- `catalog/inventory-export.json` and `catalog/audit-export.json`
- relevant docs such as `docs/federation-operations.md`, `docs/ai/discovery.md`, and `docs/ai/search-and-inspect.md`

**Step 4: Add `tests/smoke.md` and `CHANGELOG.md`**

Smoke scenario should mention a request like “why is a federated skill not showing up or why does audit export disagree with pull output?”

### Task 5: Review, promote, release, and record verified support

**Files:**
- Modify: `skills/active/release-infinitas-skill/*`
- Modify: `skills/active/consume-infinitas-skill/*`
- Modify: `skills/active/federation-registry-ops/*`
- Create: `catalog/compatibility-evidence/claude/release-infinitas-skill/<version>.json`
- Create: `catalog/compatibility-evidence/codex/release-infinitas-skill/<version>.json`
- Create: `catalog/compatibility-evidence/claude/consume-infinitas-skill/<version>.json`
- Create: `catalog/compatibility-evidence/codex/consume-infinitas-skill/<version>.json`
- Create: `catalog/compatibility-evidence/openclaw/consume-infinitas-skill/<version>.json`
- Create: `catalog/compatibility-evidence/claude/federation-registry-ops/<version>.json`
- Create: `catalog/compatibility-evidence/codex/federation-registry-ops/<version>.json`
- Modify: `catalog/ai-index.json`
- Modify: `catalog/discovery-index.json`
- Modify: `catalog/compatibility.json`
- Modify: `catalog/catalog.json`
- Modify: `catalog/active.json`
- Modify: `catalog/distributions.json`

**Step 1: Request review and approve each skill**

Run for each new skill:

```bash
scripts/request-review.sh <skill> --note "12-04 real skill inventory"
scripts/approve-skill.sh <skill> --reviewer lvxiaoer --note "Approve 12-04 registry skill"
scripts/promote-skill.sh <skill>
```

**Step 2: Produce local immutable release artifacts without remote pushes**

Run for each promoted skill:

```bash
scripts/release-skill.sh <skill> --create-tag --write-provenance
scripts/build-catalog.sh
```

Do not use `scripts/publish-skill.sh` in this branch-local slice because it requests `--push-tag`.

**Step 3: Record verified support**

Run:

```bash
python3 scripts/record-verified-support.py release-infinitas-skill --platform codex --platform claude --build-catalog
python3 scripts/record-verified-support.py consume-infinitas-skill --platform codex --platform claude --platform openclaw --build-catalog
python3 scripts/record-verified-support.py federation-registry-ops --platform codex --platform claude --build-catalog
```

**Step 4: Re-run focused tests to verify GREEN**

Run:

```bash
python3 scripts/test-real-skill-inventory.py
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
python3 scripts/test-operate-infinitas-skill.py
```

Expected: PASS.

### Task 6: Final verification and commit

**Step 1: Run the broader 12-04 verification set**

Run:

```bash
python3 scripts/test-real-skill-inventory.py
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
python3 scripts/test-operate-infinitas-skill.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-publish.py
git diff --check
```

**Step 2: Commit**

```bash
git add docs/plans/2026-03-16-real-skill-inventory.md \
  skills/active/release-infinitas-skill skills/active/consume-infinitas-skill skills/active/federation-registry-ops \
  catalog/compatibility-evidence catalog/catalog.json catalog/active.json catalog/compatibility.json \
  catalog/distributions.json catalog/ai-index.json catalog/discovery-index.json \
  scripts/test-real-skill-inventory.py scripts/test-recommend-skill.py scripts/test-search-inspect.py
git commit -m "feat: add real registry skill inventory"
```
