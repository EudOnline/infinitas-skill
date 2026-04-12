# Release Closeout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the current backend hardening and OpenClaw-first release work with a clean, auditable closeout path that is safe to ship.

**Architecture:** Treat closeout as a gated sequence instead of a single “final test” moment. First freeze and slice the current changeset, then refresh operator-facing docs, then run the fast and full release gates, then do a release dry-run and final handoff checks. Keep frontend style unchanged; any frontend follow-up remains a data-binding and verification task, not a visual redesign task.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Ruff, Pytest, Bash release scripts, Tailwind CSS build pipeline, GitHub Actions, OpenClaw-first release policy.

---

### Task 1: Freeze The Current Closeout Scope

**Files:**
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/src/infinitas_skill/release`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/scripts`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/package.json`

**Step 1: Snapshot the working tree**

Run: `git status --short`
Expected: Only the intended closeout edits are listed; no surprise binary files or generated junk.

**Step 2: Capture the current diff summary**

Run: `git diff --stat`
Expected: The diff clusters into release gating, server hardening, tests, and docs.

**Step 3: Mark commit buckets before touching anything else**

Create this checklist in your scratch notes:
- `server/` and `src/infinitas_skill/release/` security + policy fixes
- `tests/` and `scripts/` regression and invariant updates
- `package.json` and docs closeout clarity updates

**Step 4: Verify no whitespace or merge-fragment damage exists**

Run: `git diff --check`
Expected: No output.

**Step 5: Commit bucket plan**

```bash
git add server src/infinitas_skill/release
git commit -m "fix: harden release authorization and backend security gates"
git add scripts tests
git commit -m "test: align release invariants and regression helpers"
git add package.json docs
git commit -m "docs: clarify closeout and local validation flow"
```

### Task 2: Refresh Maintained Closeout Docs

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/project-closeout.md`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/reference/testing.md`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/reference/cli-reference.md`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/guide/frontend-control-plane-alignment.md`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/guide/kimi-frontend-execution-brief.md`

**Step 1: Document the actual local validation entry points**

Add:
- `npm test` only verifies frontend asset build
- `make ci-fast` is the local fast gate
- `scripts/check-all.sh` is the authoritative closeout gate

**Step 2: Document the new release authorization rule**

Add one explicit statement:
- `preflight` and `stable-release` now block if `authorized_releasers` is configured and the resolved releaser is not authorized

**Step 3: Document the canonical runtime gate correctly**

Update wording so it says:
- OpenClaw freshness is the maintained runtime release gate
- Codex and Claude evidence remain regression/audit coverage, not equal-weight release blockers

**Step 4: Re-run doc-sensitive tests**

Run: `uv run pytest -q tests/integration/test_maintainability_budgets.py`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/project-closeout.md docs/reference/testing.md docs/reference/cli-reference.md
git commit -m "docs: refresh release closeout guidance"
```

### Task 3: Reconfirm Backend Hardening Gate

**Files:**
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/settings.py`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/app.py`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/auth.py`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/api/auth.py`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/models.py`
- Test: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_private_registry_ui.py`
- Test: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_registry_read_tokens.py`

**Step 1: Run server lint**

Run: `uv run ruff check server`
Expected: PASS

**Step 2: Run the hardened settings contract**

Run: `uv run python scripts/test-settings-hardening.py`
Expected: `OK: settings hardening checks passed`

**Step 3: Run targeted auth and registry regressions**

Run: `uv run pytest -q tests/integration/test_private_registry_ui.py tests/integration/test_registry_read_tokens.py`
Expected: PASS

**Step 4: Run full Python lint gate**

Run: `uv run ruff check src/infinitas_skill server tests`
Expected: PASS

**Step 5: Commit if anything changed**

```bash
git add server tests scripts
git commit -m "test: lock backend hardening gates"
```

### Task 4: Reconfirm Release Policy Gate

