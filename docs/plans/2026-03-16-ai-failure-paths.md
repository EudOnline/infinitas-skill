# AI Failure Paths Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add wrapper-level failure-path regression coverage for ambiguous resolution and missing immutable artifacts so AI-facing install workflows fail with actionable structured output instead of raw internal payloads or vague command errors.

**Architecture:** Reuse the existing AI-facing wrapper commands as the contract surface, then tighten `install-by-name.sh` and `pull-skill.sh` around the failure states most likely to affect agents: ambiguous names, incompatible matches, missing released versions, and missing distribution files. Keep the implementation additive by mapping these failure conditions into stable JSON payloads with `error_code`, `message`, `suggested_action`, and explanation fields instead of redesigning resolver internals.

**Tech Stack:** Bash wrapper scripts, Python script-style regression tests, existing `result_schema_lib.py`, generated indexes, and Markdown AI docs.

---

## Preconditions

- Work in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`.
- Use `@superpowers:test-driven-development` before each production change.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep 12-06 focused on failure-path learnability:
  - do not add ranking changes; that belongs to 12-07
  - do not add new real skills; 12-04 already covered that
  - do not add new result schema files unless a wrapper contract is already clearly stable

## Scope decisions

- Recommended approach: strengthen AI-facing failure outputs where agents already operate today: `install-by-name.sh`, `pull-skill.sh`, and the related docs/tests.
- Recommended approach: treat ambiguous or incompatible resolution as wrapper-level failures with explicit next actions, rather than forwarding raw `resolve-skill.sh` payloads unchanged.
- Recommended approach: keep missing immutable artifact coverage at the `pull-skill.sh` level because that is where AI install policy is enforced.
- Rejected approach: rewrite `resolve-skill.sh` itself into a failure envelope, because 12-06 is about AI wrapper learnability, not low-level resolver contract churn.
- Rejected approach: broaden this slice into all possible hosted/federation errors, because the milestone only requires ambiguous names, wrong versions, and missing immutable artifacts to be actionable.

### Task 1: Add failing wrapper-level coverage for ambiguous resolution and missing artifacts

**Files:**
- Modify: `scripts/test-install-by-name.py`
- Modify: `scripts/test-ai-pull.py`
- Modify: `scripts/test-ai-workflow-drills.py`

**Step 1: Add failing `install-by-name` cases**

Extend `scripts/test-install-by-name.py` so it asserts:

- an ambiguous short name returns a structured failure payload with:
  - `ok: false`
  - `state: failed`
  - `error_code: ambiguous-skill-name`
  - actionable `suggested_action`
- an incompatible target-agent request returns a structured failure payload with:
  - `error_code: incompatible-target-agent`
  - explanation fields that describe why no compatible candidate won

**Step 2: Add failing `pull-skill` missing-artifact coverage**

Extend `scripts/test-ai-pull.py` with scenarios where the selected version is present in `ai-index.json`, but:

- `manifest_path` points to a missing file
- `bundle_path` points to a missing file
- `attestation_path` points to a missing file

Assert each returns a structured failure payload with:

- `ok: false`
- `state: failed`
- `failed_at_step: verified_manifest`
- `error_code: missing-distribution-file`
- field-specific `message`
- actionable `suggested_action`

**Step 3: Add a workflow-drill failure check**

Extend `scripts/test-ai-workflow-drills.py` with one failure drill showing that ambiguous install-by-name calls do not guess silently and instead return actionable JSON.

**Step 4: Run the focused tests to verify RED**

Run:

```bash
python3 scripts/test-install-by-name.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-workflow-drills.py
```

Expected: FAIL because ambiguous install-by-name still forwards raw resolver payloads and the new missing-artifact assertions are not yet covered.

### Task 2: Implement actionable wrapper failures

**Files:**
- Modify: `scripts/install-by-name.sh`
- Modify: `scripts/pull-skill.sh`
- Modify: `scripts/explain_install_lib.py`

**Step 1: Wrap resolver failures in `install-by-name.sh`**

When `resolve-skill.sh` returns `ambiguous`, `not-found`, `incompatible`, or `failed`, convert that into a structured wrapper failure payload that includes:

- `ok: false`
- `query`
- `qualified_name` when available
- `state: failed`
- `error_code`
- `message`
- `suggested_action`
- `requires_confirmation`
- `next_step`
- `explanation`

Use stable mappings such as:

- `ambiguous` -> `ambiguous-skill-name`
- `not-found` -> `skill-not-found`
- `incompatible` -> `incompatible-target-agent`

**Step 2: Keep `pull-skill.sh` failure output specific and actionable**

Ensure missing immutable artifact failures remain structured and field-specific, including which artifact is missing and a consistent repair action like republish/rebuild.

If needed, normalize the existing messages so tests can assert predictable output across manifest, bundle, and attestation failures.

**Step 3: Improve explanation helpers for failure states**

Update `scripts/explain_install_lib.py` so wrapper failure payloads can carry clear `selection_reason`, `policy_reasons`, and `next_actions` for:

- ambiguous short names
- incompatible agent filters
- missing immutable artifact enforcement

**Step 4: Re-run the focused failure-path tests**

Run:

```bash
python3 scripts/test-install-by-name.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-workflow-drills.py
```

Expected: PASS.

### Task 3: Document the failure-path contract for agents

**Files:**
- Modify: `docs/ai/discovery.md`
- Modify: `docs/ai/pull.md`
- Modify: `docs/ai/workflow-drills.md`

**Step 1: Document actionable failure handling**

Update the AI docs to say:

- ambiguous short names must stop and ask for a qualified name
- incompatible agent requests must stop and report compatibility mismatch
- missing immutable artifacts must stop and suggest rebuild/republish, never fallback to mutable source folders

Keep the docs aligned with the actual wrapper `error_code` names and `suggested_action` language.

**Step 2: Re-run docs and drill tests**

Run:

```bash
python3 scripts/test-search-docs.py
python3 scripts/test-ai-workflow-drills.py
```

Expected: PASS.

### Task 4: Final verification and commit

**Step 1: Run the final 12-06 regression set**

Run:

```bash
python3 scripts/test-install-by-name.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-workflow-drills.py
python3 scripts/test-search-inspect.py
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-docs.py
python3 scripts/test-ai-publish.py
git diff --check
```

Expected: PASS.

**Step 2: Commit**

```bash
git add docs/ai/discovery.md docs/ai/pull.md docs/ai/workflow-drills.md \
  scripts/install-by-name.sh scripts/pull-skill.sh scripts/explain_install_lib.py \
  scripts/test-install-by-name.py scripts/test-ai-pull.py scripts/test-ai-workflow-drills.py
git commit -m "feat: harden AI workflow failure paths"
```
