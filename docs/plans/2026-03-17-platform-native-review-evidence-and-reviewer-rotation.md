# Platform-Native Review Evidence And Reviewer Rotation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let maintainers ingest normalized platform-native approval evidence as additive quorum input and generate deterministic reviewer rotation or escalation suggestions from existing review policy.

**Architecture:** Keep governance integration Git-native and deterministic. Introduce a normalized review-evidence artifact that lives alongside skill review data, then extend `review_lib.py` so quorum evaluation merges repo-local `reviews.json` entries with imported platform evidence while preserving source provenance. Build reviewer guidance on top of the existing reviewer-group and team-policy model, using recent decision history only as an additive ranking hint rather than a new scheduler or ownership system.

**Tech Stack:** Existing Bash and Python 3.11 CLI tooling, JSON policy/evidence files, `scripts/review_lib.py`, `scripts/team_policy_lib.py`, promotion/release/catalog generators, and Markdown operator docs.

---

### Task 1: Define normalized platform review evidence and failing quorum tests

**Files:**
- Create: `scripts/test-platform-review-evidence.py`
- Create: `scripts/review_evidence_lib.py`
- Create: `schemas/review-evidence.schema.json`
- Modify: `scripts/review_lib.py`
- Modify: `scripts/review-status.py`

**Step 1: Write the failing test**

Create `scripts/test-platform-review-evidence.py` with fixture scenarios that:

- create one incubating skill plus normal `reviews.json`
- write a sibling `review-evidence.json` file containing normalized imported approvals such as:
  - `source`
  - `source_kind`
  - `source_ref`
  - `reviewer`
  - `decision`
  - `at`
  - `url`
- assert `python3 scripts/review-status.py <skill> --as-active --json`:
  - counts imported approvals toward `approval_count`
  - keeps local and imported evidence distinguishable in `latest_decisions`
  - fails clearly when the evidence file contains invalid schema or duplicate reviewer identity collisions

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-platform-review-evidence.py
```

Expected: FAIL because no review-evidence contract or loader exists yet.

**Step 3: Implement the minimal review-evidence contract**

Add a focused evidence helper library that can:

- validate and load `review-evidence.json`
- normalize imported decisions into the same shape used by quorum evaluation
- preserve evidence source metadata so downstream outputs can show whether a decision came from `reviews.json` or imported platform evidence

Update `review_lib.py` and `review-status.py` to merge both sources while remaining deterministic when the same reviewer appears in multiple inputs.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-platform-review-evidence.py
python3 scripts/review-status.py skills/active/operate-infinitas-skill --json
```

Expected: PASS for the fixture-backed test, and the status command still works for existing repo-local review data.

### Task 2: Import platform approvals into promotion, release, and catalog outputs

**Files:**
- Modify: `scripts/test-platform-review-evidence.py`
- Create: `scripts/import-platform-review-evidence.py`
- Modify: `scripts/check-promotion-policy.py`
- Modify: `scripts/build-catalog.sh`
- Modify: `scripts/release_lib.py`
- Modify: `scripts/provenance_payload_lib.py`
- Modify: `docs/review-workflow.md`
- Modify: `docs/promotion-policy.md`

**Step 1: Extend the failing test**

Add scenarios that:

- import a normalized platform evidence fixture through `python3 scripts/import-platform-review-evidence.py ... --json`
- assert promotion, catalog, and release-state surfaces expose imported evidence provenance such as:
  - decision `source_kind`
  - decision `source_ref`
  - whether quorum passed because imported evidence was present
- assert missing or malformed imported evidence fails explicitly instead of being silently ignored when a command was asked to import it

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-platform-review-evidence.py
```

Expected: FAIL because import tooling and downstream provenance fields do not exist yet.

**Step 3: Implement minimal import and provenance wiring**

Create `scripts/import-platform-review-evidence.py` so operators can:

- read one normalized JSON payload or platform export fixture
- write `review-evidence.json` next to the target skill
- print JSON describing the imported evidence count and source metadata

Then thread imported evidence through promotion, catalog, release-state, and provenance builders so external approvals remain auditable rather than collapsing into anonymous approval counts.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-platform-review-evidence.py
python3 scripts/test-review-governance.py
```

Expected: PASS.

### Task 3: Add reviewer rotation and escalation recommendations

**Files:**
- Create: `scripts/test-reviewer-rotation.py`
- Create: `scripts/reviewer_rotation_lib.py`
- Create: `scripts/recommend-reviewers.py`
- Modify: `scripts/request-review.sh`
- Modify: `scripts/review-status.py`
- Modify: `docs/review-workflow.md`
- Modify: `docs/ai/agent-operations.md`

**Step 1: Write the failing test**

Create `scripts/test-reviewer-rotation.py` with fixture scenarios that:

- define review groups and team-backed reviewers in policy
- create skills with owner constraints and partial approval coverage
- assert `python3 scripts/recommend-reviewers.py <skill> --as-active --json` returns:
  - recommended reviewers grouped by missing review group
  - exclusion reasons such as owner-conflict or already-counted reviewer
  - escalation guidance when no eligible reviewer exists for one required group
- assert `scripts/request-review.sh <skill>` and `python3 scripts/review-status.py <skill> --as-active` can surface or reference the same suggestion data without mutating policy

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-reviewer-rotation.py
```

Expected: FAIL because no reviewer recommendation tooling exists yet.

**Step 3: Implement deterministic reviewer guidance**

Build a small recommendation library that:

- starts from the effective quorum rule and configured review groups
- removes ineligible reviewers such as owners when forbidden, already-counted reviewers, and reviewers from already-covered groups when appropriate
- ranks remaining candidates using deterministic, repo-local signals such as configured group order and recent review participation
- emits escalation guidance when a required group cannot currently be satisfied

Keep the first pass read-only and advisory.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-reviewer-rotation.py
python3 scripts/test-review-governance.py
```

Expected: PASS.

### Task 4: Run full verification and capture the governance-planning start commit

**Files:**
- Modify: any files changed above

**Step 1: Run targeted checks**

Run:

```bash
python3 scripts/test-platform-review-evidence.py
python3 scripts/test-reviewer-rotation.py
python3 scripts/test-review-governance.py
```

Expected: PASS.

**Step 2: Run full verification**

Run:

```bash
./scripts/check-all.sh
```

Expected: PASS, with the existing hosted-registry e2e environment skip if Python extras remain unavailable.

**Step 3: Commit**

Run:

```bash
git add .planning/PROJECT.md .planning/REQUIREMENTS.md .planning/ROADMAP.md .planning/STATE.md docs/plans/2026-03-17-platform-native-review-evidence-and-reviewer-rotation.md scripts/test-platform-review-evidence.py scripts/review_evidence_lib.py schemas/review-evidence.schema.json scripts/review_lib.py scripts/review-status.py scripts/import-platform-review-evidence.py scripts/check-promotion-policy.py scripts/build-catalog.sh scripts/release_lib.py scripts/provenance_payload_lib.py scripts/test-reviewer-rotation.py scripts/reviewer_rotation_lib.py scripts/recommend-reviewers.py scripts/request-review.sh docs/review-workflow.md docs/promotion-policy.md docs/ai/agent-operations.md
git commit -m "feat: integrate platform review evidence"
```
