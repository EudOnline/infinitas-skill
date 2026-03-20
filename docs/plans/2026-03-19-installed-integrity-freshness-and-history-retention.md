# Installed Integrity Freshness And History Retention Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep target-local installed-integrity state trustworthy over time by adding explicit freshness classification plus bounded audit-history retention for long-lived install targets.

**Architecture:** Reuse v17's manifest-driven installed-integrity report as the source of current local trust state. First add one validated freshness policy that classifies target-local verification as fresh, stale, or never verified without changing immutable release semantics, then introduce deterministic retention rules that keep current trust summary inline in `.infinitas-skill-install-manifest.json` while spilling older integrity events into a target-local sidecar snapshot/history artifact when event volume grows.

**Tech Stack:** Existing Bash and Python 3.11 CLI tooling, JSON schema validation, `.infinitas-skill-install-manifest.json`, a new install-integrity policy config, `scripts/report-installed-integrity.py`, `scripts/list-installed.sh`, focused regression tests in `scripts/test-*.py`, and Markdown operator plus AI docs.

---

### Task 1: Define the freshness policy and failing stale-report contract

**Files:**
- Create: `config/install-integrity-policy.json`
- Create: `schemas/install-integrity-policy.schema.json`
- Create: `scripts/test-installed-integrity-freshness.py`
- Modify: `scripts/test-installed-integrity-report.py`
- Modify: `scripts/test-install-manifest-compat.py`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/compatibility-contract.md`

**Step 1: Write the failing tests**

Create `scripts/test-installed-integrity-freshness.py` with scenarios that:

- build one temp install target with a manifest entry that was verified recently and assert the future report surface classifies it as `fresh`
- build one temp install target with an old `last_verified_at` and assert the same surface classifies it as `stale`
- build one legacy install target that never carried verification timestamps and assert it classifies as `never-verified`
- assert stale-but-clean installs recommend `refresh`, while drifted installs still recommend `repair`

Extend `scripts/test-installed-integrity-report.py` so the reported payload must include additive freshness fields such as:

- `freshness_state`
- `checked_age_seconds`
- `last_checked_at`

Extend `scripts/test-install-manifest-compat.py` so older manifests that lack freshness metadata still normalize cleanly and report deterministic defaults instead of failing.

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-install-manifest-compat.py
```

Expected: FAIL because no freshness policy or stale-report contract exists yet.

**Step 3: Define the freshness contract**

Add one repo-managed install-integrity policy with validated defaults, for example:

```json
{
  "schema_version": 1,
  "freshness": {
    "stale_after_hours": 168
  },
  "history": {
    "max_inline_events": 20
  }
}
```

Define the additive report fields so they stay target-local and do not leak into repo-scoped release exports:

- `freshness_state`: `fresh`, `stale`, or `never-verified`
- `checked_age_seconds`: integer age from the most recent local verification/check, or `null`
- `last_checked_at`: last local refresh/report write timestamp, or `null`

Keep the immutable release trust contract unchanged. This task only defines how target-local runtime state ages over time.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-install-manifest-compat.py
```

Expected: PASS.

### Task 2: Implement freshness classification in report and list flows

**Files:**
- Create: `scripts/install_integrity_policy_lib.py`
- Modify: `scripts/installed_integrity_lib.py`
- Modify: `scripts/report-installed-integrity.py`
- Modify: `scripts/list-installed.sh`
- Modify: `scripts/update-install-manifest.py`
- Modify: `scripts/check-all.sh`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/compatibility-contract.md`

**Step 1: Extend the failing tests**

Add assertions that:

- `report-installed-integrity.py --json` reads the repo policy and emits freshness classification for every skill
- `list-installed.sh` surfaces compact freshness hints without scraping raw manifest JSON
- freshly installed or freshly refreshed entries remain `fresh`
- stale entries preserve their prior integrity state (`verified` or `unknown`) while changing `recommended_action` to `refresh`

**Step 2: Run the focused tests to verify they fail**

Run:

```bash
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-installed-integrity-report.py
```

Expected: FAIL because report/list flows do not yet evaluate or surface freshness policy.

**Step 3: Implement the freshness flow**

Update the local installed-integrity pipeline so it:

- loads and validates `config/install-integrity-policy.json` through one shared helper library
- computes freshness from `last_checked_at` or `last_verified_at` without changing immutable verification logic
- keeps freshness additive in report/list surfaces instead of rewriting repo-scoped release metadata
- preserves compatibility for older manifests that lack freshness timestamps
- adds the new freshness regression test to `scripts/check-all.sh`

