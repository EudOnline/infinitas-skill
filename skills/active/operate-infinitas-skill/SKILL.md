---
name: operate-infinitas-skill
description: Use when OpenClaw, Codex, or Claude Code needs to operate the private-first infinitas-skill registry through drafts, releases, exposures, review cases, and audience-scoped discovery.
---

# Operate infinitas-skill

## Overview

This skill teaches an agent how to work inside the `infinitas-skill` repository after the private-first cutover.

Core rule: operate the hosted registry lifecycle, not the removed submission/promotion shell flow.

## Shared Model

Always distinguish these states before choosing a command:

1. **Draft authoring**: mutable `skill_drafts`
2. **Immutable release state**: `skill_versions`, `releases`, `artifacts`
3. **Audience policy**: `exposures`, `review_cases`, `access_grants`, `credentials`
4. **Discovery/install**: `/api/v1/catalog/*`, `/api/v1/install/*`, and `/registry/*`

Read this machine-facing surface first:

- `README.md`
- `docs/ai/discovery.md`
- `docs/ai/publish.md`
- `docs/ai/pull.md`
- `docs/ai/server-api.md`
- `docs/private-first-cutover.md`

Use `--mode confirm` first when the request could mutate the repo, write into a runtime directory, or publish a release.

## Command Map

- `scripts/registryctl.py`: the primary operator CLI for skills, drafts, releases, exposures, grants, tokens, and review cases
- `/api/v1/skills`, `/api/v1/drafts/*`, `/api/v1/releases/*`: authoring and release lifecycle
- `/api/v1/exposures/*`, `/api/v1/review-cases/*`: exposure and review lifecycle
- `/api/v1/catalog/*`, `/api/v1/install/*`, `/registry/*`: discovery and install surfaces

## Default Workflow

1. Identify whether the user is asking to author, seal, release, expose, review, grant, discover, or download.
2. Read only the machine-facing docs first unless debugging requires deeper script inspection.
3. Create or patch drafts before talking about releases.
4. Seal drafts into versions, then create releases.
5. Expose releases to the intended audience and review public exposures before calling them installable.
6. Use registry discovery or install endpoints when the task is about audience-scoped download.

## OpenClaw

Use this section when the caller is working from an OpenClaw prototype or wants an OpenClaw runtime install.

- Author content into the hosted private-first registry instead of relying on source-folder promotion
- Use `scripts/registryctl.py` or the hosted UI to create drafts, releases, and exposures
- Treat `/api/v1/install/*` and `/registry/*` as the hosted download contract

Hard rules for OpenClaw:

- do not treat a draft as a release
- do not treat a release as discoverable before exposure and review policy allow it
- do not assume a grant token can read unrelated public or private releases

## Codex

Use this section when Codex is acting as the repository operator.

- Treat this repository as a hosted private-first registry, not as a source-folder promotion workflow
- Use `scripts/registryctl.py` and the hosted API surface before reaching for low-level DB edits
- Prefer qualified names when resolving install targets

## Claude Code

Use this section when Claude Code is acting as the repository operator.

- Treat this repository as the registry source of truth, not as `~/.claude/skills` or `.claude/agents`
- Follow the same draft -> release -> exposure -> review -> discovery workflow as other operators
- Read the machine-facing docs first and only inspect internals when the docs leave a real gap

## Hard Rules

- Do not reintroduce the removed submission/review/job product flow
- Do not treat release creation as exposure or exposure as approval
- Do not use removed publish/promotion shell scripts

## Bundled Resources

- `tests/smoke.md` contains a realistic trigger scenario for this skill
