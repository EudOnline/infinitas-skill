---
audience: contributors and maintainers
owner: repository maintainers
source_of_truth: maintained surface cutover contract
last_reviewed: 2026-03-30
status: maintained
---

# 0002 - Maintained surface cutover

## Status

Accepted

## Context

The maintainability reset now has a maintained CLI, a hosted runtime, and a shrinking set of script-era bridges, but the repository still lacks a durable contract for what counts as "done" for the cutover. Without that contract, shared logic can drift back into `scripts/`, `server/app.py` can keep accumulating runtime behavior, and contributors have no explicit rule for when a shim must be deleted instead of tolerated.

## Decision

Treat the reset as complete only when these ownership boundaries hold:

- Maintained package-owned logic lives under `src/infinitas_skill/...`, especially install, policy, release, and maintained server command services.
- Hosted runtime-owned logic lives under `server/modules/...` and `server/ui/...`; `server/app.py` remains app assembly, middleware/static setup, and route registration glue.
- `scripts/*.py` may remain only as thin compatibility adapters that call maintained package or runtime code. They are not an approved home for new maintained shared logic.
- Maintained docs must identify canonical `infinitas ...` entrypoints and mark bridge surfaces as `shim` until they are deleted.
- `2026-06-30` is the default checkpoint for alias removal. Any shim that survives past that date requires a new or updated ADR.

## Consequences

- The repository now has an explicit closeout rule for package-owned, runtime-owned, and compatibility-only surfaces.
- Maintainers can remove bridges incrementally while preserving a shared definition of which surface is canonical.
- Future slices should measure progress by shrinking the compatibility-only surface, not by adding more wrapper-aware documentation.
