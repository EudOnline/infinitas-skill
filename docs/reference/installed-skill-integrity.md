---
audience: contributors, integrators, operators
owner: repository maintainers
source_of_truth: installed skill integrity reference
last_reviewed: 2026-03-30
status: maintained
---

# Installed Skill Integrity

Installed skills are not trusted just because they were once installed from a verified distribution manifest. Local runtime files can still drift afterward through manual edits, partial copy failures, or accidental overwrite.

The installed-integrity workflow extends v15's signed `file_manifest` into the local runtime directory:

1. read the installed entry from `.infinitas-skill-install-manifest.json`
2. re-verify the recorded immutable distribution manifest and attestation
3. compare the installed local files against the signed released-file inventory
4. report whether the runtime copy is still trustworthy

## Commands

Verify one installed skill:

```bash
python3 scripts/verify-installed-skill.py my-skill ~/.openclaw/skills --json
```

Report the currently recorded integrity summary for all installed skills:

```bash
python3 scripts/report-installed-integrity.py ~/.openclaw/skills --json
```

Refresh the target-local summary and append additive audit history:

```bash
python3 scripts/report-installed-integrity.py ~/.openclaw/skills --refresh --json
```

Repair one drifted install back to its recorded immutable source:

```bash
scripts/repair-installed-skill.sh my-skill ~/.openclaw/skills
```

## Integrity States

- `verified`: the installed local files still match the signed released-file inventory recorded by the immutable distribution source
- `drifted`: one or more local files are missing, modified, or unexpected compared with the signed released-file inventory
- `repaired`: not a persisted steady-state value; it describes the action where `repair-installed-skill.sh` restores the install and the follow-up verification returns `verified`
- `unknown`: the install manifest does not yet carry enough immutable source metadata to compare local files against a signed released-file inventory

For legacy immutable releases, `unknown` is often a manifest-shape problem instead of an install problem. After backfilling the referenced distribution manifest in place, the same installed runtime copy can move to `verified` without reinstalling:

```bash
python3 scripts/backfill-distribution-manifests.py --manifest <distribution-manifest> --write --json
python3 scripts/verify-installed-skill.py <name> <target-dir> --json
```

`verify-installed-skill.py` stays read-only. `report-installed-integrity.py --refresh` is the command that re-runs verification and writes refreshed summary fields back into `.infinitas-skill-install-manifest.json`.

## Drift Report

`verify-installed-skill.py --json` reports additive arrays for:

- `modified_files`
- `missing_files`
- `unexpected_files`

It also reports compact summary counters such as:

- `release_file_manifest_count`
- `checked_file_count`
- `modified_count`
- `missing_count`
- `unexpected_count`

This keeps both humans and wrappers on the same contract without scraping stdout text.

`report-installed-integrity.py --json` adds a stable per-skill summary layer:

- `integrity_capability`
- `integrity_reason`
- `integrity_events`
- `freshness_state`
- `checked_age_seconds`
- `last_checked_at`
- `recommended_action`
- top-level `last_verified_at`

`freshness_state` is additive target-local interpretation, not a replacement for immutable verification:

- `fresh`: the most recent local check is still within the configured freshness window
- `stale`: the installed copy may still be clean, but the last local check is older than the configured freshness window
- `never-verified`: the manifest does not carry enough local timing information to classify freshness yet

`recommended_action` is intentionally compact:

- `none` when the installed copy is still `verified`
- `repair` when the installed copy is `drifted`
- `refresh` when the local integrity summary is still clean but older than the configured freshness window
- `backfill-distribution-manifest` when the recorded immutable release is legacy and still missing a signed `file_manifest`
- `reinstall` when the install lacks enough immutable source metadata to refresh trust locally

Freshness policy is repo-managed configuration, not a new persisted install-manifest requirement:

```json
{
  "freshness": {
    "stale_after_hours": 168,
    "stale_policy": "warn",
    "never_verified_policy": "warn"
  }
}
```

- `freshness.stale_policy`: controls stale-but-clean installs
- `freshness.never_verified_policy`: controls installs that lack any usable local verification timestamp
- `ignore`: keep the state additive only
- `warn`: print the recommended recovery path before overwrite-style mutation
- `fail`: refuse overwrite-style mutation until the recommended recovery path has re-established trust

`stale_policy` applies only to stale-but-clean installs. `never_verified_policy` applies to `never-verified` installs, including legacy manifests that do not yet carry enough timing data. Refreshable installs recommend `report-installed-integrity.py <target-dir> --refresh`; compatibility-only installs without enough immutable source metadata recommend reinstall or manifest backfill instead.

## Repair Workflow

When a skill is `drifted`, prefer repair over silent overwrite:

1. run `python3 scripts/verify-installed-skill.py <name> <target-dir> --json`
2. inspect the reported drift paths
3. run `scripts/repair-installed-skill.sh <name> <target-dir>`
4. verify again to confirm the state is back to `verified`

`repair-installed-skill.sh` is exact-source and manifest-driven:

