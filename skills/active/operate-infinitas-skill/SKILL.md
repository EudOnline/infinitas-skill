---
name: operate-infinitas-skill
description: Use when OpenClaw, Codex, or Claude Code needs to operate inside the infinitas-skill repository to import prototypes, validate skills, publish immutable releases, pull stable installs, or export OpenClaw-compatible bundles.
---

# Operate infinitas-skill

## Overview

This skill teaches an agent how to work inside the `infinitas-skill` repository without confusing editable source, released artifacts, and runtime installs.

Core rule: never install from `skills/incubating/` or `skills/active/`. Validate and publish first, then pull from immutable release artifacts.

## Shared Model

Always distinguish these four states before choosing a command:

1. **Local prototype**: a working folder such as `~/.openclaw/workspace/skills/<skill>`
2. **Registry source**: `skills/incubating/` or `skills/active/`
3. **Immutable release artifacts**: `catalog/distributions/...` and `catalog/provenance/...`
4. **Runtime install target**: a local runtime directory such as `~/.openclaw/skills`

Do not mix these states together. A prototype is not a release. A reviewed source folder is not an install artifact. A runtime install should come from verified release data.

Read this machine-facing surface first:

- `README.md`
- `docs/ai/agent-operations.md`
- `docs/ai/discovery.md`
- `docs/ai/openclaw.md`
- `docs/ai/publish.md`
- `docs/ai/pull.md`
- `catalog/ai-index.json`

Use `--mode confirm` first when the request could mutate the repo, write into a runtime directory, or publish a release.

## Command Map

- `scripts/import-openclaw-skill.sh`: import a local OpenClaw prototype into the registry
- `scripts/check-skill.sh`: validate a skill folder before review or release
- `scripts/publish-skill.sh`: produce immutable release artifacts and refresh catalogs
- `scripts/pull-skill.sh`: install a released version into a runtime directory
- `scripts/export-openclaw-skill.sh`: render an already released skill into an OpenClaw or ClawHub-compatible export folder
- `scripts/resolve-skill.sh` and `scripts/install-by-name.sh`: discovery-first helpers that still resolve to immutable release artifacts

## Default Workflow

1. Identify whether the user is asking to import, validate, publish, install, upgrade, or export.
2. Read only the machine-facing docs first unless debugging requires deeper script inspection.
3. If the task starts from an OpenClaw local prototype, use `scripts/import-openclaw-skill.sh`.
4. If the task starts from a registry skill and the user wants a stable version for others, validate it and use `scripts/publish-skill.sh`.
5. If the task is about installing a stable version, use `scripts/pull-skill.sh` or `scripts/install-by-name.sh`, not direct copies from source folders.
6. If the task is about ClawHub packaging, publish first and then use `scripts/export-openclaw-skill.sh`.
7. Never auto-run `clawhub publish` unless the user explicitly asks for that public step.

## OpenClaw

Use this section when the caller is working from an OpenClaw prototype or wants an OpenClaw runtime install.

- Import prototypes from `~/.openclaw/workspace/skills/<skill>` with `scripts/import-openclaw-skill.sh ... --owner lvxiaoer --publisher lvxiaoer`
- Publish reviewed registry skills with `scripts/publish-skill.sh lvxiaoer/<skill>`
- Install released versions into `~/.openclaw/skills` with `scripts/pull-skill.sh lvxiaoer/<skill> ~/.openclaw/skills`
- Export public-ready or review-ready folders with `scripts/export-openclaw-skill.sh lvxiaoer/<skill> --out /tmp/openclaw-export`

Hard rules for OpenClaw:

- do not treat the local prototype folder as a published version
- do not install directly from `skills/incubating/` or `skills/active/`
- do not assume export success means `public_ready: true`

## Codex

Use this section when Codex is acting as the repository operator.

- Treat this repository as a private skill registry, not as `~/.agents/skills`
- Use the docs listed above as the contract surface before reading internal implementation scripts
- Prefer `scripts/publish-skill.sh`, `scripts/pull-skill.sh`, and `scripts/install-by-name.sh` over low-level manual file copies
- Prefer qualified names such as `lvxiaoer/operate-infinitas-skill` when a skill might be ambiguous
- Use `--mode confirm` before any action that could publish, install, or overwrite data

## Claude Code

Use this section when Claude Code is acting as the repository operator.

- Treat this repository as the registry source of truth, not as `~/.claude/skills` or `.claude/agents`
- Follow the same import, validate, publish, pull, and export workflow as Codex and OpenClaw operators
- Read the machine-facing docs first and only inspect internal scripts when debugging or when the docs leave a real gap
- Keep installs tied to immutable release artifacts instead of direct copies from editable source trees

## Hard Rules

- Do not install from `skills/incubating/` or `skills/active/`
- Do not equate “merged” with “published”
- Do not equate “tag exists” with “published”
- Do not skip manifest or attestation verification for installs
- Do not infer a default version from the working tree; use `catalog/ai-index.json`
- Do not auto-publish to ClawHub

## Bundled Resources

- `tests/smoke.md` contains a realistic trigger scenario for this skill
