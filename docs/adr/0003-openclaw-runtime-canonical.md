---
audience: contributors and maintainers
owner: repository maintainers
source_of_truth: openclaw runtime canonicalization decision
last_reviewed: 2026-04-07
status: maintained
---

# 0003 - OpenClaw runtime canonicalization

## Status

Accepted

## Context

The repository currently treats OpenClaw mainly as a compatibility/export target alongside other agent runtimes. That model no longer matches the latest OpenClaw design, which centers runtime behavior around workspace skill directories, sub-agents, plugin capabilities, and scheduled/background execution primitives.

At the same time, this repository already has a durable backend for drafts, sealed versions, releases, exposures, reviews, access grants, artifacts, and audit records. Replacing that backend is unnecessary for the current migration and would expand scope far beyond the runtime-design problem.

## Decision

Adopt OpenClaw as the canonical agent runtime for maintained runtime semantics while keeping the current registry and control-plane backend as the source of truth for release and access workflows.

This means:

- OpenClaw runtime concepts such as workspace skill resolution, sub-agents, plugin capabilities, and background task expectations become first-class maintained contracts.
- Registry lifecycle records remain authoritative for `skill -> draft -> sealed version -> release -> exposure -> review case -> grant/credential -> discovery/install`.
- Compatibility-first abstractions such as equal-weight triple-runtime support, renderer-led OpenClaw exports, and `agent_compatible` as a primary runtime truth source are now migration-era concepts.
- Legacy compatibility import/export helpers may remain temporarily, but they are migration tooling rather than the maintained runtime owner.

## Consequences

- Maintained docs and maintained CLI surfaces must describe OpenClaw-first runtime semantics instead of platform-neutral compatibility language.
- Release, artifact, review, and access truth continue to live in the existing backend and are not delegated to the OpenClaw runtime.
- Existing compatibility evidence can remain as historical context, but it is no longer the center of maintained runtime design.
