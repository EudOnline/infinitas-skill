---
audience: contributors, integrators, reviewers
owner: repository maintainers
source_of_truth: openclaw runtime contract reference
last_reviewed: 2026-04-07
status: maintained
---

# OpenClaw Runtime Contract

This document defines the maintained OpenClaw runtime contract for `infinitas-skill`.

OpenClaw is now the canonical agent runtime. The repository still owns the registry, release, artifact, review, access, and audit backend, but maintained runtime semantics are defined in OpenClaw-native terms.

## Runtime scope

The maintained runtime contract centers on:

- OpenClaw workspace and user skill directories
- skill entrypoint and runtime requirement semantics
- sub-agent support and task delegation expectations
- plugin capability expectations
- background task and cron-oriented runtime assumptions

## Published object contract

OpenClaw-facing distribution now treats these object kinds as first-class:

- `skill`
- `agent_preset`
- `agent_code`

`agent_preset` is the shared OpenClaw configuration object. It captures runtime-facing configuration such as prompt, model, tool, dependency, and memory defaults without implying that the preset itself owns the executable runtime implementation.

`agent_code` is the lightweight runnable agent-code object. It may originate from an immutable external source, but hosted release output must still be a platform-owned frozen bundle rather than a live upstream reference.

Install-time preset selection must use the exact variant field names:

- `memory_mode`
- `content_mode`

## Backend source-of-truth boundary

The following remain authoritative in the repository backend:

- draft and sealed-version state
- immutable release and artifact state
- exposure, review case, and access-grant state
- install planning and audit history

OpenClaw runtime state does not replace those records. It defines how maintained runtime-facing metadata, discovery, and install behavior should be interpreted.

Hosted content ownership also remains a backend concern. The backend may store complete uploaded content bundles and freeze immutable external imports so downstream installs always resolve through hosted artifacts.

## Legacy migration boundary

The repository still contains compatibility-era structures such as:

- `agent_compatible`
- renderer-generated platform overlays
- OpenClaw import/export bridge helpers
- historical compatibility evidence

Those are migration inputs or historical context. They are not the maintained source of runtime truth.
