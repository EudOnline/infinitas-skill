# infinitas-skill

Private skill factory for Claude Code, Codex, and OpenClaw.

This repository is meant to hold private skills, templates, helper scripts, and review guidance for skills that should not live in a public repository.

## Recommended workflow

1. Scaffold a new skill from a template
2. Build it under `skills/incubating/`
3. Validate it with `scripts/check-skill.sh`
4. Promote stable skills into `skills/active/`
5. Move retired skills into `skills/archived/`

## Repository layout

```text
skills/
├─ incubating/            work in progress
├─ active/                ready-to-use skills
└─ archived/              deprecated or historical skills

scripts/
├─ new-skill.sh           scaffold a new skill folder from a template
└─ check-skill.sh         quick validation + secret scan

templates/
├─ basic-skill/           minimal starting point
├─ scripted-skill/        for skills that rely on helper scripts
└─ reference-heavy-skill/ for skills with larger reference docs

docs/
├─ conventions.md         naming, layout, lifecycle rules
└─ release-checklist.md   pre-publish / pre-promote review list
```

## Quick start

```bash
# Create a new incubating skill from the basic template
scripts/new-skill.sh my-skill basic

# Create a scripted skill directly in active/
scripts/new-skill.sh repo-audit scripted skills/active

# Validate a skill folder
scripts/check-skill.sh skills/incubating/my-skill
```

## Safety rules

- Keep the repository private.
- Do not commit API keys, tokens, cookies, SSH keys, auth exports, or raw credential files.
- Review generated content before every push.
- Treat private repos as private collaboration space, not as a secret manager.
