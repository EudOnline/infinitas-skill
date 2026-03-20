# Project Completion and Steady-State Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the repository as a completed project on `main` by syncing planning truth to the merged state, recording steady-state expectations, and locking that truth in with one lightweight regression check.

**Architecture:** Do not start a new capability milestone. Treat this as post-closeout truth-maintenance work. Add one small repo-local regression test that fails if planning or closeout docs drift back to pre-merge language, then update the planning and operator docs so they consistently say the project is complete on `main` and any remaining concerns are accepted maintenance notes or explicit future backlog.

**Tech Stack:** Existing Bash/Python 3.11 tooling, repo-local Markdown docs, `.planning/*` status files, and `scripts/check-all.sh`.

---

### Task 1: Add a failing post-merge completion-state regression check

**Files:**
- Create: `scripts/test-project-complete-state.py`
- Modify: `scripts/check-all.sh`

**Step 1: Write the failing test**

Create `scripts/test-project-complete-state.py` with assertions that:

- `.planning/PROJECT.md` no longer says the remaining step is to merge a feature branch back to `main`
- `.planning/REQUIREMENTS.md` no longer says v20 still needs merging to `main`
- `.planning/ROADMAP.md` no longer says the next operational step is to merge `codex/v17-installed-reporting` back to `main`
- `.planning/STATE.md` no longer says `merge prep`, `merge-back to main`, or `Pending Todos` that are already completed
- `docs/project-closeout.md` no longer phrases merge as a future gate; instead it should state the project is complete on `main` and future work belongs to a new milestone

Example skeleton:

```python
#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def assert_contains(path: str, needle: str) -> None:
    if needle not in read(path):
        fail(f"expected {path} to contain {needle!r}")


def assert_not_contains(path: str, needle: str) -> None:
    if needle in read(path):
        fail(f"expected {path} not to contain {needle!r}")
```

**Step 2: Run the new test to verify it fails**

Run:

```bash
python3 scripts/test-project-complete-state.py
```

Expected: FAIL because current planning docs still contain post-v20 pre-merge wording such as `remaining operational step`, `merge prep`, or `merge-back to main`.

**Step 3: Wire the test into the standard verification path**

Add this command near the planning/doc-state checks in `scripts/check-all.sh`:

```bash
python3 scripts/test-project-complete-state.py
```

Do not move hosted e2e gating or any heavy integration checks.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-project-complete-state.py
```

Expected: still FAIL, but now through the canonical repo verification path as well.

**Step 5: Commit**

```bash
git add scripts/test-project-complete-state.py scripts/check-all.sh
git commit -m "test: add project completion state regression"
```

### Task 2: Sync planning docs from “merged branch pending” to “project complete on main”

**Files:**
- Modify: `.planning/PROJECT.md`
- Modify: `.planning/REQUIREMENTS.md`
- Modify: `.planning/ROADMAP.md`
- Modify: `.planning/STATE.md`

**Step 1: Update `.planning/PROJECT.md`**

Change the v20 status text so it says:

- v20 is complete on `main`
- the project is now in steady-state unless a new milestone is intentionally started
- `codex/v17-installed-reporting` is no longer the active branch context

Also replace any wording that still says “remaining operational step is to merge back to `main`”.

**Step 2: Update `.planning/REQUIREMENTS.md`**

Change the v20 summary text from “remaining operational step is merging the verified branch back to `main`” to language like:

- all v20 requirements are complete on `main`
- future work, if any, should be opened as a new milestone or maintenance slice

**Step 3: Update `.planning/ROADMAP.md`**

Change:

- `Current Follow-up` to reflect that v20 is complete on `main`
- any line that still says “The next operational step is to merge `codex/v17-installed-reporting` back to `main`”
- any branch-specific completion labels that should now say `main` for the merged record

Keep historical references to the original implementation branch only when they are truly historical.

**Step 4: Update `.planning/STATE.md`**

Set this file to true post-merge completion state, for example:

- `Current focus`: project complete on `main`, no active milestone
- `Phase`: steady-state or project complete
- `Status`: v20 complete on `main`
- `Pending Todos`: only real remaining items, or replace with a short “no active milestone” note
- `Session Continuity`: point future work to a new milestone plan rather than the old merge-prep status

**Step 5: Run the regression test**

Run:

```bash
python3 scripts/test-project-complete-state.py
```

Expected: PASS

**Step 6: Commit**

```bash
git add .planning/PROJECT.md .planning/REQUIREMENTS.md .planning/ROADMAP.md .planning/STATE.md
git commit -m "docs: mark project complete on main"
```

### Task 3: Convert closeout docs from merge-gate language to steady-state guidance

**Files:**
- Modify: `docs/project-closeout.md`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/compatibility-contract.md`
- Optionally modify: `README.md`

