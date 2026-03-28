# UI Auth And I18n Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the verified browser-session and localization regressions in the kawaii UI without reopening the old UI surface.

**Architecture:** Keep the current cookie-backed browser auth model, but stop treating `localStorage` as the source of truth for browser session state. Centralize UI copy in server-provided context so templates and `app.js` render the same language and preserve `lang` across page transitions.

**Tech Stack:** FastAPI, Jinja2 templates, vanilla JavaScript, Python smoke tests, Playwright CLI for browser verification

---

### Task 1: Lock The Regressions With Tests

**Files:**
- Modify: `scripts/test-home-kawaii-theme.py`
- Modify: `scripts/test-hosted-api.py`
- Create: `scripts/test-home-auth-session-runtime.py`

**Step 1: Write the failing server-render tests**

Add assertions that:
- `/?lang=en` renders English quick-start, auth modal, user panel, and skill copy labels
- English console links and maintainer CTA preserve `?lang=en`
- The home search input exposes a non-empty placeholder and aria-label
- The English login page redirects to a localized home URL instead of bare `/`

**Step 2: Run the targeted server-render tests to verify they fail**

Run:

```bash
./.venv/bin/python scripts/test-home-kawaii-theme.py
./.venv/bin/python scripts/test-hosted-api.py
```

Expected: failures showing missing English strings, missing localized hrefs, or empty search label markers.

**Step 3: Write the failing browser-session regression test**

In `scripts/test-home-auth-session-runtime.py`, start a temporary hosted app, log in through the browser once, clear only `localStorage`, reload `/?lang=en`, and assert that the user trigger still renders the logged-in icon/state from the cookie-backed session.

**Step 4: Run the runtime regression test to verify it fails**

Run:

```bash
./.venv/bin/python scripts/test-home-auth-session-runtime.py
```

Expected: failure because the home page falls back to the locked state when only the cookie remains.

### Task 2: Localize Server Context And Template Navigation

**Files:**
- Modify: `server/app.py`
- Modify: `server/templates/layout-kawaii.html`
- Modify: `server/templates/index-kawaii.html`
- Modify: `server/templates/login-kawaii.html`

**Step 1: Add missing UI copy keys to the shared kawaii context**

Add localized strings for:
- search placeholder and search result labels
- theme-switch toast copy
- auth modal and user panel labels
- quick-start section labels and hint
- skill copy action label

Also add helpers that preserve `lang` for internal route hrefs.

**Step 2: Update templates to consume the shared copy**

Replace hard-coded Chinese strings in the home and login templates with context-backed labels, and make brand / console / post-login links preserve the current language.

**Step 3: Run the render tests**

Run:

```bash
./.venv/bin/python scripts/test-home-kawaii-theme.py
./.venv/bin/python scripts/test-hosted-api.py
```

Expected: render assertions pass while the runtime cookie-only test still fails.

### Task 3: Make Browser Auth State Cookie-First

**Files:**
- Modify: `server/templates/index-kawaii.html`

**Step 1: Remove the home page dependence on localStorage-only auth presence**

Update auth initialization so the page always probes `/api/auth/me` for browser session state, even when localStorage is empty. Keep localStorage only as optional convenience metadata, not as the gate for browser login state.

**Step 2: Make UI fallbacks work without localStorage expiry**

If expiry metadata is unavailable, render a localized generic session label instead of forcing the page back to anonymous state.

**Step 3: Run the runtime regression test**

Run:

```bash
./.venv/bin/python scripts/test-home-auth-session-runtime.py
```

Expected: pass with the user trigger showing the authenticated state after clearing localStorage.

### Task 4: Unify Shared JavaScript Copy

**Files:**
- Modify: `server/templates/layout-kawaii.html`
- Modify: `server/static/js/app.js`

**Step 1: Expose a JS-safe UI copy object from the layout**

Serialize the localized UI strings into a single browser-readable config object.

**Step 2: Replace hard-coded Chinese strings in `app.js`**

Use the serialized UI copy for:
- theme toast messages
- copy success/error toasts
- search dropdown labels and empty state
- skill-use success/failure feedback

**Step 3: Re-run targeted tests**

Run:

```bash
./.venv/bin/python scripts/test-home-kawaii-theme.py
./.venv/bin/python scripts/test-home-auth-session-runtime.py
```

Expected: both remain green after JS copy refactor.

### Task 5: Final Verification

**Files:**
- No new production files

**Step 1: Run the full regression suite**

Run:

```bash
./.venv/bin/python scripts/test-home-kawaii-theme.py
./.venv/bin/python scripts/test-home-auth-session-runtime.py
./.venv/bin/python scripts/test-hosted-api.py
node --check server/static/js/app.js
```

**Step 2: Perform one manual browser sanity check**

Verify in a real browser that:
- `/?lang=en` stays English through auth and console navigation
- clearing localStorage does not log the browser UI out while the auth cookie still exists
- search field has visible hint text and localized dropdown copy

**Step 3: Commit**

```bash
git add docs/plans/2026-03-28-ui-auth-i18n-hardening-plan.md scripts/test-home-kawaii-theme.py scripts/test-home-auth-session-runtime.py scripts/test-hosted-api.py server/app.py server/static/js/app.js server/templates/index-kawaii.html server/templates/layout-kawaii.html server/templates/login-kawaii.html
git commit -m "fix: harden hosted ui auth and i18n flows"
```
