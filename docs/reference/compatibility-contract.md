---
audience: contributors, integrators, reviewers
owner: repository maintainers
source_of_truth: current runtime compatibility contract
last_reviewed: 2026-07-14
status: maintained
---

# Runtime Compatibility Contract

Compatibility in this repository means current platform/runtime support: whether a skill can run correctly in OpenClaw, Codex, Claude Code, or another declared Agent environment. It does not mean accepting superseded project files, routes, commands, or database shapes.

## Canonical runtime

OpenClaw is the canonical runtime contract. See [openclaw-runtime-contract.md](openclaw-runtime-contract.md) for workspace targets, precedence, plugin capability, background task, subagent, and readiness requirements.

Other platforms remain valid declared or verified targets, but they do not weaken OpenClaw release requirements.

## Declared and verified support

- `agent_compatible` is current declared support supplied by the skill author.
- verified support is current evidence produced by platform checks and release workflows.
- freshness metadata distinguishes `fresh`, `stale`, and `unknown` evidence.

Release decisions use verified support and policy. A declaration by itself is not evidence that the current release works.

## Current format rule

Each persisted format has one accepted schema version. Readers reject missing or unsupported versions and do not rewrite input into another shape.

- `_meta.json`: `schemas/skill-meta.schema.json`
- install manifest: `schemas/install-manifest.schema.json`
- canonical skill source: `skill.json` validated by `infinitas_skill.skills.canonical`
- distribution manifest: `schemas/distribution-manifest.schema.json`

This rule is separate from runtime/platform compatibility.

## Installed integrity

Current install manifests may record:

- `integrity`
- `integrity_capability`
- `integrity_reason`
- `integrity_events`
- `last_checked_at`
- target-local `.infinitas-skill-installed-integrity.json`

Use `uv run infinitas install report`, `uv run infinitas install verify`, and `uv run infinitas install repair` to manage current installed trust state.

## Verification

```bash
uv run infinitas compatibility check-platform-contracts --json
uv run infinitas release check-state <skill> --mode local-preflight --json
uv run infinitas install verify <installed-name> <target-dir> --json
```

Automated coverage lives under `tests/unit/compatibility`, current discovery/release integration tests, and platform-specific evidence tests under `tests/`.
