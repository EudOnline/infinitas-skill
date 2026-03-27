# Home Kawaii Mobile & Readability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the refined kawaii homepage so supporting text reads more clearly and the mobile layout feels intentionally adapted instead of merely stacked.

**Architecture:** Keep the existing kawaii visual system and section structure, but strengthen text tokens, increase readability in supporting copy, add overflow protection, and introduce mobile-specific layout rules for actions, cards, and navigation. Verification will combine focused HTML/CSS regression checks with a fresh browser screenshot.

**Tech Stack:** FastAPI, Jinja2 templates, inline CSS, Python regression script, Playwright CLI screenshots.

---

### Task 1: Add a failing regression scenario

**Files:**
- Modify: `scripts/test-home-kawaii-theme.py`

**Step 1: Write the failing test**

Add assertions that the homepage output includes:
- darker supporting text tokens
- overflow protection markers such as `min-width: 0` and `overflow-wrap: anywhere`
- mobile-specific adaptations for action groups and section CTAs

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python scripts/test-home-kawaii-theme.py`

Expected: FAIL because the current refined homepage still uses lighter secondary text and limited mobile-specific action layout rules.

### Task 2: Improve readability and harden text containers

**Files:**
- Modify: `server/templates/layout-kawaii.html`
- Modify: `server/templates/index-kawaii.html`

**Step 1: Strengthen supporting text**

Darken secondary and muted text tokens and slightly raise key supporting type sizes where the current UI looks faint.

**Step 2: Protect against overflow**

Add `min-width: 0`, `overflow-wrap`, and wrapping rules to command rows, summaries, and metadata containers.

### Task 3: Adapt the layout for mobile intentionally

**Files:**
- Modify: `server/templates/layout-kawaii.html`
- Modify: `server/templates/index-kawaii.html`

**Step 1: Improve small-screen navigation**

Make the top bar and nav chips feel intentionally arranged on narrow screens.

**Step 2: Improve small-screen actions and cards**

Stack hero and skill actions cleanly, give section CTAs full-width treatment, and tighten card spacing for handheld use.

**Step 3: Run the focused test**

Run: `./.venv/bin/python scripts/test-home-kawaii-theme.py`

Expected: PASS.

### Task 4: Visual verification

**Files:**
- No code changes required unless issues are found

**Step 1: Start the app locally**

Run: `./.venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8765`

**Step 2: Capture fresh desktop and mobile screenshots**

Use Playwright CLI to inspect both contexts and confirm readability plus mobile adaptation quality.
