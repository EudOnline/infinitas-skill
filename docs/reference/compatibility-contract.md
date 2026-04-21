---
audience: contributors, integrators, reviewers
owner: repository maintainers
source_of_truth: compatibility contract reference
last_reviewed: 2026-04-07
status: maintained
---

# Compatibility Contract

This document defines which parts of `infinitas-skill` are treated as compatibility promises and which parts are still implementation details that may evolve more freely.

## Stable surfaces

The following are currently treated as stable contracts unless a future deprecation notice says otherwise:

- `_meta.json` core identity and lifecycle fields: `name`, `version`, `status`, `summary`, `owner`, `review_state`, `risk_level`, `distribution`
- `_meta.json` compatibility-sensitive identity fields when present: `publisher`, `qualified_name`, `owners`, `author`, `maintainers`
- archived exact-version snapshot resolution for historical installs and lineage lookups
- install manifest core keys used by install, sync, list, switch, and rollback flows
- top-level install commands and their current safety expectations:
  - `uv run infinitas install exact`
  - `uv run infinitas install sync`
  - `scripts/list-installed.sh`

## Versioned file formats

Two file formats are compatibility-sensitive and must be treated as versioned contracts:

- `_meta.json`
- `.infinitas-skill-install-manifest.json`

Current rule set:

- `_meta.json` without `schema_version` is treated as schema version `1`
- `.infinitas-skill-install-manifest.json` without `schema_version` is treated as schema version `1`
- new writers should emit the latest supported schema version for each file format
- readers must continue to accept supported historical versions inside the declared compatibility window

## Surface classification

| Surface | Classification | Notes |
| --- | --- | --- |
| `_meta.json` core required fields | stable contract | scripts and catalogs depend on these fields today |
| `_meta.json` optional extension fields | soft contract | additive changes are preferred |
| install manifest `skills`, `history`, `locked_version`, `source_*`, `integrity`, `integrity_capability`, `integrity_reason`, `integrity_events`, `last_checked_at` | stable contract | install, sync, rollback, dependency planning, `report-installed-integrity.py`, and installed-integrity status surfaces read these keys |
| `config/install-integrity-policy.json` freshness controls such as `freshness.stale_after_hours`, `freshness.stale_policy`, and `freshness.never_verified_policy` | soft contract | repo-managed command behavior for target-local freshness guardrails; additive modes should prefer compatibility-safe defaults |
| target-local `.infinitas-skill-installed-integrity.json` snapshot/history artifact | soft contract | additive snapshot layer for current report state plus `archived_integrity_events`; missing file must be tolerated |
| archived snapshot exact-version resolution | stable contract | historical installs and lineage depend on this |
| `catalog/compatibility.json` structure | soft contract | generated view, useful to consumers, but not the only source of truth |
| internal helper implementation details in `scripts/*.py` | internal detail | refactor freely if behavior stays compatible |

## Deprecation policy

Behavior should not be removed without a compatibility window.

Minimum deprecation expectations:

- announce the field, path, or behavior being deprecated in docs
- keep old readers working for at least one additional release cycle
- provide a migration path when persisted state is involved
- add regression coverage before tightening validation

## Dual-read / single-write rule

Compatibility-sensitive persisted formats follow this rule:

- readers accept both the newest supported shape and older supported shapes
- writers emit exactly one canonical current shape
- migrations move old data forward explicitly instead of relying on silent ad-hoc rewrites

This rule applies first to `_meta.json` and `.infinitas-skill-install-manifest.json`.

## Migration guarantees

When a compatibility-sensitive file format evolves:

- a migration command should exist for persisted state
- current migration entrypoints are `scripts/migrate-skill-meta.py` and `scripts/migrate-install-manifest.py`
- `--check` or dry-run style output should show what would change
- unsupported future schema versions should fail clearly instead of being silently rewritten
- migrations should preserve historical information such as `history`, `locked_version`, and snapshot provenance

## Compatibility test matrix

At minimum, compatibility regression coverage should preserve these behaviors:

The standard repository verification path should run `scripts/test-compat-regression.py` so compatibility stays enforced as the toolchain evolves.

- legacy `_meta.json` without `schema_version` still validates
- legacy install manifest without `schema_version` still loads
- legacy install manifest without `integrity` still loads and defaults to `integrity.state = unknown`
- legacy install manifest without `integrity_capability`, `integrity_reason`, or `integrity_events` still loads and normalizes additively
- missing `.infinitas-skill-installed-integrity.json` sidecar still allows current report surfaces to load from inline manifest state
- `locked_version` still prevents unsafe upgrade plans
- archived exact-version snapshots still resolve for historical installs
- legacy bare skill names still resolve unless a strict mode explicitly disables them

## Installed-Integrity Additive Fields

The install manifest's installed-integrity surface now has two layers:

- nested `integrity` summary for current status counters and file drift details
- additive top-level `integrity_capability`, `integrity_reason`, `integrity_events`, and `last_checked_at` for compatibility-safe trust and audit metadata
- optional target-local `.infinitas-skill-installed-integrity.json` snapshot/history artifact for current report state plus `archived_integrity_events`

Compatibility rule:

- older manifests may omit `integrity_capability`, `integrity_reason`, `integrity_events`, and `last_checked_at`
- readers must normalize those omissions to `unknown`, `null`, `[]`, and `null`
- current writers should emit the canonical expanded shape
- `report-installed-integrity.py` may append new `integrity_events`, but it must not break manifests that predate those fields
- missing target-local `.infinitas-skill-installed-integrity.json` must not break report or list surfaces
- freshness guardrails remain config-and-behavior only; `freshness.stale_policy` and `freshness.never_verified_policy` must not imply new required install-manifest fields
- read-only report/update surfaces may add derived fields such as `mutation_readiness`, `mutation_policy`, `mutation_reason_code`, and `recovery_action`, but readers must tolerate them being absent on older payloads
- legacy manifests may still derive `freshness_state` and `checked_age_seconds` from `integrity.last_verified_at` while leaving top-level `last_checked_at = null` until an explicit refresh rewrites the canonical field
- wrappers should treat the derived readiness fields as authoritative for overwrite-policy decisions on older manifests instead of assuming `last_checked_at` will always be populated

Operational steady-state guidance, accepted maintenance notes, and the final verification matrix live in `docs/project-closeout.md`; they are workflow guidance, not a separate persisted file-format contract.

## Notes on runtime vs format compatibility

Treat `agent_compatible` as legacy migration metadata. The maintained runtime contract is now OpenClaw-native, so `agent_compatible` remains useful only for migration, historical declarations, and compatibility-era audit context.

The repository still distinguishes between these legacy compatibility concepts when historical data is present:

- **declared support**: what the author says a skill intends to support
- **verified support**: what recent platform-specific checks and evidence files have confirmed

Verified support now carries additive freshness metadata so the repository can distinguish between:

- recent evidence that is still considered fresh
- older evidence that is now stale because of age or because the tracked platform contract changed after the last verification
- missing evidence, which remains `unknown`

It is **not** the same thing as registry file-format compatibility. File-format compatibility is governed by versioned schemas, migration guarantees, and regression tests. It is also not the maintained runtime contract; OpenClaw runtime behavior now lives in `openclaw-runtime-contract.md`.
