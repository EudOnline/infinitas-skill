# Kawaii Full UI Cutover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fully switch the hosted registry web UI to the new kawaii interface, retire the legacy homepage and `v2` experiment, and remove stale UI assets/templates without changing API behavior.

**Architecture:** Keep one canonical server-rendered shell, [server/templates/layout-kawaii.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/layout-kawaii.html), as the only HTML layout for user-facing pages. Migrate `/`, `/submissions`, `/reviews`, `/jobs`, and `/login` into that shell; redirect `/v2` to `/`; then delete obsolete templates and the CSS bundle that only powered `layout_v2.html`. Preserve route auth, data queries, and API contracts exactly as-is.

**Tech Stack:** FastAPI, Jinja2 templates, inline CSS/JS for the kawaii shell, Python regression scripts, Playwright screenshots, ripgrep for cleanup verification.

---

### Recommended Cutover Strategy

**Option A: Hard cutover with compatibility redirect**  
Recommendation. Migrate all HTML pages to the kawaii shell in one branch, redirect `/v2` to `/`, then delete unused legacy files. This gives one source of truth immediately while keeping inbound `/v2` links from breaking.

**Option B: Dual-run transitional phase**  
Keep old console pages for one more iteration and only switch the shell + homepage. Lower short-term risk, but it preserves duplication and delays cleanup.

**Option C: Shell-only migration without file cleanup**  
Fastest to land, but it leaves dead templates, old CSS, and stale docs behind. This is the least desirable if the goal is “全面切换”.

This plan assumes **Option A**.

### Task 1: Freeze the cutover contract with failing tests

**Files:**
- Modify: `scripts/test-home-kawaii-theme.py`
- Modify: `scripts/test-hosted-api.py`
- Modify: `scripts/test-hosted-operator-console.py`

**Step 1: Add a failing homepage cutover assertion**

Add checks that the homepage HTML:
- still renders through `layout-kawaii.html`
- no longer contains links or markers for `/v2`
- still exposes language and theme controls

Example assertion:

```python
if '/v2' in html:
    fail('homepage should not advertise the retired /v2 UI')
```

**Step 2: Add failing console-shell assertions**

Extend console page checks so maintainer-rendered `/submissions`, `/reviews`, and `/jobs` must include:
- the new topbar control groups
- the kawaii shell marker `data-theme="kawaii"`
- language/theme toggles

Example assertion:

```python
for shared_needle in ['data-theme="kawaii"', 'data-theme-choice="light"', 'data-theme-choice="dark"']:
    if shared_needle not in response.text:
        fail(f'expected {route} page to contain {shared_needle!r}')
```

**Step 3: Add a failing redirect expectation for `/v2`**

Update the FastAPI smoke test to expect either:
- `307/308` redirect to `/`, or
- `404` if the team explicitly wants the route removed immediately

Recommended expectation:

```python
response = client.get('/v2', follow_redirects=False)
assert response.status_code in {307, 308}
assert response.headers['location'] == '/'
```

**Step 4: Run focused tests and confirm they fail**

Run:

```bash
./.venv/bin/python scripts/test-home-kawaii-theme.py
./.venv/bin/python scripts/test-hosted-api.py
./.venv/bin/python scripts/test-hosted-operator-console.py
```

Expected: FAIL on missing kawaii console controls and `/v2` cutover expectations.

### Task 2: Make `layout-kawaii.html` the only live shell

**Files:**
- Modify: `server/app.py`
- Modify: `server/templates/layout-kawaii.html`

**Step 1: Unify route intent in `server/app.py`**

Change the HTML routes so:
- `/` stays on `index-kawaii.html`
- `/v2` redirects to `/`
- console routes prepare context compatible with `layout-kawaii.html`
- `/login` stops rendering raw `layout.html`

Recommended minimal route change:

```python
from fastapi.responses import RedirectResponse

@app.get('/v2')
def index_v2_redirect():
    return RedirectResponse(url='/', status_code=307)
```

**Step 2: Generalize the kawaii shell**

Promote `layout-kawaii.html` from “homepage shell” to “site shell” by ensuring it can render:
- homepage
- maintainers-only console pages
- login/auth message state

Do not duplicate the topbar, theme switcher, or language switcher into separate layouts.

**Step 3: Keep auth semantics untouched**

Do not change:
- `401` for anonymous access
- `403` for contributor access
- maintainer-only rendering rules

The cutover is visual + structural, not behavioral.

**Step 4: Run the failing tests again**

Run:

```bash
./.venv/bin/python scripts/test-hosted-api.py
./.venv/bin/python scripts/test-hosted-operator-console.py
```

Expected: still FAIL until console templates are migrated.

### Task 3: Migrate console templates into the kawaii system

