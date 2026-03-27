# Home Kawaii Refinement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refine the default kawaii homepage so it feels calmer, more intentional, and less AI-generated while keeping the friendly personality.

**Architecture:** Keep the existing `index-kawaii.html` information architecture and live data wiring, but reduce intensity through CSS token changes, interaction script removal, and section-level hierarchy adjustments. Verification combines HTML regression checks with a fresh browser screenshot.

**Tech Stack:** FastAPI, Jinja2 templates, inline CSS/JS, Python script-based regression tests, Playwright CLI screenshots.

---

### Task 1: Lock the refinement constraints with a failing test

**Files:**
- Modify: `scripts/test-home-kawaii-theme.py`

**Step 1: Write the failing test**

Add a scenario that asserts the rendered homepage no longer ships:
- gradient-text implementation markers
- bounce / elastic easing tokens
- mousemove parallax
- click sparkle effects

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python scripts/test-home-kawaii-theme.py`

Expected: FAIL because the current homepage still includes those high-intensity markers.

### Task 2: Quiet the global theme language

**Files:**
- Modify: `server/templates/layout-kawaii.html`

**Step 1: Reduce theme intensity**

Tone down glow and shadow tokens, remove gradient-text branding, and replace bounce / elastic easing with smoother motion curves.

**Step 2: Remove decorative interaction noise**

Delete mousemove parallax and click sparkle scripts while preserving copy interaction feedback.

**Step 3: Run the focused test**

Run: `./.venv/bin/python scripts/test-home-kawaii-theme.py`

Expected: still FAIL until section-level refinement is complete if any banned markers remain.

### Task 3: Rebalance homepage hierarchy

**Files:**
- Modify: `server/templates/index-kawaii.html`

**Step 1: Keep hero as the only loud area**

Reduce hero decorative weight, remove unused gradient-title styling, and make CTA hierarchy calmer.

**Step 2: Make later sections more editorial**

Differentiate status, maintainer, and skills areas by reducing repeated card sameness, simplifying borders, and tightening copy hierarchy.

**Step 3: Run the focused test**

Run: `./.venv/bin/python scripts/test-home-kawaii-theme.py`

Expected: PASS.

### Task 4: Visual verification

**Files:**
- No code changes required unless issues are found

**Step 1: Start the app locally**

Run: `./.venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8765`

**Step 2: Capture a fresh homepage screenshot**

Use Playwright CLI to open `http://127.0.0.1:8765`, resize the viewport, and save a screenshot.

**Step 3: Compare against the refinement goals**

Confirm:
- less glow
- calmer motion language
- clearer section hierarchy after the hero
- kawaii personality retained
