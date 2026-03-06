# Repository Conventions

## Lifecycle

- `skills/incubating/` → early or experimental skills
- `skills/active/` → stable skills worth reusing
- `skills/archived/` → retired or historical skills

## Skill shape

Each skill should usually follow this layout:

```text
skill-name/
├─ SKILL.md
├─ _meta.json            optional but useful
├─ scripts/              executable helpers
├─ references/           docs to load as needed
└─ assets/               templates or output resources
```

## Naming

- Use lowercase letters, digits, and hyphens only
- Keep names short and specific
- One skill = one folder
- Match the folder name to the `name:` field in `SKILL.md`

## Template selection

- `basic-skill` → lightweight workflow skill
- `scripted-skill` → repeated deterministic work via scripts
- `reference-heavy-skill` → domain-heavy skill with docs in `references/`

## Promotion bar

Before moving a skill to `skills/active/`, check that:

- trigger description is clear
- `SKILL.md` is concise and actionable
- heavy detail is moved into `references/`
- scripts are named clearly and do one job well
- obvious secrets and private dumps are removed
