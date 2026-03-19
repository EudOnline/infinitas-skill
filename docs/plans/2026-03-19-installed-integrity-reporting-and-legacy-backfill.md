# Installed Integrity Reporting And Legacy Backfill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce avoidable installed-integrity `unknown` states by backfilling legacy immutable distribution manifests where signed evidence already exists, then add a stable local report surface for installed-skill trust and repair history.

**Architecture:** Reuse the existing immutable artifact chain instead of inventing a second release format. First add one deterministic backfill path that regenerates missing `file_manifest` and build metadata from committed provenance plus bundle artifacts, then thread a capability summary into release or discovery surfaces. After that, extend the existing install-manifest contract with additive integrity audit events and one local reporting command that can summarize or refresh installed-skill trust without requiring a hosted service.

**Tech Stack:** Existing Bash CLI wrappers, Python 3.11 helper libraries, distribution or attestation verification helpers, install-manifest JSON, generated catalog exports, script-style regression tests in `scripts/test-*.py`, and Markdown operator plus AI docs.

---

### Task 1: Add failing legacy-backfill coverage

**Files:**
- Create: `scripts/test-legacy-distribution-backfill.py`
- Modify: `scripts/test-hosted-registry-install.py`
- Modify: `scripts/test-distribution-install.py`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/installed-skill-integrity.md`

**Step 1: Write the failing tests**

Create `scripts/test-legacy-distribution-backfill.py` with scenarios that:

- copies one legacy distribution manifest fixture that lacks `file_manifest`
- runs `python3 scripts/backfill-distribution-manifests.py --manifest <path> --write --json`
- asserts the rewritten manifest now contains:
  - non-empty `file_manifest`
  - normalized `build`
  - unchanged bundle path, digest, attestation refs, and source snapshot identity
- reruns the same command and asserts the second pass reports `state = "unchanged"` instead of rewriting again

Extend `scripts/test-hosted-registry-install.py` so it can:

- serve the current legacy hosted fixture and assert install still lands on `integrity.state = "unknown"`
- then backfill the served manifest before install and assert the same hosted install now lands on `integrity.state = "verified"`
- assert explicit `verify-installed-skill.py --json` succeeds after backfill and still fails before backfill

Extend `scripts/test-distribution-install.py` so one immutable install fixture can verify successfully when its distribution manifest has been backfilled in place.

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-legacy-distribution-backfill.py
python3 scripts/test-hosted-registry-install.py
```

Expected: FAIL because no legacy-backfill tool or capability contract exists yet.

**Step 3: Implement the minimal backfill contract**

Define the backfill behavior so the future tool:

- loads one existing distribution manifest
- verifies that signed provenance plus bundle artifacts still exist
- regenerates the canonical manifest payload from those immutable artifacts
- preserves immutable identity fields instead of guessing new release metadata
- writes only additive missing metadata such as `file_manifest` and normalized `build`
- reports whether the manifest was `backfilled`, already `unchanged`, or cannot be upgraded because immutable evidence is incomplete

Keep the first pass file-local and deterministic. Do not bundle audit-history or install-manifest work into this task.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-legacy-distribution-backfill.py
python3 scripts/test-hosted-registry-install.py
python3 scripts/test-distribution-install.py
```

Expected: PASS.

### Task 2: Thread legacy-backfill and integrity capability through release surfaces

**Files:**
- Create: `scripts/backfill-distribution-manifests.py`
- Modify: `scripts/distribution_lib.py`
- Modify: `scripts/generate-distribution-manifest.py`
- Modify: `scripts/build-catalog.sh`
- Modify: `scripts/test-audit-inventory-exports.py`
- Modify: `docs/release-strategy.md`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/distribution-manifests.md`

**Step 1: Extend the failing tests**

Add assertions that:

- one manifest index entry now reports an additive installed-integrity capability summary, for example:

```json
{
  "file_manifest_count": 12,
  "installed_integrity_capability": "supported"
}
```

- legacy manifests that still cannot be backfilled expose a compatibility-only state such as:

```json
{
  "installed_integrity_capability": "unknown",
  "installed_integrity_reason": "missing-signed-file-manifest"
}
```

- `catalog/catalog.json`, `catalog/distributions.json`, and AI or discovery guidance surface whether a released version fully supports installed-integrity verification
- `audit-export.json` continues to remain release-scoped and does not try to absorb local installed-runtime state

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-legacy-distribution-backfill.py
python3 scripts/test-audit-inventory-exports.py
```

Expected: FAIL because release or discovery surfaces do not yet expose the installed-integrity capability summary.

**Step 3: Implement capability reporting**

Add the backfill tool and release-surface updates so they:

- support `--manifest <path>` plus repo-root scanning modes
- emit machine-readable status for each inspected manifest
- reuse `build_distribution_manifest_payload(...)` as the canonical manifest builder rather than duplicating normalization logic
- expose an additive capability summary through `distribution_lib.py` and generated catalog surfaces
- keep repo-scoped exports focused on immutable artifact capability, not local installed state

Do not add network requirements or hosted backends. This remains a repo-local artifact maintenance flow.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-legacy-distribution-backfill.py
python3 scripts/test-hosted-registry-install.py
python3 scripts/test-distribution-install.py
python3 scripts/test-audit-inventory-exports.py
```

Expected: PASS.

### Task 3: Add failing installed-integrity report and audit-history coverage

