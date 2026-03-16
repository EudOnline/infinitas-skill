# Platform Usage Guide Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish one stable human/agent usage guide that explains when to search, recommend, inspect, publish, pull, and verify without opening implementation internals.

**Architecture:** Add a new `docs/ai/usage-guide.md` as the top-level workflow entrypoint, then wire README and `docs/ai/agent-operations.md` to treat it as the stable guide while keeping the existing protocol documents as deeper references. Keep this slice documentation-first, with regression tests that assert the guide exists, is discoverable, and explicitly maps user intent to the correct wrapper commands.

**Tech Stack:** Markdown docs and the existing `scripts/test-*.py` documentation regression style.

---

## Preconditions

- Work in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`.
- Use `@superpowers:test-driven-development` for documentation behavior changes too: add failing docs assertions first.
- Use `@superpowers:verification-before-completion` before claiming completion or committing.
- Keep 12-09 narrow:
  - do not redesign command behavior
  - do not duplicate the full protocol from discovery / publish / pull docs
  - do not replace `agent-operations.md`; this guide should sit above it as a stable entrypoint

## Scope decisions

- Recommended approach: create one short, stable guide that says when to use each public command, then link to deeper protocol docs.
- Recommended approach: keep the guide readable by both humans and agents, with concrete intent-to-command mappings and confirm-first reminders.
- Rejected approach: rely on `agent-operations.md` alone, because it mixes decision guidance with detailed operational workflows and is not yet positioned as the single stable entrypoint.
- Rejected approach: copy full protocol details into the guide, because that would create another duplication hotspot immediately after 12-08.

### Task 1: Add failing docs coverage for the stable usage guide

**Files:**
- Create: `scripts/test-usage-guide-docs.py`
- Modify: `scripts/test-search-docs.py`

**Step 1: Add the new docs test**

Create `scripts/test-usage-guide-docs.py` asserting:

- `docs/ai/usage-guide.md` exists
- it explicitly mentions when to:
  - `search`
  - `recommend`
  - `inspect`
  - `publish`
  - `pull`
  - `verify`
- it references the public wrapper commands rather than internal implementation files

**Step 2: Extend the existing docs discovery test**

Update `scripts/test-search-docs.py` so README or `agent-operations.md` must point readers to the new usage guide.

**Step 3: Run focused tests to verify RED**

Run:

```bash
python3 scripts/test-usage-guide-docs.py
python3 scripts/test-search-docs.py
```

Expected: FAIL because the new guide does not exist yet.

### Task 2: Publish the stable usage guide and wire entrypoints

**Files:**
- Create: `docs/ai/usage-guide.md`
- Modify: `docs/ai/agent-operations.md`
- Modify: `README.md`

**Step 1: Write the guide**

The guide should clearly answer:

- when to use `scripts/search-skills.sh`
- when to use `scripts/recommend-skill.sh`
- when to use `scripts/inspect-skill.sh`
- when to use `scripts/publish-skill.sh`
- when to use `scripts/pull-skill.sh`
- when to use `scripts/check-skill.sh` or `scripts/check-all.sh` to verify

It should also document:

- confirm-first defaults
- inspect-before-install or publish
- stop conditions that require human confirmation
- links to deeper docs for discovery, recommend, publish, pull, and workflow drills

**Step 2: Wire the stable entrypoint**

Update `README.md` and `docs/ai/agent-operations.md` so they present `docs/ai/usage-guide.md` as the stable high-level guide and position `agent-operations.md` / protocol docs as deeper references.

**Step 3: Re-run focused docs tests**

Run:

```bash
python3 scripts/test-usage-guide-docs.py
python3 scripts/test-search-docs.py
python3 scripts/test-recommend-docs.py
```

Expected: PASS.

### Task 3: Final verification and commit

**Step 1: Run the final 12-09 docs regression set**

Run:

```bash
python3 scripts/test-usage-guide-docs.py
python3 scripts/test-search-docs.py
python3 scripts/test-recommend-docs.py
python3 scripts/test-ai-workflow-drills.py
git diff --check
```

Expected: PASS.

**Step 2: Commit**

```bash
git add README.md docs/ai/usage-guide.md docs/ai/agent-operations.md \
  docs/plans/2026-03-16-platform-usage-guide.md \
  scripts/test-usage-guide-docs.py scripts/test-search-docs.py
git commit -m "docs: add stable platform usage guide"
```
