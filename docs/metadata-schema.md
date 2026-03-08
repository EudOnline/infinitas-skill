# `_meta.json` Schema (MVP)

Every registry-managed skill should include `_meta.json`.

## Required fields

```json
{
  "name": "repo-audit",
  "version": "0.1.0",
  "status": "incubating",
  "summary": "Audit a repository for structure, code health, and obvious risks.",
  "owner": "lvxiaoer",
  "review_state": "draft",
  "risk_level": "medium",
  "distribution": {
    "installable": true,
    "channel": "git"
  }
}
```

## Recommended full shape

```json
{
  "name": "repo-audit",
  "version": "0.1.0",
  "status": "incubating",
  "summary": "Audit a repository for structure, code health, and obvious risks.",
  "owner": "lvxiaoer",
  "maintainers": ["lvxiaoer"],
  "tags": ["github", "audit", "code-review"],
  "agent_compatible": ["openclaw", "claude-code", "codex"],
  "depends_on": [
    {
      "name": "registry-core",
      "version": ">=1.2.0 <2.0.0",
      "registry": "self"
    },
    "snapshot-tools@0.4.0"
  ],
  "conflicts_with": [
    {
      "name": "legacy-registry-core",
      "version": "<1.2.0"
    }
  ],
  "derived_from": null,
  "replaces": null,
  "visibility": "private",
  "review_state": "draft",
  "risk_level": "medium",
  "requires": {
    "tools": ["read", "exec"],
    "bins": ["git"],
    "env": []
  },
  "entrypoints": {
    "skill_md": "SKILL.md"
  },
  "tests": {
    "smoke": "tests/smoke.md"
  },
  "distribution": {
    "installable": true,
    "channel": "git"
  }
}
```

## Field notes

- `name`: folder name and `SKILL.md` frontmatter name should match this
- `version`: semver string like `0.1.0`
- `status`: `incubating | active | archived`
- `review_state`: `draft | under-review | approved | rejected`
- `risk_level`: `low | medium | high`
- `derived_from`: lineage string such as `repo-audit@0.1.0`
- Use the `name@version` form so lineage tools can diff against the intended ancestor
- `tests.smoke`: path to the minimum realistic validation case
- `distribution.installable`: whether install/sync scripts should expose the skill
- `depends_on`: install-time dependency list; use an object for machine-checked ranges and source hints, or keep the legacy `skill` / `skill@version` shorthand
- `conflicts_with`: install-time conflict list using the same object-or-shorthand format
- dependency objects support `name`, `version`, optional `registry`, and optional `allow_incubating`
- version constraints support `*`, exact versions, comparator chains like `>=1.2.0 <2.0.0`, plus `^` and `~` shorthands
- archived dependencies are only selected for exact version requests; incubating dependencies require `allow_incubating: true`

## MVP constraints

- Keep `_meta.json` machine-friendly and flat enough to parse from shell/python helpers
- Do not store secrets here
- Prefer explicit lineage over implicit inheritance

## Machine-readable schema

The canonical JSON Schema file for CI and editor integration lives at:

- `schemas/skill-meta.schema.json`

The current validation script is intentionally dependency-free, so it performs schema-equivalent checks in Python rather than requiring an external `jsonschema` package.

## Install manifests

Installed copies are tracked outside `_meta.json` in target directories via:

- `.infinitas-skill-install-manifest.json`

That manifest records which active skill version was installed or synced into a local runtime directory.

## Snapshot metadata

Archived snapshots may add these optional fields:

- `snapshot_of`: original skill and version, e.g. `repo-audit@0.2.0`
- `snapshot_created_at`: UTC timestamp used when the snapshot was created
- `snapshot_label`: optional human label such as `pre-refactor`

Archived snapshot folder names may differ from `_meta.json.name` because the directory encodes version and timestamp for uniqueness.

## Install manifest history

Target directories now maintain:

- current installed skill state under `skills.<name>`
- prior states under `history.<name>[]`

That history is used by rollback tooling and is separate from the registry catalog itself.

Root install/sync entries may also persist `resolution_plan`, which records the deterministic dependency plan that was applied for that action.
