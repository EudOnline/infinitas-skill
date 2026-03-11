# History and Snapshots

Fourth-version registry tooling adds explicit support for preserving active skill history without forcing a full package registry yet.

## Why snapshots exist

When an active skill is replaced, you often want three things at once:

1. keep the stable skill name for consumers
2. preserve the previous implementation for audit and rollback
3. let derived skills diff against the exact historical ancestor they were built from

Timestamped archived snapshots solve that without introducing a separate object store.

## Snapshot format

`scripts/snapshot-active-skill.sh <skill-name>` copies:

- `skills/active/<name>`

into:

- `skills/archived/<name>--v<version>--<timestamp>[--label]`

The copied `_meta.json` is annotated with:

- `status = archived`
- `snapshot_of = <name>@<version>`
- `snapshot_created_at = <UTC timestamp>`
- `snapshot_label = <label>` when provided

## Promotion overwrite behavior

`scripts/promote-skill.sh <name> --force` now snapshots the existing active skill before replacing it.

Default snapshot label:

- `promote-overwrite`

You can override it with:

```bash
scripts/promote-skill.sh repo-audit --force --snapshot-label tuned-scoring
```

## Exact lineage resolution

If a derived skill declares:

```json
{
  "derived_from": "repo-audit@0.2.0"
}
```

`lineage-diff.sh` will try to resolve that exact ancestor version first. It prefers an archived snapshot when available, then falls back to a same-version active/incubating copy, and only then falls back to the plain skill name.

## Compatibility guarantees

The following behaviors are treated as compatibility guarantees for persisted installs:

- `locked_version` remains authoritative for preventing silent unsafe upgrades
- archived exact-version snapshot resolution remains available for historical installs
- install-history based rollback must preserve enough source metadata to re-resolve the previous state

These guarantees are part of `docs/compatibility-contract.md`, not just implementation details.

## Version-locked installs

`install-skill.sh --version <active-version>` records a `locked_version` in the install manifest.

`sync-skill.sh` refuses to advance a locked install if the active skill has moved past that version.

That gives you a light-weight way to say: "keep this local agent on the current stable version until I explicitly re-install or change the lock."

## Historical installs

`install-skill.sh --version <x.y.z>` now resolves the requested version from archived snapshots when the active copy has already moved on.

That means local agents can intentionally stay on or return to an older stable version without manual path-copy work.

## Switching and rollback

Two helpers now exist for installed copies:

```bash
# switch to a specific historical version
scripts/switch-installed-skill.sh repo-audit ~/.openclaw/skills --to-version 0.2.0 --force

# roll back using manifest history
scripts/rollback-installed-skill.sh repo-audit ~/.openclaw/skills --force
```

Manifest history stores previous install states so rollback can choose the last known version source automatically.

If older local installs are still missing manifest schema metadata, use `scripts/migrate-install-manifest.py` before tightening validation in automation or CI.

With V10 Phase 3, those stored states can now re-resolve immutable release artifacts through verified distribution manifests instead of depending only on a still-present working-tree copy under `skills/active/` or `skills/archived/`.

## Regression coverage

Compatibility-sensitive snapshot and rollback behavior should stay covered by `scripts/test-compat-regression.py` together with install-flow tests such as `scripts/test-distribution-install.py`.