**Step 1: Update `docs/project-closeout.md`**

Keep the verification matrix, but change the framing so it:

- records that the merge gate has already been satisfied on `main`
- defines what “steady-state complete” means now
- moves future work into a short backlog or “new milestone required” section

Do not leave language that reads as if the branch merge is still pending.

**Step 2: Tighten the operator-facing steady-state notes**

In `docs/installed-skill-integrity.md` and `docs/compatibility-contract.md`, make sure the residual compatibility notes are clearly presented as:

- accepted non-blocking notes for the completed project
- not reasons to reopen v20
- candidates for a future maintenance milestone only if a user-facing problem appears

If helpful, add one short README pointer to `docs/project-closeout.md` so the repository has a visible “project complete / maintenance mode” entrypoint.

**Step 3: Re-run focused checks**

Run:

```bash
python3 scripts/test-project-complete-state.py
python3 scripts/test-explain-install.py
python3 scripts/test-skill-update.py
python3 scripts/test-installed-skill-integrity.py
```

Expected: PASS

**Step 4: Commit**

```bash
git add docs/project-closeout.md docs/installed-skill-integrity.md docs/compatibility-contract.md README.md
git commit -m "docs: convert closeout to steady-state guidance"
```

### Task 4: Run final verification on `main` and declare the repository complete

**Files:**
- Modify: `.planning/STATE.md`
- Optionally modify: `docs/project-closeout.md`

**Step 1: Run the final verification matrix**

Use `@superpowers:verification-before-completion`.

Run:

```bash
python3 scripts/test-project-complete-state.py
python3 scripts/test-installed-integrity-never-verified-guardrails.py
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-skill-update.py
python3 scripts/test-explain-install.py
python3 scripts/test-distribution-install.py
./scripts/check-all.sh
```

If local hosted-registry dependencies are intentionally minimal, run the full suite inside a temporary virtualenv exactly as documented in `docs/project-closeout.md`.

**Step 2: Record completion truth**

If all verification passes:

- update `.planning/STATE.md` so the latest activity reflects the project being complete on `main`
- optionally add one short dated note in `docs/project-closeout.md` that fresh verification was rerun on `main`

Do not invent a v21 milestone here.

**Step 3: Run the final verification one more time if any completion-text files changed**

Run:

```bash
python3 scripts/test-project-complete-state.py
./scripts/check-all.sh
```

Expected: PASS

**Step 4: Commit**

```bash
git add .planning/STATE.md docs/project-closeout.md
git commit -m "chore: finalize project completion state"
```

## Suggested Commit Sequence

1. `test: add project completion state regression`
2. `docs: mark project complete on main`
3. `docs: convert closeout to steady-state guidance`
4. `chore: finalize project completion state`

## Verification Checklist

- `python3 scripts/test-project-complete-state.py`
- `python3 scripts/test-installed-integrity-never-verified-guardrails.py`
- `python3 scripts/test-installed-integrity-stale-guardrails.py`
- `python3 scripts/test-installed-integrity-report.py`
- `python3 scripts/test-installed-integrity-freshness.py`
- `python3 scripts/test-install-manifest-compat.py`
- `python3 scripts/test-installed-skill-integrity.py`
- `python3 scripts/test-skill-update.py`
- `python3 scripts/test-explain-install.py`
- `python3 scripts/test-distribution-install.py`
- `./scripts/check-all.sh`

## Handoff Notes

- Do not start v21 or any new feature expansion as part of this plan.
- Prefer documenting residual compatibility notes as accepted steady-state behavior unless a concrete user-facing defect appears.
- The current stash entry `pre-sync-local-main-2026-03-20` is local operator state, not repository scope; do not turn stash recovery into a tracked project milestone.
- The purpose of this plan is to make the repository say the truth about itself on `main`, then stop.
