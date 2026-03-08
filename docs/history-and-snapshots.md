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

## Version-locked installs

`install-skill.sh --version <active-version>` records a `locked_version` in the install manifest.

`sync-skill.sh` refuses to advance a locked install if the active skill has moved past that version.

That gives you a light-weight way to say: "keep this local agent on the current stable version until I explicitly re-install or change the lock."
