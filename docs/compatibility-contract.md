# Compatibility Contract

This document defines which parts of `infinitas-skill` are treated as compatibility promises and which parts are still implementation details that may evolve more freely.

## Stable surfaces

The following are currently treated as stable contracts unless a future deprecation notice says otherwise:

- `_meta.json` core identity and lifecycle fields: `name`, `version`, `status`, `summary`, `owner`, `review_state`, `risk_level`, `distribution`
- `_meta.json` compatibility-sensitive identity fields when present: `publisher`, `qualified_name`, `owners`, `author`, `maintainers`
- archived exact-version snapshot resolution for historical installs and lineage lookups
- install manifest core keys used by install, sync, list, switch, and rollback flows
- top-level install commands and their current safety expectations:
  - `scripts/install-skill.sh`
  - `scripts/sync-skill.sh`
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
| install manifest `skills`, `history`, `locked_version`, `source_*`, `integrity` | stable contract | install, sync, rollback, dependency planning, and installed-integrity status surfaces read these keys |
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
- `locked_version` still prevents unsafe upgrade plans
- archived exact-version snapshots still resolve for historical installs
- legacy bare skill names still resolve unless a strict mode explicitly disables them

## Notes on runtime vs format compatibility

`agent_compatible` is a runtime compatibility declaration: it says which agent runtimes a skill claims to support. That declaration is now treated as **declared support**, not the final compatibility verdict.

As the multi-platform pipeline evolves, the repository distinguishes between:

- **declared support**: what the author says a skill intends to support
- **verified support**: what recent platform-specific checks and evidence files have confirmed

It is **not** the same thing as registry file-format compatibility. File-format compatibility is governed by versioned schemas, migration guarantees, and regression tests.
