# Installed Skill Integrity And Repair Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend v15's signed release-file inventory into the local consumption path so installed skill directories can be audited for drift, repaired back to their exact immutable source, and guarded during sync or upgrade flows.

**Architecture:** Reuse the existing install manifest as the durable local state contract instead of inventing a second lock database. First add one verifier that loads the recorded immutable distribution source, verifies its attestation and distribution manifest, and compares the installed files against the signed `file_manifest`. Then persist a compact integrity summary into install-manifest entries and thread that status through read-only consumer surfaces plus a manifest-driven repair command and drift-aware update guardrails.

**Tech Stack:** Existing Bash CLI wrappers, Python 3.11 helper libraries, install-manifest JSON, distribution and attestation verification helpers, script-style regression tests in `scripts/test-*.py`, and Markdown operator and AI docs.

**Status:** Completed on `main` on 2026-03-18 via commit `a2490c1` (`feat: add installed skill integrity and repair flows`).

---

### Task 1: Add failing installed-integrity verifier coverage

**Files:**
- Create: `scripts/test-installed-skill-integrity.py`
- Create: `scripts/installed_integrity_lib.py`
- Create: `scripts/verify-installed-skill.py`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/history-and-snapshots.md`

**Step 1: Write the failing test**

Create `scripts/test-installed-skill-integrity.py` with fixture scenarios that:

- release and install one stable fixture skill into a temp target using the existing immutable distribution path
- run `python3 scripts/verify-installed-skill.py <installed-name> <target-dir> --json`
- assert the clean result exposes:
  - `state = "verified"`
  - `qualified_name`
  - `installed_version`
  - `source_distribution_manifest`
  - `source_attestation_path`
  - `release_file_manifest_count`
  - `checked_file_count`
  - empty `modified_files`, `missing_files`, and `unexpected_files`
- then modify one installed file, delete one expected file, and add one unexpected file inside the installed skill directory
- assert the verifier returns `state = "drifted"` and reports the exact relative paths in additive arrays such as:

```json
{
  "state": "drifted",
  "modified_files": ["SKILL.md"],
  "missing_files": ["tests/smoke.md"],
  "unexpected_files": ["local-notes.txt"]
}
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
```

Expected: FAIL because no installed-skill verifier or drift-report contract exists yet.

**Step 3: Implement the minimal verifier**

Add a small installed-integrity helper that:

- loads the installed skill entry from `.infinitas-skill-install-manifest.json`
- requires a recorded immutable source such as `source_distribution_manifest` plus attestation references
- verifies the referenced distribution manifest and signed attestation before trusting the local comparison target
- compares files under `<target-dir>/<installed-name>/` against the signed `file_manifest`
- reports missing, modified, and unexpected files using repo-relative or skill-relative paths only
- supports both human-readable output and `--json`

Keep the first pass read-only and additive. Do not mutate the install manifest yet.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-distribution-install.py
```

Expected: PASS.

### Task 2: Persist integrity state in install manifests and read-only status surfaces

**Files:**
- Modify: `scripts/test-installed-skill-integrity.py`
- Modify: `scripts/test-install-manifest-compat.py`
- Modify: `scripts/test-skill-update.py`
- Modify: `scripts/update-install-manifest.py`
- Modify: `scripts/install_manifest_lib.py`
- Modify: `scripts/installed_skill_lib.py`
- Modify: `scripts/list-installed.sh`
- Modify: `scripts/check-skill-update.sh`
- Modify: `docs/compatibility-contract.md`
- Modify: `docs/ai/discovery.md`

**Step 1: Extend the failing tests**

Add scenarios that:

- assert install-manifest entries now preserve an additive `integrity` block such as:

```json
{
  "integrity": {
    "state": "verified",
    "last_verified_at": "2026-03-18T08:00:00Z",
    "checked_file_count": 3,
    "release_file_manifest_count": 3,
    "modified_count": 0,
    "missing_count": 0,
    "unexpected_count": 0
  }
}
```

- assert legacy manifests without `integrity` still load and normalize cleanly
- assert `scripts/list-installed.sh` prints a compact integrity summary for each installed skill
- assert `scripts/check-skill-update.sh` includes additive integrity fields in JSON output and surfaces when an installed copy is drifted, even if an update is available

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-skill-update.py
```

Expected: FAIL because install-manifest entries and consumer status surfaces do not yet preserve integrity state.

**Step 3: Implement additive manifest and status updates**

Update the install-manifest pipeline so it:

- records a compact integrity summary after successful install-like mutations
- keeps all new fields additive and backward-compatible
- defaults missing integrity state to `unknown` instead of failing old installs
- exposes the same state through `installed_skill_lib.py`, `list-installed.sh`, and `check-skill-update.sh`

Do not require a network round-trip for read-only status views; they should rely on recorded local state plus existing source checks.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-skill-update.py
```

