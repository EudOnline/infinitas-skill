---
name: consume-infinitas-skill
description: Use when OpenClaw, Codex, Claude, or Claude Code needs to search, inspect, install, pull, or upgrade stable infinitas-skill releases.
---

# Consume infinitas-skill

## Overview

This skill focuses on the discovery and installation side of the repository. It helps an agent choose the right released skill, inspect trust state, and materialize immutable installs into runtime directories.

Use it when the task begins from a user goal or an already released skill name. Do not use it to publish or promote source changes.

## Read First

Start with these stable surfaces:

- `README.md`
- `docs/ai/discovery.md`
- `docs/ai/search-and-inspect.md`
- `docs/ai/pull.md`
- `catalog/discovery-index.json`
- `catalog/ai-index.json`

## Workflow

1. Search with `scripts/search-skills.sh` when the task is broad or exploratory.
2. Rank candidates with `scripts/recommend-skill.sh` when the task is phrased as an intent instead of a precise name.
3. Inspect the winning candidate with `scripts/inspect-skill.sh` before installation.
4. Use `scripts/install-by-name.sh` or `scripts/pull-skill.sh` for immutable installation.
5. When the user already has an installed version, compare and update with `scripts/check-skill-update.sh` and `scripts/upgrade-skill.sh`.
6. Prefer `--mode confirm` before any install or upgrade that would mutate a runtime directory.

## Command Map

- `scripts/search-skills.sh`: list possible skill matches from the generated discovery index
- `scripts/recommend-skill.sh`: rank the best fit for a task
- `scripts/inspect-skill.sh`: inspect trust, compatibility, provenance, and decision metadata
- `scripts/install-by-name.sh`: resolve and install by discovery-first name lookup
- `scripts/pull-skill.sh`: install a known released skill from immutable artifacts
- `scripts/check-skill-update.sh`: inspect whether a newer compatible release exists
- `scripts/upgrade-skill.sh`: perform an immutable upgrade using the recorded source registry

## Hard Rules

- Do not install directly from `skills/incubating/` or `skills/active/`
- Do not skip inspection when trust state, provenance, or compatibility matters
- Do not infer versions from the working tree; use generated indexes
- Do not mutate runtime directories in `confirm` mode
- Do not use this skill to publish a release from source

## Bundled Resources

- `tests/smoke.md` contains a realistic discovery and install request
