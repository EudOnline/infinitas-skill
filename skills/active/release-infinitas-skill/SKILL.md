---
name: release-infinitas-skill
description: Use when Codex, Claude, or Claude Code needs to move a private-first skill through draft sealing, release materialization, exposure policy, and review approval.
---

# Release infinitas-skill

## Overview

This skill handles the release side of the private-first lifecycle: draft sealing, immutable release materialization, audience exposure, and public review approval.

Use it when the job is to make a skill safely releasable for other agents, not when the job is simply to search or download an already exposed release.

## Read First

Start with these machine-facing docs before opening implementation internals:

- `README.md`
- `docs/reference/cli-reference.md`
- `docs/ops/release-checklist.md`
- `docs/guide/private-first-cutover.md`

Default to confirm-first reasoning when a command could seal a draft, create a release, open a review case, or change exposure state.

## Workflow

1. Resolve the target skill and current draft/version/release state.
2. Create or patch a draft until content and metadata are ready.
3. Seal the draft into an immutable version.
4. Create a release for that version.
5. Let the worker materialize the release artifacts.
6. Create the intended exposure.
7. If the exposure is public, approve the review case before announcing it as public.

## Command Map

- `uv run infinitas registry skills create`
- `uv run infinitas registry drafts create`
- `uv run infinitas registry drafts update`
- `uv run infinitas registry drafts seal`
- `uv run infinitas registry releases create`
- `uv run infinitas registry exposures create`
- `uv run infinitas registry reviews decide`

## Hard Rules

- Do not treat a sealed version as a release until materialization completes
- Do not treat a release as public until the blocking review case is approved
- Do not use removed review/promotion/publish shell scripts
- Do not claim installability until manifest, bundle, provenance, and signature artifacts exist

## Bundled Resources

- `tests/smoke.md` contains a realistic release request for this skill
