# Repository Conventions

## Lifecycle

- `skills/incubating/` → early or experimental skills
- `skills/active/` → stable skills worth reusing
- `skills/archived/` → retired or historical skills

See also: `docs/lifecycle.md`

## Skill shape

Each skill should usually follow this layout:

```text
skill-name/
├─ SKILL.md
├─ _meta.json            required for registry indexing
├─ CHANGELOG.md          optional but recommended after first release
├─ scripts/              executable helpers
├─ references/           docs to load as needed
├─ assets/               templates or output resources
└─ tests/
   └─ smoke.md           minimal realistic validation note/case
```

## Naming

- Use lowercase letters, digits, and hyphens only
- Keep names short and specific
- One skill = one folder
- Match the folder name to the `name:` field in `SKILL.md`
- Match `_meta.json.name` to both the folder name and `SKILL.md` name

## Template selection

- `basic-skill` → lightweight workflow skill
- `scripted-skill` → repeated deterministic work via scripts
- `reference-heavy-skill` → domain-heavy skill with docs in `references/`

## Metadata expectations

Every installable skill should declare at least:

- `name`
- `version`
- `status`
- `summary`
- `owner`
- `review_state`
- `risk_level`
- `distribution.installable`

See `docs/metadata-schema.md` for the full shape.

## Promotion bar

Before moving a skill to `skills/active/`, check that:

- trigger description is clear
- `SKILL.md` is concise and actionable
- `_meta.json` is complete and accurate
- heavy detail is moved into `references/`
- scripts are named clearly and do one job well
- `tests/smoke.md` exists
- obvious secrets and private dumps are removed