Expected: PASS.

### Task 3: Add exact-source repair and drift-aware update guardrails

**Files:**
- Modify: `scripts/test-installed-skill-integrity.py`
- Create: `scripts/repair-installed-skill.sh`
- Modify: `scripts/sync-skill.sh`
- Modify: `scripts/switch-installed-skill.sh`
- Modify: `scripts/rollback-installed-skill.sh`
- Modify: `scripts/upgrade-skill.sh`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/history-and-snapshots.md`
- Modify: `docs/ai/pull.md`

**Step 1: Extend the failing tests**

Add scenarios that:

- drift one installed fixture and assert `scripts/repair-installed-skill.sh <name> <target-dir>` restores the exact recorded immutable version
- assert repair reuses the stored `source_qualified_name`, `source_registry`, `locked_version`, and distribution-manifest metadata instead of guessing a newer version
- assert `sync-skill.sh`, `switch-installed-skill.sh`, `rollback-installed-skill.sh`, and `upgrade-skill.sh` refuse to overwrite drifted local files unless `--force` is explicitly provided
- assert the failure payload or stderr tells the operator to run `verify-installed-skill.py` or `repair-installed-skill.sh`

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-skill-update.py
```

Expected: FAIL because repair flow and drift-aware mutation guardrails do not exist yet.

**Step 3: Implement repair and guardrails**

Add a repair command that:

- loads the installed-skill manifest entry
- resolves the exact recorded immutable source, preferring the recorded version lock and source registry
- reinstalls atomically into the same target directory
- updates the install-manifest integrity block after the repair succeeds

Then thread the same integrity check into sync, switch, rollback, and upgrade flows so:

- clean installs proceed normally
- drifted installs fail with an actionable message by default
- `--force` remains the explicit override for intentional destructive replacement

**Step 4: Re-run targeted verification**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-skill-update.py
python3 scripts/test-distribution-install.py
```

Expected: PASS.

### Task 4: Document the installed-integrity workflow and harden end-to-end regression

**Files:**
- Modify: `scripts/test-installed-skill-integrity.py`
- Modify: `scripts/test-distribution-install.py`
- Create: `docs/installed-skill-integrity.md`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/history-and-snapshots.md`
- Modify: `docs/compatibility-contract.md`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/ai/pull.md`

**Step 1: Extend the failing test and doc expectations**

Add assertions that:

- end-to-end install regression covers verify -> drift -> repair
- operator docs describe when to audit an installed skill, how to interpret drift, and how to repair it back to the recorded immutable source
- AI-facing docs explain that repair is the preferred path over silent overwrite when local runtime files no longer match signed release metadata

**Step 2: Run the focused checks to verify they fail**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-distribution-install.py
```

Expected: FAIL because the new workflow is not yet documented or exercised end to end.

**Step 3: Implement the docs and regression updates**

Document:

- `verify-installed-skill.py`
- `repair-installed-skill.sh`
- the meaning of `verified`, `drifted`, `repaired`, and `unknown`
- how `--force` interacts with drift-aware guardrails
- why the workflow remains offline-verifiable and manifest-driven

Keep the docs explicit that repair and verification depend on recorded immutable source metadata, not mutable working-tree guesses.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-distribution-install.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-skill-update.py
```

Expected: PASS.

### Task 5: Run full verification and commit

**Files:**
- Modify: any files changed above

**Step 1: Run targeted checks**

Run:

```bash
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-distribution-install.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-skill-update.py
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
git add docs/plans/2026-03-18-installed-skill-integrity-and-repair.md scripts/test-installed-skill-integrity.py scripts/installed_integrity_lib.py scripts/verify-installed-skill.py scripts/repair-installed-skill.sh scripts/test-distribution-install.py scripts/test-install-manifest-compat.py scripts/test-skill-update.py scripts/update-install-manifest.py scripts/install_manifest_lib.py scripts/installed_skill_lib.py scripts/list-installed.sh scripts/check-skill-update.sh scripts/sync-skill.sh scripts/switch-installed-skill.sh scripts/rollback-installed-skill.sh scripts/upgrade-skill.sh docs/distribution-manifests.md docs/history-and-snapshots.md docs/installed-skill-integrity.md docs/compatibility-contract.md docs/ai/discovery.md docs/ai/pull.md
git commit -m "feat: add installed skill integrity and repair flows"
```
