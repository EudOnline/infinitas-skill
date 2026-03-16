---
name: release-infinitas-skill
description: Use when Codex, Claude, or Claude Code needs to validate a registry skill, move it through review and promotion, and produce immutable release artifacts inside infinitas-skill.
---

# Release infinitas-skill

## Overview

This skill handles the release side of the repository lifecycle: validation, review, promotion, immutable release output, and compatibility evidence refresh.

Use it when the job is to make a skill safely releasable for other agents, not when the job is simply to find or install an already released version.

## Read First

Start with these machine-facing docs before opening implementation internals:

- `README.md`
- `docs/ai/agent-operations.md`
- `docs/ai/publish.md`
- `docs/release-strategy.md`
- `catalog/ai-index.json`

Default to confirm-first reasoning when a command could change review state, promote a skill, create a tag, or write release artifacts.

## Workflow

1. Resolve the target skill and confirm whether it is still `incubating` or already `active`.
2. Run `scripts/check-skill.sh <skill>` before any review or release action.
3. If review has not been requested yet, use `scripts/request-review.sh <skill> --note ...`.
4. When approval is intended, record it with `scripts/approve-skill.sh <skill> --reviewer ... --note ...`.
5. Promote approved incubating skills with `scripts/promote-skill.sh <skill>`.
6. Produce immutable release artifacts with `scripts/release-skill.sh <skill> --create-tag --write-provenance`.
7. Refresh generated indexes with `scripts/build-catalog.sh`.
8. If compatibility evidence should stay current, run `python3 scripts/record-verified-support.py <skill> --platform ... --build-catalog`.

## Command Map

- `scripts/check-skill.sh`: validate metadata, frontmatter, and core repository invariants
- `scripts/request-review.sh`: open the review process for an incubating skill
- `scripts/approve-skill.sh`: record approval or rejection decisions
- `scripts/promote-skill.sh`: move an approved skill from `skills/incubating/` to `skills/active/`
- `scripts/release-skill.sh`: create a signed local release tag and immutable distribution artifacts
- `scripts/build-catalog.sh`: regenerate catalog, AI index, discovery index, and export views
- `python3 scripts/record-verified-support.py`: write compatibility evidence and refresh catalog views

## Hard Rules

- Do not treat a successful review as a release
- Do not treat an `active` folder as an installable artifact
- Do not skip `scripts/check-skill.sh` before review or release
- Do not use `scripts/publish-skill.sh` when branch-local work must avoid remote pushes
- Do not claim release success until manifest, bundle, provenance, and catalog outputs all exist

## Bundled Resources

- `tests/smoke.md` contains a realistic release request for this skill
