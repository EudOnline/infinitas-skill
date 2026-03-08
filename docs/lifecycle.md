# Skill Lifecycle

## Stages

### `incubating`
Use for:
- brand-new skills
- agent-generated variants
- major rewrites
- skills awaiting review

Expected review state:
- `draft`
- `under-review`
- `approved`
- `rejected`

### `active`
Use for:
- reviewed, reusable skills
- skills safe enough to install into agent-local registries

Expected review state:
- usually `approved`

### `archived`
Use for:
- deprecated skills
- historical snapshots
- skills replaced by a better successor

## Promotion flow

1. Create or copy a skill into `skills/incubating/<name>`
2. Fill in `SKILL.md`, `_meta.json`, and `tests/smoke.md`
3. Run `scripts/check-skill.sh skills/incubating/<name>`
4. Mark `_meta.json.review_state = "approved"` after human review
5. Run `scripts/promote-skill.sh <name>`
6. Rebuild catalogs with `scripts/build-catalog.sh`

## Evolution rule of thumb

For MVP, prefer **explicit derivation** over hidden inheritance.

Use `_meta.json.derived_from` to track lineage, for example:

```json
{
  "derived_from": "repo-audit@0.1.0"
}
```

That keeps history auditable without adding a build-time merge system yet.
