---
audience: skill authors, registry maintainers, tooling developers
owner: repository maintainers
source_of_truth: schemas/skill-meta.schema.json
last_reviewed: 2026-07-14
status: maintained
---

# `_meta.json` Schema

Each registry skill directory contains one `_meta.json` document validated by `schemas/skill-meta.schema.json`. Only schema version `1` is accepted; the field is required.

## Required fields

| Field | Type | Contract |
|---|---|---|
| `schema_version` | integer | Exactly `1` |
| `name` | string | Lowercase slug |
| `version` | string | Semantic version |
| `status` | string | `incubating`, `active`, or `archived` |
| `summary` | string | Non-empty summary |
| `owner` | string | Primary accountable actor |
| `review_state` | string | `draft`, `under-review`, `approved`, or `rejected` |
| `risk_level` | string | `low`, `medium`, or `high` |
| `distribution` | object | `installable` boolean and `channel` string |

Unknown top-level fields are rejected. Add a field to the schema and all current producers/consumers together.

## Identity

Published skills use a qualified identity:

```json
{
  "schema_version": 1,
  "name": "operate-infinitas-skill",
  "publisher": "lvxiaoer",
  "qualified_name": "lvxiaoer/operate-infinitas-skill",
  "owner": "lvxiaoer",
  "owners": ["lvxiaoer"],
  "author": "lvxiaoer",
  "maintainers": ["lvxiaoer"]
}
```

`qualified_name` must equal `<publisher>/<name>`. Namespace ownership, signer authority, releaser authority, and publisher transfers are governed by `policy/namespace-policy.json`.

## Discovery metadata

These optional fields improve Agent selection and explanation:

- `tags`
- `maturity`
- `quality_score` from `0` to `100`
- `capabilities`
- `use_when`
- `avoid_when`
- `runtime_assumptions`
- `agent_compatible`

`agent_compatible` records current runtime/platform support. Release gates recompute verified support from current evidence; metadata alone is not proof of freshness.

## Runtime requirements

```json
{
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
  }
}
```

Paths are relative to the skill directory and must exist when required by policy.

## Dependencies and conflicts

Dependency entries use one object shape:

```json
{
  "depends_on": [
    {
      "name": "publisher/other-skill",
      "version": ">=1.2.0,<2.0.0",
      "registry": "self",
      "allow_incubating": false
    }
  ],
  "conflicts_with": []
}
```

String shorthand is not accepted. `name` is required; the other constraint fields are optional.

## Distribution

```json
{
  "distribution": {
    "installable": true,
    "channel": "git"
  }
}
```

Release and install tooling use this declaration together with generated distribution manifests, bundle hashes, and attestations. It does not bypass release verification.

## Snapshot and lineage fields

- `derived_from` and `replaces` describe lineage.
- `snapshot_of`, `snapshot_created_at`, and `snapshot_label` describe a current snapshot.

These fields are evidence and discovery metadata; they do not create an alternate source layout.

## Validation

Run the repository policy and release checks through the CLI:

```bash
uv run infinitas policy check-promotion skills/active/<skill> --as-active --json
uv run infinitas release check-state <skill> --mode local-preflight --json
```

The strict-schema regression lives in `tests/unit/skills/test_strict_skill_schema.py`.
