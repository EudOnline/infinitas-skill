---
name: reference-heavy-skill
description: Replace this with a skill that relies on larger reference documents loaded only when needed.
---

# Reference-Heavy Skill Template

## Purpose

Describe the domain or system this skill covers.

## When to use

Use this when the task needs domain-specific reference material that should live in `references/` instead of bloating `SKILL.md`.

## Workflow

1. Identify which reference file is relevant.
2. Read only the needed reference material.
3. Execute the task with minimal extra context.
4. Return the result and mention any assumptions.

## Bundled resources

- `references/` for domain docs, schemas, or policies
- `scripts/` for optional helpers
- `assets/` for reusable templates or examples
