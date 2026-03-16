# Production Signer Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the repository's signer bootstrap from a one-time milestone into a maintained operator surface by adding a repository-level signing readiness report, syncing signer docs to the real post-bootstrap state, and updating planning files to reflect the completed stable release ceremony.

**Architecture:** Reuse the existing signing bootstrap, doctor, and release-state helpers to build one repository-level readiness reporter that summarizes trusted signer enrollment, local git signing configuration, publisher authorization, and released-artifact verification for the canonical active skill. Then update signer-facing docs and `.planning` to consume that real state instead of continuing to describe `config/allowed_signers` as comment-only or the first stable release as still pending.

**Tech Stack:** Python 3.11 CLI scripts, existing `release_lib` / `signing_bootstrap_lib` helpers, Bash validation entrypoints, Markdown docs, and `.planning` project state files.

---

### Task 1: Add a repository-level signing readiness report with a failing test

**Files:**
- Create: `scripts/report-signing-readiness.py`
- Create: `scripts/test-signing-readiness-report.py`

**Step 1: Write the failing test**

Create a focused integration test that prepares a temp repository in two states:

1. bootstrap pending:
   - empty `config/allowed_signers`
   - no configured signing key
   - no stable tag or provenance for the fixture skill
2. bootstrap complete:
   - committed allowed signer entry for `release-test`
   - configured SSH signing key that matches the trusted entry
   - publisher authorization for the signer and releaser
   - pushed signed stable tag plus verified provenance for the fixture skill

Assert that the new report command returns JSON like:

```json
{
  "overall_status": "warn",
  "trusted_signers": {
    "count": 0
  },
  "skills": [
    {
      "name": "bootstrap-fixture",
      "release_ready": false,
      "tag": {
        "present": false
      },
      "provenance": {
        "verified": false
      }
    }
  ]
}
```

and then, after the fixture bootstrap and release ceremony:

```json
{
  "overall_status": "ok",
  "trusted_signers": {
    "count": 1,
    "identities": ["release-test"]
  },
  "skills": [
    {
      "name": "bootstrap-fixture",
      "release_ready": true,
      "tag": {
        "present": true,
        "verified": true
      },
      "provenance": {
        "verified": true
      }
    }
  ]
}
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-signing-readiness-report.py
```

Expected: FAIL because `scripts/report-signing-readiness.py` does not exist yet.

**Step 3: Write the minimal implementation**

Implement `scripts/report-signing-readiness.py` so it:

- accepts `--skill` (repeatable) plus `--json`
- loads `config/signing.json` and parses `config/allowed_signers`
- resolves the configured SSH signing key, if any, and whether it matches a trusted signer identity
- resolves publisher authorization for the inspected skill(s)
- checks stable release state and provenance verification by reusing existing release and attestation helpers
- emits a compact machine-readable summary with `overall_status`, trusted signer facts, signing-key facts, and per-skill tag / provenance / policy readiness

**Step 4: Re-run the test**

Run:

```bash
python3 scripts/test-signing-readiness-report.py
```

Expected: PASS.

### Task 2: Wire the readiness report into validation and steady-state signer docs

**Files:**
- Modify: `scripts/check-all.sh`
- Modify: `docs/signing-bootstrap.md`
- Modify: `docs/release-strategy.md`
- Modify: `docs/distribution-manifests.md`
- Create: `docs/signing-operations.md`

**Step 1: Write the failing doc/validation regression test**

Extend `scripts/test-signing-readiness-report.py` with assertions that the command:

- can inspect the repository's real `operate-infinitas-skill` release state
- reports `lvxiaoer` as a trusted signer when run against the checked-in repository
- keeps working when multiple `--skill` values are provided

This should fail until the implementation and validation wiring support the real repository flow.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-signing-readiness-report.py
```

Expected: FAIL because the command does not yet support the real repo or multi-skill output.

**Step 3: Implement the minimal validation and doc updates**

- Add `python3 scripts/test-signing-readiness-report.py` to `scripts/check-all.sh`
- Update `docs/signing-bootstrap.md` so it explicitly distinguishes:
  - how a fresh repo starts
  - the fact that this repository already has a committed trusted signer and released provenance
  - how operators check ongoing readiness with the new report
- Add `docs/signing-operations.md` covering:
  - daily readiness checks
  - adding another signer
  - replacing a signing key
  - verifying existing provenance without re-running a release
- Update `docs/release-strategy.md` and `docs/distribution-manifests.md` to point to the steady-state report instead of implying this repo is still blocked on first-time signer enrollment

**Step 4: Re-run the test and focused checks**

Run:

```bash
python3 scripts/test-signing-readiness-report.py
python3 scripts/report-signing-readiness.py --skill operate-infinitas-skill --json
```

Expected: PASS, and the report shows the checked-in signer / tag / provenance as ready.

### Task 3: Sync `.planning` to the post-bootstrap signer reality

**Files:**
- Modify: `.planning/PROJECT.md`
- Modify: `.planning/STATE.md`
- Modify: `.planning/ROADMAP.md`

**Step 1: Write the failing regression check**

Use the new readiness report output as the source of truth and add a targeted assertion to `scripts/test-signing-readiness-report.py` that the checked-in repository no longer has to describe:

- `config/allowed_signers` as comments-only
- trusted signer enrollment as still pending
- the first production stable release ceremony as not yet complete

Expected failure mode: the docs still contain those stale statements.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-signing-readiness-report.py
```

Expected: FAIL because `.planning` and signer docs still describe the pre-bootstrap state.

**Step 3: Update planning state**

Sync the planning files so they state that:

- `config/allowed_signers` contains a committed `lvxiaoer` trusted signer entry
- `operate-infinitas-skill` already has a signed pushed stable tag and verified provenance
- the current post-v12 follow-up is operational readiness and maintenance, not first-time signer bootstrap

Keep the remaining open question focused on follow-on roadmap choice after this closeout.

**Step 4: Re-run the readiness test**

Run:

```bash
python3 scripts/test-signing-readiness-report.py
```

Expected: PASS.

### Task 4: Verify the repository end-to-end and capture the closeout commit

**Files:**
- Modify: any generated docs or scripts changed above

**Step 1: Run focused verification**

Run:

```bash
python3 scripts/test-signing-readiness-report.py
python3 scripts/report-signing-readiness.py --skill operate-infinitas-skill --json
```

Expected: PASS.

**Step 2: Run full verification**

Run:

```bash
./scripts/check-all.sh
```

Expected: PASS, with the existing hosted-registry e2e environment skip if the Python extras are still unavailable.

**Step 3: Commit**

Run:

```bash
git add scripts/report-signing-readiness.py scripts/test-signing-readiness-report.py scripts/check-all.sh docs/signing-bootstrap.md docs/signing-operations.md docs/release-strategy.md docs/distribution-manifests.md .planning/PROJECT.md .planning/STATE.md .planning/ROADMAP.md
git commit -m "feat: add signing readiness reporting"
```

**Step 4: Prepare merge handoff**

Document the verification evidence, summarize any remaining roadmap decisions, and then use the finishing workflow before merging back to `main`.