- it reuses the recorded `source_qualified_name`
- it reuses the recorded `source_registry`
- it prefers the recorded `locked_version` or installed version
- it restores the same immutable release rather than guessing the latest available version

## Guardrails

Mutation commands such as:

- `uv run infinitas install sync`
- `uv run infinitas install upgrade`
- `uv run infinitas install switch`
- `uv run infinitas install rollback`

now follow one guard order before overwriting local files:

1. detected `drifted` state still blocks first and points operators to `verify-installed-skill.py` or `repair-installed-skill.sh`
2. stale-but-clean installs then consult `freshness.stale_policy`
3. `never-verified` installs then consult `freshness.never_verified_policy`
4. `warn` emits the matching recovery guidance and continues
5. `fail` stops and tells the operator to refresh, repair, reinstall, or backfill first
6. `--force` is an explicit bypass for these local overwrite guardrails

This keeps immutable release verification separate from target-local freshness. A skill can still be `integrity.state = verified` while `freshness_state = stale`.

Use `--force` only when you intentionally want to overwrite the local runtime copy despite detected drift.

## Decision Matrix

Use this matrix when you need to predict what overwrite-style mutation will do:

| Local condition | Policy consulted | Default readiness | Recommended recovery |
| --- | --- | --- | --- |
| `integrity.state = drifted` | none, drift always wins first | `blocked` | `repair` |
| `freshness_state = stale` and install is otherwise clean | `freshness.stale_policy` | `warning` under the default `warn` policy | `refresh` |
| `freshness_state = never-verified` and immutable source metadata supports refresh | `freshness.never_verified_policy` | `warning` under the default `warn` policy | `refresh` |
| `freshness_state = never-verified` and immutable source metadata is compatibility-only | `freshness.never_verified_policy` | `warning` under the default `warn` policy | `backfill-distribution-manifest` or `reinstall` |
| explicit `--force` | bypasses local readiness guardrails | forced overwrite | use only when intentionally bypassing the target-local safety checks |

`infinitas install upgrade --mode confirm`, `infinitas install check-update`, `report-installed-integrity.py`, and the overwrite-style mutation commands all consume the same derived readiness fields so wrappers do not need separate per-command policy logic.

## Trust Boundary

The workflow remains offline-verifiable and manifest-driven:

- it does not require a hosted control plane
- it does not trust mutable working-tree folders as the verification source
- it relies on the immutable distribution manifest and signed attestation already recorded in the local install manifest

For hosted installs, the toolchain now persists the fetched immutable distribution artifacts under a target-local cache root and records that root in the install manifest. Later explicit verification reuses that cached immutable set rather than resolving back through a mutable repo checkout copy.

If the install lacks those immutable references, the integrity state remains `unknown` until the skill is reinstalled, repaired from a verified immutable source, or the referenced legacy distribution manifest is backfilled.

## Steady-State Verification

Repository steady-state verification guidance is documented in `../project-closeout.md`.

- CI installs the hosted-registry dependency set with `python3 -m pip install .` and runs `scripts/check-all.sh` with `INFINITAS_REQUIRE_HOSTED_E2E_TESTS=1`.
- Minimal local environments may still skip `scripts/test-hosted-registry-e2e.py` until that same dependency set is installed explicitly.
- The project is already complete on `main`; these notes describe the supported maintenance baseline, not an unfinished merge gate.
- The remaining compatibility quirks are accepted non-blocking maintenance notes unless a concrete user-facing defect appears.

## Audit History

Install-manifest entries now preserve additive trust metadata alongside the nested `integrity` record:

```json
{
  "last_checked_at": "2026-03-19T10:05:00Z",
  "integrity_capability": "supported",
  "integrity_reason": null,
  "integrity_events": [
    {
      "at": "2026-03-19T10:00:00Z",
      "event": "verified",
      "source": "install"
    },
    {
      "at": "2026-03-19T10:05:00Z",
      "event": "drifted",
      "source": "refresh"
    }
  ]
}
```

Current writers also keep only bounded recent `integrity_events` inline. `report-installed-integrity.py --refresh` writes or refreshes one target-local snapshot/history artifact at:

```text
.infinitas-skill-installed-integrity.json
```

That sidecar keeps the current report snapshot plus older overflow history under `archived_integrity_events`:

```json
{
  "schema_version": 1,
  "generated_at": "2026-03-19T10:05:00Z",
  "target_dir": "/Users/example/.openclaw/skills",
  "skills": [
    {
      "name": "demo-skill",
      "freshness_state": "fresh",
      "integrity_events": [
        {
          "at": "2026-03-19T10:04:00Z",
          "event": "verified",
          "source": "refresh"
        }
      ],
      "archived_integrity_events": [
        {
          "at": "2026-03-18T10:00:00Z",
          "event": "verified",
          "source": "install"
        }
      ]
    }
  ]
}
```

These fields are additive. Older manifests without `integrity_capability`, `integrity_reason`, `integrity_events`, or `last_checked_at` still load, while current writers emit the canonical expanded shape. Missing `.infinitas-skill-installed-integrity.json` is tolerated; readers fall back to inline current state only.
