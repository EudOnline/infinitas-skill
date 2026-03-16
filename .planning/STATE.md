# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-16)

**Core value:** Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.
**Current focus:** v13 registry operations planning, starting with refresh cadence and freshness policy.

## Current Position

Phase: v13 planning
Plan: `docs/plans/2026-03-16-registry-refresh-cadence-and-freshness.md`
Status: v13 selected on `codex/post-v12-roadmap-planning`; first implementation plan is being prepared
Last activity: 2026-03-16 — Merged signer readiness closeout to `main` and began v13 registry-operations planning

Progress: [#---------] 10%

## Performance Metrics

**Velocity:**
- Total plans completed: 49
- Average duration: n/a
- Total execution time: n/a

**By Phase:**
- v9: 14 plans completed across 5 phases
- v10: 18 plans completed across 6 phases
- v11: 8 plans completed across 3 phases
- v12: 9 plans completed across 3 phases

**Recent Trend:**
- Last 5 plans: 12-06, 12-07, 12-08, 12-09, 2026-03-16-production-signer-readiness
- Trend: v12 and the signer-readiness closeout are merged on `main`; the next value line is registry refresh policy and offline-safe snapshot mirroring

## Accumulated Context

### Decisions

Decisions are logged in `PROJECT.md`.

- 2026-03-08: Start GSD-managed planning history at v9 and number tracked phases from 1.
- 2026-03-08: Skip separate milestone research because the codebase map and repo docs already expose the v9 problem space.
- 2026-03-08: Keep v9/v10 implementation Bash/Python/JSON-native.
- 2026-03-08: Make `self` registry explicitly `local-only` so sync never hard-resets the working repository.
- 2026-03-08: Surface exact registry commit/tag identity through resolver, install manifest, and catalog exports.
- 2026-03-08: Keep dependency constraints backward-compatible with legacy `skill` / `skill@version` strings while preferring object entries with version ranges and registry hints.
- 2026-03-08: Make install and sync plan the full dependency graph before copying files, and fail on dependency lock violations or reverse conflicts.
- 2026-03-09: Make computed review state authoritative, while keeping `_meta.json.review_state` synced as a compatibility field.
- 2026-03-09: Drive reviewer allowlists and quorum from policy-defined reviewer groups with stage/risk overrides.
- 2026-03-09: Make signed, pushed `skill/<name>/v<version>` tags the authoritative stable release snapshot and require explicit preview mode for pre-release note inspection.
- 2026-03-09: Make SSH-signed, repo-verified release attestations mandatory for written release artifacts when the v9 attestation policy is enabled.
- 2026-03-09: Preserve legacy unqualified identities while adding first-class publisher namespaces and machine-readable release actor auditing.
- 2026-03-09: Add explicit bootstrap helpers for SSH signing keys, allowed signer trust roots, and publisher actor authorization instead of relying on manual repo spelunking.
- 2026-03-09: Keep signing doctor output non-mutating and explanatory so it improves operator diagnostics without weakening the existing release and attestation gates.
- 2026-03-14: Keep CI-native provenance as an explicit second trust path and let policy require `ssh`, `ci`, or `both` without collapsing the SSH-based release path.
- 2026-03-14: Reuse generated discovery indexes and immutable manifests for search, inspect, and explain flows instead of adding a separate backend.
- 2026-03-15: Add a deterministic recommendation layer as v10 Phase 6, driven by explicit metadata, trust state, compatibility evidence, quality, and verification freshness.
- 2026-03-16: Treat the current platform as "M1 complete: AI-first registry core" and adopt "M2: AI-usable skill ecosystem" as v12.
- 2026-03-16: Start v12 by making AI decision metadata and `publish-skill` / `pull-skill` result schemas canonical before adding more real skills or ranking heuristics.
- 2026-03-16: Complete all three v12 phases on `main`, including canonical decision metadata, real skill inventory, AI-only drills, failure-path hardening, comparative recommendation signals, and a stable usage guide.

### Pending Todos

- Finalize the v13 roadmap update and first implementation plan for registry refresh cadence / freshness policy.
- Decide the exact state format and operator surface for registry refresh metadata before implementation begins.
- Plan how immutable registry snapshots should integrate with resolver/install flows without weakening current mirror trust boundaries.
- Decide whether CI-native attestations should remain additive to, or eventually become authoritative over, the repo-managed SSH path.
- Keep governance-integration and supply-chain backlog items deferred unless v13 work exposes a dependency.

### Blockers/Concerns

- `config/allowed_signers` now contains a committed `lvxiaoer` trusted signer entry.
- `operate-infinitas-skill` already has a signed pushed stable tag plus verified provenance.
- The signer-readiness closeout is merged to `main`, but `.planning` still needs to be advanced from closeout mode into the chosen v13 milestone.
- Registry freshness and offline snapshot behavior do not yet exist as first-class contracts, so operators still rely on ad-hoc cache expectations.
- The repository still installs skills by bare folder name for backward compatibility; any future multi-publisher same-slug work should stay compatibility-aware.
- The project should stay Git-native and private-first; public marketplace features, social features, and on-chain reputation remain intentionally deferred.

## Session Continuity

Last session: 2026-03-16 18:30 GMT+8
Stopped at: v13 selected as registry operations; planning and phase-1 implementation plan in progress
Resume file: `.planning/ROADMAP.md`