**Files:**
- Modify: `server/templates/submissions.html`
- Modify: `server/templates/reviews.html`
- Modify: `server/templates/jobs.html`
- Create: `server/templates/login-kawaii.html`

**Step 1: Rebase console templates onto `layout-kawaii.html`**

Replace:

```jinja2
{% extends "layout.html" %}
```

with:

```jinja2
{% extends "layout-kawaii.html" %}
```

Then adapt section wrappers so the pages visually match the new system while preserving the same data and headings.

**Step 2: Keep console IA familiar**

Do not redesign workflow semantics. Preserve:
- `Submissions`, `Reviews`, `Jobs` headings
- `registryctl.py` command references
- maintainer notes / insight cards
- table content and ordering

The change should feel like “same tool, new shell”, not “new product”.

**Step 3: Add a dedicated kawaii login page**

Create `server/templates/login-kawaii.html` so `/login` renders inside the new shell with:
- short auth explanation
- token-focused copy
- no old layout dependency

**Step 4: Add minimal console-specific styling only where needed**

Prefer small local sections in each page or shared classes inside `layout-kawaii.html`. Do not recreate a second design system.

**Step 5: Run console verification**

Run:

```bash
./.venv/bin/python scripts/test-hosted-api.py
./.venv/bin/python scripts/test-hosted-operator-console.py
```

Expected: PASS.

### Task 4: Delete obsolete templates, routes, and CSS bundles

**Files:**
- Delete: `server/templates/index.html`
- Delete: `server/templates/layout.html`
- Delete: `server/templates/index_v2.html`
- Delete: `server/templates/layout_v2.html`
- Delete: `server/static/css/variables.css`
- Delete: `server/static/css/base.css`
- Delete: `server/static/css/components.css`
- Modify: `server/app.py`

**Step 1: Verify no runtime references remain**

Run:

```bash
rg -n 'index_v2|layout_v2|layout.html|index.html|/v2|variables.css|base.css|components.css' server
```

Expected: only intentional doc references remain before deletion.

**Step 2: Delete dead templates and assets**

Remove the legacy files only after tests are green and `server/app.py` no longer references them.

**Step 3: Re-run reference scan**

Run:

```bash
rg -n 'extends "layout.html"|extends "layout_v2.html"|TemplateResponse\\(.+index_v2|TemplateResponse\\(.+layout.html' server
```

Expected: no matches.

**Step 4: Decide doc treatment**

For docs that describe the retired UI:
- keep historical design docs under `docs/` if they are archival
- update migration guides that could mislead future work

Minimum doc cleanup targets:
- `docs/theme-migration-guide.md`
- `docs/v2-migration-guide.md`
- `docs/fixes-applied.md`

### Task 5: Refresh verification and screenshot baselines

**Files:**
- Modify: `scripts/test-home-kawaii-theme.py`
- Modify: `scripts/test-hosted-api.py`
- Modify: `scripts/test-hosted-operator-console.py`
- Create or refresh artifacts under: `output/playwright/`

**Step 1: Run the full focused verification suite**

Run:

```bash
./.venv/bin/python scripts/test-home-kawaii-theme.py
./.venv/bin/python scripts/test-hosted-api.py
./.venv/bin/python scripts/test-hosted-operator-console.py
```

Expected: PASS.

**Step 2: Capture fresh screenshots**

Capture at minimum:
- homepage zh light
- homepage zh dark
- homepage en light
- homepage mobile
- one console page in light
- one console page in dark

**Step 3: Run cleanup grep**

Run:

```bash
rg -n 'layout_v2|index_v2|/v2|layout.html|index.html' server scripts
```

Expected: no runtime references; only historical docs may remain.

**Step 4: Summarize residual risks**

Check specifically for:
- console page spacing drift versus homepage shell
- bilingual copy overflow in the topbar
- auth pages that still rely on legacy copy or structure
- screenshot mismatch between desktop and mobile toggle controls

### Task 6: Commit in clear migration slices

**Files:**
- Git only

**Step 1: Commit shell + route migration**

```bash
git add server/app.py server/templates/layout-kawaii.html server/templates/index-kawaii.html
git commit -m "feat: unify hosted homepage under kawaii shell"
```

**Step 2: Commit console migration**

```bash
git add server/templates/submissions.html server/templates/reviews.html server/templates/jobs.html server/templates/login-kawaii.html
git commit -m "feat: migrate operator console to kawaii ui"
```

**Step 3: Commit legacy cleanup**

```bash
git add server/templates server/static/css docs
git commit -m "refactor: remove retired hosted ui templates"
```

**Step 4: Commit test baseline updates**

```bash
git add scripts/test-home-kawaii-theme.py scripts/test-hosted-api.py scripts/test-hosted-operator-console.py output/playwright
git commit -m "test: lock full kawaii ui cutover coverage"
```
