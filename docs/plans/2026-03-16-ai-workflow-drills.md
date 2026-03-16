# AI Workflow Drills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add AI-only workflow drills so agents can complete realistic search, recommend, inspect, publish, and pull flows using the stable AI docs and generated JSON surfaces instead of repository internals.

**Architecture:** Reuse the existing public AI-facing docs and wrapper commands as the contract surface, then add one dedicated drill document plus regression scripts that exercise those workflows in confirm-mode or fixture repos. Keep the drills protocol-focused: assert command choice, required output fields, and stop conditions without requiring direct reads from `skills/active/`, `skills/incubating/`, or implementation-only helper modules.

**Tech Stack:** Markdown AI docs, Python script-style regression tests, existing wrapper commands, existing result-schema validators, and temporary fixture repos for publish/pull rehearsals.

---

## Preconditions

- Work in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`.
- Use `@superpowers:test-driven-development` before each production change.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep 12-05 focused on learnability and public protocol drills:
  - do not add ranking heuristic changes; that belongs to 12-07
  - do not add missing-artifact or ambiguous-resolution failure-path suites; that belongs to 12-06
  - do not add hosted-service orchestration beyond the current file-backed wrapper flows

## Scope decisions

- Recommended approach: add one explicit workflow-drill manual under `docs/ai/` and one end-to-end drill regression script that only uses documented wrapper commands and stable JSON outputs.
- Recommended approach: exercise `publish` and `pull` through `--mode confirm` in docs-level drills unless a fixture release is already required for realistic coverage.
- Recommended approach: keep search/recommend/inspect drills tied to real generated catalog state so the tests prove agents can work from actual registry content.
- Rejected approach: teach drill tests to read `skills/*` or helper-library internals directly, because 12-05 is about AI-usable public surfaces.
- Rejected approach: collapse this into prose-only doc updates, because ECO-05 requires realistic executable drills rather than descriptive guidance alone.

### Task 1: Add failing coverage for AI-only workflow drills

**Files:**
- Create: `scripts/test-ai-workflow-drills.py`
- Modify: `scripts/test-search-docs.py`
- Modify: `scripts/test-recommend-docs.py`

**Step 1: Write a failing workflow drill test**

Create `scripts/test-ai-workflow-drills.py` with scenarios that deliberately stay on the public protocol surface:

- a search drill that runs `scripts/search-skills.sh release` and asserts the top-level result exposes `qualified_name`, `use_when`, `runtime_assumptions`, and `verified_support`
- a recommend drill that runs `scripts/recommend-skill.sh "publish immutable skill release"` and asserts the result includes `recommendation_reason`, `ranking_factors`, and a real specialized skill winner
- an inspect drill that runs `scripts/inspect-skill.sh lvxiaoer/release-infinitas-skill` and asserts `decision_metadata`, `verified_distribution`, and provenance references are surfaced
- a publish drill that uses a fixture repo plus `scripts/publish-skill.sh <skill> --mode confirm` and validates the output with `validate_publish_result`
- a pull drill that uses a fixture repo plus `scripts/pull-skill.sh <qualified-name> <target-dir> --mode confirm` and validates the output with `validate_pull_result`

Use assertions like:

```python
if payload.get('state') != 'planned':
    fail(f"expected planned publish drill output, got {payload!r}")
```

and:

```python
decision = payload.get('decision_metadata') or {}
if not decision.get('use_when'):
    fail(f"expected inspect drill to expose decision metadata, got {payload!r}")
```

**Step 2: Tighten the docs checks so they describe the drill surface**

Extend the existing docs tests to require mentions of:

- `docs/ai/workflow-drills.md`
- `--mode confirm` for publish/pull drill safety
- the ordered search -> inspect -> install/pull and recommend -> inspect flows
- the rule that agents should not open implementation internals for routine workflows

**Step 3: Run the focused tests to verify RED**

Run:

```bash
python3 scripts/test-ai-workflow-drills.py
python3 scripts/test-search-docs.py
python3 scripts/test-recommend-docs.py
```

Expected: FAIL because the workflow-drill doc and the new drill expectations do not exist yet.

### Task 2: Document the AI-only drills

**Files:**
- Create: `docs/ai/workflow-drills.md`
- Modify: `docs/ai/agent-operations.md`
- Modify: `README.md`

**Step 1: Add a dedicated workflow-drill manual**

Create `docs/ai/workflow-drills.md` with five protocol drills:

- Search: `search -> inspect -> install-by-name --mode confirm`
- Recommend: `recommend -> inspect`
- Inspect-before-install: inspect trust/provenance/distribution before any mutation
- Publish: `check-skill -> request/approve if needed -> publish-skill --mode confirm`
- Pull: `pull-skill --mode confirm -> pull-skill`

Each drill should state:

- allowed public files to read first
- commands to run
- keys to inspect in the JSON output
- stop conditions where the agent must not guess

**Step 2: Link the drill manual from the existing AI docs**

Update `docs/ai/agent-operations.md` and `README.md` so they point readers to the new drill manual and make it explicit that the drill workflow should stay on documented commands plus generated JSON outputs.

**Step 3: Re-run the docs-focused tests**

Run:

```bash
python3 scripts/test-search-docs.py
python3 scripts/test-recommend-docs.py
```

Expected: PASS.

### Task 3: Implement the executable drill regression

**Files:**
- Create: `scripts/test-ai-workflow-drills.py`
- Reference: `scripts/test-ai-publish.py`
- Reference: `scripts/test-ai-pull.py`
- Reference: `scripts/result_schema_lib.py`

**Step 1: Build fixture helpers around public wrapper commands**

Reuse the same temporary-repo pattern already proven by `scripts/test-ai-publish.py` and `scripts/test-ai-pull.py`, but keep the drill script focused on workflow ordering instead of wrapper internals.

The drill script should:

- call only public wrapper commands for the workflow under test
- validate JSON output with `validate_publish_result` / `validate_pull_result` where applicable
- avoid importing private implementation libraries beyond shared schema validators

**Step 2: Make the drills assert the public protocol, not implementation details**

Examples:

- search drill checks decision metadata fields and real specialized skill names
- recommend drill checks ranking reason plus top candidate
- inspect drill checks surfaced provenance/distribution references
- publish confirm drill checks `state: planned`, `commands`, and `next_step`
- pull confirm drill checks `state: planned`, `manifest_path`, `attestation_path`, `install_command`, and `explanation`

**Step 3: Run the focused workflow-drill test**

Run:

```bash
python3 scripts/test-ai-workflow-drills.py
```

Expected: PASS.

### Task 4: Verify the drill set against the existing AI protocol suite

**Files:**
- No new files beyond Task 1-3 outputs

**Step 1: Run the focused 12-05 verification set**

Run:

```bash
python3 scripts/test-ai-workflow-drills.py
python3 scripts/test-search-docs.py
python3 scripts/test-recommend-docs.py
python3 scripts/test-ai-publish.py
python3 scripts/test-ai-pull.py
python3 scripts/test-search-inspect.py
python3 scripts/test-recommend-skill.py
```

Expected: PASS.

### Task 5: Final verification and commit

**Step 1: Run the final 12-05 regression set**

Run:

```bash
python3 scripts/test-ai-workflow-drills.py
python3 scripts/test-search-docs.py
python3 scripts/test-recommend-docs.py
python3 scripts/test-ai-publish.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-index.py
python3 scripts/test-search-inspect.py
python3 scripts/test-recommend-skill.py
git diff --check
```

Expected: PASS.

**Step 2: Commit**

```bash
git add docs/ai/workflow-drills.md docs/ai/agent-operations.md README.md \
  scripts/test-ai-workflow-drills.py scripts/test-search-docs.py scripts/test-recommend-docs.py
git commit -m "feat: add AI workflow drills"
```
