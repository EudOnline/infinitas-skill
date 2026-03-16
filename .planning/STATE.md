# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-16)

**Core value:** Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.
**Current focus:** v11 complete; next milestone planning pending

## Current Position

Phase: v11 Phase 3 of 3 (Federation, Mirrors, and Audit Export)
Plan: `docs/plans/2026-03-16-federation-boundaries-recovery.md`
Status: v11 complete through 11-08
Last activity: 2026-03-16 — Completed 11-08 federation trust boundaries, failure modes, and recovery documentation

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 39
- Average duration: n/a
- Total execution time: n/a

**By Phase:**
- v9: 14 plans completed across 5 phases
- v10: 18 plans completed across 6 phases
- v11: 8 plans completed across 3 phases

**Recent Trend:**
- Last 5 plans: 11-04, 11-05, 11-06, 11-07, 11-08
- Trend: v11 Phase 3 is complete; the next work item is future milestone selection rather than more federation mechanics

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

### Pending Todos

- Bootstrap real trusted signer entries in `config/allowed_signers` before the first actual stable release.
- Decide whether CI-native attestations should be additive to, or eventually authoritative over, the repo-managed SSH path.
- Decide which Phase 3 audit or inventory exports should stay release/provenance-only versus become separate catalog-facing products.
- Select the next milestone after v11 now that policy packs, federation rules, export artifacts, and recovery guidance are in place.

### Blockers/Concerns

- `config/allowed_signers` still contains bootstrap guidance comments only; Phase 2 added the bootstrap and doctor flow, but a real production signer ceremony is still pending.
- Phase 2 needs a shared team model that can expand into namespace ownership, reviewer groups, and future exception scopes without duplicating membership lists across policy files.
- Future work should avoid broadening Phase 3 again without a new milestone, since v11’s current scope is now complete.
- The repository still installs skills by bare folder name for backward compatibility; future v10 work may revisit how far concurrent same-slug publisher installs should go.
- v10 should stay Git-native and private-first; public marketplace features, social features, and on-chain reputation are intentionally deferred.

## Session Continuity

Last session: 2026-03-15 09:00 GMT+8
Stopped at: v11 complete
Resume file: `.planning/ROADMAP.md`
