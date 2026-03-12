# Operate infinitas-skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a shared registry skill that teaches OpenClaw, Codex, and Claude Code how to operate inside this repository without confusing source trees, releases, and runtime installs.

**Architecture:** Create one installable incubating skill, `lvxiaoer/operate-infinitas-skill`, using the existing basic template. Keep the reusable guidance in a single `SKILL.md`, split by shared repository model plus platform-specific sections, and validate it with a focused repository test plus the existing skill checks and catalog rebuild flow.

**Tech Stack:** Bash scaffolding scripts, Markdown skill docs, `_meta.json` registry metadata, smoke-test notes, Python temp-repo tests, and the existing `scripts/check-skill.sh` / `scripts/build-catalog.sh` pipeline.

---

### Task 1: Add a failing skill contract test

**Files:**
- Create: `scripts/test-operate-infinitas-skill.py`

**Step 1:** Assert the skill directory exists at `skills/incubating/operate-infinitas-skill`.

**Step 2:** Assert `SKILL.md` contains:
- a trigger description for OpenClaw, Codex, and Claude Code
- sections for shared model plus each platform
- command references for `import-openclaw-skill.sh`, `publish-skill.sh`, `pull-skill.sh`, and `export-openclaw-skill.sh`

**Step 3:** Assert `_meta.json` declares publisher-qualified identity and cross-platform compatibility.

**Step 4:** Run the test and confirm it fails before the skill exists.

### Task 2: Scaffold and write the shared skill

**Files:**
- Create: `skills/incubating/operate-infinitas-skill/*`

**Step 1:** Scaffold from `templates/basic-skill` using `scripts/new-skill.sh lvxiaoer/operate-infinitas-skill basic`.

**Step 2:** Replace template metadata with:
- publisher-qualified identity under `lvxiaoer`
- concise summary and tags
- `agent_compatible` including `openclaw`, `codex`, `claude`, and `claude-code`

**Step 3:** Rewrite `SKILL.md` to cover:
- the four repository states
- the default decision workflow
- platform-specific sections for OpenClaw, Codex, and Claude Code
- confirm-first and hard-rule guidance

**Step 4:** Add a realistic `tests/smoke.md` scenario proving the skill’s intended trigger.

**Step 5:** Update `CHANGELOG.md` to describe the new skill.

### Task 3: Validate and regenerate generated artifacts

**Files:**
- Modify: `catalog/catalog.json`
- Modify: `catalog/compatibility.json`

**Step 1:** Re-run `scripts/test-operate-infinitas-skill.py`.

**Step 2:** Run `scripts/check-skill.sh skills/incubating/operate-infinitas-skill`.

**Step 3:** Run `scripts/build-catalog.sh` to refresh generated catalog views.

**Step 4:** Run the focused validation set needed for this skill addition and confirm it passes.