Do not introduce a daemon, background scheduler, or hosted service. This remains an explicit local operator workflow.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-install-manifest-compat.py
```

Expected: PASS.

### Task 3: Define bounded history retention and sidecar snapshot coverage

**Files:**
- Create: `schemas/installed-integrity-snapshot.schema.json`
- Create: `scripts/test-installed-integrity-history-retention.py`
- Modify: `scripts/test-installed-integrity-report.py`
- Modify: `scripts/test-install-manifest-compat.py`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/compatibility-contract.md`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/ai/pull.md`

**Step 1: Write the failing tests**

Create `scripts/test-installed-integrity-history-retention.py` with scenarios that:

- repeatedly refresh one target until integrity event history exceeds the policy `max_inline_events`
- assert the install manifest keeps only the newest inline events
- assert older events are retained in a deterministic target-local sidecar artifact such as `.infinitas-skill-installed-integrity.json`
- validate that the sidecar artifact contains both the current report snapshot and archived event history without scraping stdout text

Extend compatibility coverage so:

- old targets without any sidecar artifact still load and report successfully
- current readers can tolerate a missing sidecar file and fall back to inline history only
- current writers emit the canonical compact inline shape after refresh or snapshot export

**Step 2: Run the tests to verify they fail**

Run:

```bash
python3 scripts/test-installed-integrity-history-retention.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-install-manifest-compat.py
```

Expected: FAIL because no retention policy or sidecar snapshot contract exists yet.

**Step 3: Define the retention and snapshot contract**

Keep the install manifest focused on current state plus bounded recent history:

- `integrity`
- `integrity_capability`
- `integrity_reason`
- `last_checked_at`
- the newest `N` `integrity_events`

Define the target-local sidecar artifact so it is schema-governed and offline-usable, with fields such as:

- `generated_at`
- `target_dir`
- `policy`
- `skills`
- per-skill `archived_integrity_events`

The sidecar is target-local runtime state, not a repo export. It should never be treated as authoritative release evidence.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-installed-integrity-history-retention.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-install-manifest-compat.py
```

Expected: PASS.

### Task 4: Implement history compaction and sidecar snapshot export

**Files:**
- Modify: `scripts/install_manifest_lib.py`
- Modify: `scripts/installed_integrity_lib.py`
- Modify: `scripts/report-installed-integrity.py`
- Modify: `scripts/update-install-manifest.py`
- Modify: `scripts/list-installed.sh`
- Modify: `scripts/check-all.sh`
- Modify: `docs/installed-skill-integrity.md`
- Modify: `docs/compatibility-contract.md`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/ai/pull.md`

**Step 1: Extend the failing tests and docs expectations**

Add assertions that:

- refresh flows compact inline `integrity_events` to the configured bound while preserving older events in the sidecar artifact
- `report-installed-integrity.py --json` can optionally write or refresh the sidecar snapshot without requiring separate stdout scraping
- docs explain the boundary between:
  - inline current state in `.infinitas-skill-install-manifest.json`
  - historical spillover in `.infinitas-skill-installed-integrity.json`
  - repo-scoped immutable release evidence in catalog exports

**Step 2: Run the focused checks to verify they fail**

Run:

```bash
python3 scripts/test-installed-integrity-history-retention.py
python3 scripts/test-installed-integrity-report.py
```

Expected: FAIL because manifest writers do not yet compact history or emit a sidecar snapshot artifact.

**Step 3: Implement retention and export behavior**

Update the installed-integrity flow so it:

- compacts inline event history deterministically according to repo policy
- preserves archived older events in the target-local sidecar artifact
- lets `report-installed-integrity.py` write or refresh the sidecar snapshot on demand
- keeps `list-installed.sh` focused on current state and small summary hints instead of dumping archived history
- preserves compatibility for targets that predate the sidecar artifact

Do not make the sidecar artifact a repo-tracked export or add any background sync machinery. It is local runtime state.

**Step 4: Re-run verification**

Run:

```bash
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-installed-integrity-history-retention.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-skill-integrity.py
python3 scripts/test-install-manifest-compat.py
./scripts/check-all.sh
```

Expected: PASS, with the same environment-sensitive hosted-registry e2e skip behavior already documented by the repository.

## Suggested Commit Sequence

1. `test: add installed integrity freshness coverage`
2. `feat: add installed integrity freshness policy`
3. `test: add installed integrity history retention coverage`
4. `feat: add installed integrity sidecar snapshot retention`

## Verification Checklist

- `python3 scripts/test-installed-integrity-freshness.py`
- `python3 scripts/test-installed-integrity-history-retention.py`
- `python3 scripts/test-installed-integrity-report.py`
- `python3 scripts/test-installed-skill-integrity.py`
- `python3 scripts/test-install-manifest-compat.py`
- `./scripts/check-all.sh`

## Handoff Notes

- Keep all new state target-local and offline-usable; do not reintroduce repo-scoped runtime state.
- Preserve the dual-read/single-write compatibility rule for `.infinitas-skill-install-manifest.json`.
- Treat freshness as additive interpretation of local verification timestamps, not as a replacement for immutable artifact verification.