**Files:**
- Create: `scripts/test-installed-integrity-report.py`
- Modify: `scripts/test-installed-skill-integrity.py`
- Modify: `scripts/test-install-manifest-compat.py`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/compatibility-contract.md`

**Step 1: Write the failing tests**

Create `scripts/test-installed-integrity-report.py` with scenarios that:

- installs one released fixture skill into a temp target
- runs `python3 scripts/report-installed-integrity.py <target-dir> --json`
- asserts each reported skill includes:
  - `qualified_name`
  - `installed_version`
  - `integrity.state`
  - `integrity_capability`
  - `last_verified_at`
  - `recommended_action`
  - additive `integrity_events`
- drifts one installed file, reruns `python3 scripts/report-installed-integrity.py <target-dir> --refresh --json`, and asserts the manifest plus report now capture a `drifted` event
- repairs the same skill and asserts the event trail includes a later `repaired` or `verified` outcome with a fresh timestamp

Extend compatibility coverage so legacy install manifests still normalize cleanly with:

- missing `integrity_events`
- missing capability fields
- report output that defaults those fields additively instead of failing older installs

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-install-manifest-compat.py
```

Expected: FAIL because no local installed-integrity report surface or additive audit-history contract exists yet.

**Step 3: Define the report and audit-history contract**

Design the report so it stays local and manifest-driven:

- `report-installed-integrity.py <target-dir> --json` reads installed entries and prints a stable summary per skill
- `--refresh` may re-run live verification and write the refreshed summary back into the install manifest
- install-manifest entries preserve additive fields such as:

```json
{
  "integrity_capability": "supported",
  "integrity_reason": null,
  "integrity_events": [
    {
      "at": "2026-03-19T10:00:00Z",
      "event": "verified",
      "source": "install"
    }
  ]
}
```

Keep `verify-installed-skill.py` read-only; the new report surface is where refresh-and-record behavior belongs.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-install-manifest-compat.py
```

Expected: PASS.

### Task 4: Implement local installed-integrity reporting and docs

**Files:**
- Create: `scripts/report-installed-integrity.py`
- Modify: `scripts/install_manifest_lib.py`
- Modify: `scripts/installed_integrity_lib.py`
- Modify: `scripts/update-install-manifest.py`
- Modify: `scripts/repair-installed-skill.sh`
- Modify: `scripts/list-installed.sh`
- Modify: `scripts/test-installed-integrity-report.py`
- Modify: `scripts/test-installed-skill-integrity.py`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/compatibility-contract.md`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/ai/pull.md`
- Modify: `docs/federation-operations.md`

**Step 1: Extend the failing tests and docs expectations**

Add assertions that:

- install and repair flows append additive integrity events without breaking older manifests
- `list-installed.sh` can surface capability or event-count hints without scraping raw JSON
- docs explain the difference between:
  - repository-scoped immutable release exports such as `catalog/audit-export.json`
  - target-local installed-integrity reports from `report-installed-integrity.py`

**Step 2: Run the focused checks to verify they fail**

Run:

```bash
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-install-manifest-compat.py
```

Expected: FAIL because install-manifest writes and docs do not yet preserve or explain the local report contract.

**Step 3: Implement the local reporting flow**

Update the installed-integrity pipeline so it:

- normalizes additive capability and event fields in `install_manifest_lib.py`
- records install or repair outcomes in `update-install-manifest.py` and repair flows
- lets `report-installed-integrity.py --refresh` reuse the existing verifier and write refreshed summary fields back into the manifest
- keeps `verify-installed-skill.py` focused on explicit read-only verification
- points AI guidance at the local report when the operator needs target-local trust state, not repo-scoped release evidence

Do not collapse local install reporting into catalog exports. They solve different trust questions.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-hosted-registry-install.py
python3 scripts/test-audit-inventory-exports.py
```

Expected: PASS.

### Task 5: Run full verification and commit

**Files:**
- Modify: any files changed above

**Step 1: Run targeted checks**

Run:

```bash
python3 scripts/test-legacy-distribution-backfill.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-distribution-install.py
python3 scripts/test-hosted-registry-install.py
python3 scripts/test-install-manifest-compat.py
python3 scripts/test-audit-inventory-exports.py
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
git add docs/plans/2026-03-19-installed-integrity-reporting-and-legacy-backfill.md .planning/PROJECT.md .planning/REQUIREMENTS.md .planning/ROADMAP.md .planning/STATE.md scripts/backfill-distribution-manifests.py scripts/test-legacy-distribution-backfill.py scripts/report-installed-integrity.py scripts/test-installed-integrity-report.py scripts/install_manifest_lib.py scripts/installed_integrity_lib.py scripts/update-install-manifest.py scripts/repair-installed-skill.sh scripts/list-installed.sh scripts/distribution_lib.py scripts/generate-distribution-manifest.py scripts/build-catalog.sh scripts/test-hosted-registry-install.py scripts/test-distribution-install.py scripts/test-installed-skill-integrity.py scripts/test-install-manifest-compat.py scripts/test-audit-inventory-exports.py docs/distribution-manifests.md docs/installed-skill-integrity.md docs/release-strategy.md docs/compatibility-contract.md docs/ai/discovery.md docs/ai/pull.md docs/federation-operations.md
git commit -m "feat: add installed integrity reporting and legacy backfill"
```
