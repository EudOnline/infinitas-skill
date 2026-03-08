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
- `tests.smoke`: path to the minimum realistic validation case
- `distribution.installable`: whether install/sync scripts should expose the skill

## MVP constraints

- Keep `_meta.json` machine-friendly and flat enough to parse from shell/python helpers
- Do not store secrets here
- Prefer explicit lineage over implicit inheritance

## Machine-readable schema

The canonical JSON Schema file for CI and editor integration lives at:

- `schemas/skill-meta.schema.json`

The current validation script is intentionally dependency-free, so it performs schema-equivalent checks in Python rather than requiring an external `jsonschema` package.