**Files:**
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/src/infinitas_skill/release/release_issues.py`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/src/infinitas_skill/release/service.py`
- Test: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/unit/release/test_release_issues.py`
- Test: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_cli_release_state.py`
- Test: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/scripts/test-release-invariants.py`

**Step 1: Run the focused release unit + CLI matrix**

Run: `uv run pytest -q tests/unit/release/test_release_issues.py tests/integration/test_cli_release_state.py`
Expected: PASS

**Step 2: Run the release invariant script**

Run: `uv run python scripts/test-release-invariants.py`
Expected: `OK: release invariant checks passed`

**Step 3: Run CI attestation contract**

Run: `python3 scripts/test-ci-attestation-workflow.py`
Expected: `OK: CI attestation workflow contract looks valid`

**Step 4: Record the policy rule in the release notes draft**

Add one bullet to your release notes draft:
- unauthorized releasers now block preflight/stable release instead of surfacing as warnings

**Step 5: Commit**

```bash
git add src/infinitas_skill/release tests/unit/release/test_release_issues.py tests/integration/test_cli_release_state.py scripts/test-release-invariants.py
git commit -m "fix: enforce authorized releasers in release preflight"
```

### Task 5: Reconfirm Frontend Asset And UI Closeout Surface

**Files:**
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/package.json`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/static/js/app.js`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/static/js/auth-session.js`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/routes.py`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/guide/kimi-frontend-execution-brief.md`

**Step 1: Build frontend assets**

Run: `npm run build`
Expected: PASS

**Step 2: Verify the local script warning is clear**

Run: `npm test`
Expected: PASS plus a note that this only verifies frontend asset build

**Step 3: Run the fast UI/backend integration gate**

Run: `make ci-fast`
Expected: PASS

**Step 4: Manual smoke review**

Check:
- login still works
- release page still renders readiness state
- private registry pages still show data correctly
- no visual redesign slipped in

**Step 5: Frontend handoff note**

If any remaining frontend bug appears, assign it as:
- data-binding only
- no UI style change
- Kimi Code execution allowed

### Task 6: Run The Authoritative Closeout Matrix

**Files:**
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/scripts/check-all.sh`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.github/workflows/validate.yml`

**Step 1: Run the default closeout gate**

Run: `scripts/check-all.sh`
Expected: PASS

**Step 2: Run the long release gate**

Run: `scripts/check-all.sh release-long`
Expected: PASS

**Step 3: If browser/runtime dependencies are available, run the full matrix**

Run: `scripts/check-all.sh focused-integration hosted-ui release-long full-regression`
Expected: PASS or a clearly documented environmental skip

**Step 4: Capture the command log for release notes**

Record:
- command
- timestamp
- pass/fail
- any skips and why

**Step 5: Commit only if the matrix exposed doc or script drift**

```bash
git add .github/workflows/validate.yml scripts/check-all.sh docs/reference/testing.md
git commit -m "chore: align closeout matrix documentation"
```

### Task 7: Clean Dependency And Tooling Noise

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/package-lock.json`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/package.json`

**Step 1: Refresh Browserslist metadata**

Run: `npx update-browserslist-db@latest`
Expected: caniuse-lite metadata updates cleanly

**Step 2: Rebuild CSS after metadata refresh**

Run: `npm run build`
Expected: PASS with no new build break

**Step 3: Re-run the local package gate**

Run: `npm test`
Expected: PASS and the same explicit note about limited scope

**Step 4: Verify lockfile-only diff is sane**

Run: `git diff -- package-lock.json`
Expected: dependency metadata update only

**Step 5: Commit**

```bash
git add package-lock.json package.json
git commit -m "chore: refresh frontend build metadata"
```

### Task 8: Final Ship Checklist

**Files:**
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/project-closeout.md`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/reference/testing.md`

**Step 1: Verify branch cleanliness**

Run: `git status --short`
Expected: no unintended unstaged or untracked files remain

**Step 2: Re-run whitespace and patch health**

Run: `git diff --check`
Expected: no output

**Step 3: Produce the release summary**

Include:
- backend security hardening
- release authorization enforcement
- release invariant alignment with OpenClaw canonical gate
- local validation script clarification

**Step 4: Confirm go/no-go**

Go only if all are true:
- `make ci-fast` passes
- `scripts/check-all.sh` passes
- `scripts/check-all.sh release-long` passes
- release invariants pass
- settings hardening passes
- no style drift is observed in frontend smoke review

**Step 5: Create the final integration commit or PR**

```bash
git add .
git commit -m "chore: finalize release closeout"
```
