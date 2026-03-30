---
audience: contributors and maintainers
owner: repository maintainers
source_of_truth: maintainability reset decision
last_reviewed: 2026-03-30
status: maintained
---

# 0001 — Maintainability reset

## Status

Accepted

## Context

The repository has accumulated a sprawling collection of documentation, tooling notes, and operational artifacts without a clear information architecture. Maintaining the root README as a knowledge index makes it harder for contributors to find the right surface and harder for the team to keep each topic current.

The codebase is also moving toward a real package boundary under `src/infinitas_skill/`, but the repository still exposes too much behavior through ad hoc top-level scripts and docs. Without an explicit reset, the tree will keep getting harder to reason about.

## Decision

Adopt a breaking maintainability reset with these rules:

- New shared Python logic should move toward `src/infinitas_skill/`.
- `scripts/` is a legacy surface and should receive new top-level entrypoints only with explicit architecture approval.
- Documentation is organized by role and task, with maintained landing pages under `docs/guide/`, `docs/reference/`, `docs/ops/`, `docs/archive/`, and `docs/adr/`.
- The root `README.md` becomes a short entry page instead of an exhaustive handbook.
- Temporary compatibility aliases are allowed only to reduce migration risk and currently expire on `2026-06-30` unless a later ADR extends them.

## Consequences

- Contributors must choose the target package and doc homes intentionally instead of adding new top-level sprawl.
- Readers get a small set of canonical entry pages even while legacy files are still being relocated.
- The reset explicitly prefers coherence over indefinite backward compatibility for command names and documentation layout.
