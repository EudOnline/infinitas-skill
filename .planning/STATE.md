# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-17)

**Core value:** Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.
**Current focus:** v15 supply-chain planning after completing and merging v14 governance integration on `main`.

## Current Position

Phase: v15 Phase 1 planning
Plan: `docs/plans/2026-03-17-supply-chain-transparency-and-reproducible-release-metadata.md`
Status: v14 is completed and merged on `main`; v15 planning is starting on `main`
Last activity: 2026-03-17 — Merged v14 governance integration to `main`, verified the merged result, and opened the next supply-chain planning slice
Progress: [##--------] 20%

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
- Last 5 plans: 2026-03-16-production-signer-readiness, 2026-03-16-registry-refresh-cadence-and-freshness, 2026-03-17-registry-snapshot-mirroring-and-offline-resolution, 2026-03-17-platform-native-review-evidence-and-reviewer-rotation
- Trend: v14 is now complete on `main`; the next value line is stronger supply-chain transparency around released artifacts

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
- 2026-03-17: Complete v13 Phase 1 by adding validated refresh policy, persisted refresh state, freshness status output, and stale-cache warn/fail enforcement.
- 2026-03-17: Treat registry snapshots as additive, explicit artifacts derived from existing registries rather than introducing a new authoritative registry kind.
- 2026-03-17: Keep platform-native approval ingestion additive and file-backed so review quorum remains deterministic and testable offline.
- 2026-03-17: Base reviewer rotation and escalation suggestions on existing configured review groups and recent decision history, not a new scheduling system.
- 2026-03-17: Complete v14 on `main` by merging platform-native review evidence ingestion plus reviewer recommendation and escalation guidance.
- 2026-03-17: Start v15 with reproducible release metadata before transparency publication so any external log entry anchors a richer signed artifact.
- 2026-03-17: Keep transparency publication additive to the current SSH and CI verification model rather than replacing offline verification with a network dependency.

### Pending Todos

- Write and execute the dedicated v15 Phase 1/2 plan for reproducible release metadata and transparency publication.
- Define the signed file-manifest and reproducible-build metadata contract shared by provenance and distribution manifests.
- Decide how transparency-log proofs should be stored in provenance, release-state, and catalog surfaces without weakening offline verification.
- Decide whether SSH attestations, CI attestations, or both should be publishable to the transparency log under policy.
- Keep future work beyond v15 constrained unless supply-chain implementation exposes a stronger dependency.

### Blockers/Concerns

- `config/allowed_signers` now contains a committed `lvxiaoer` trusted signer entry.
- `operate-infinitas-skill` already has a signed pushed stable tag plus verified provenance.
- No external transparency-log integration exists yet, so release trust currently stops at repo-local SSH and CI verification.
- Current provenance and distribution manifests do not yet commit to a full released-file inventory or normalized build reproducibility metadata.
- The repository still installs skills by bare folder name for backward compatibility; any future multi-publisher same-slug work should stay compatibility-aware.
- The project should stay Git-native and private-first; public marketplace features, social features, and on-chain reputation remain intentionally deferred.

## Session Continuity

Last session: 2026-03-17 10:35 GMT+8
Stopped at: v14 merged to `main`; next is v15 planning for reproducible release metadata and transparency publication
Resume file: `docs/plans/2026-03-17-supply-chain-transparency-and-reproducible-release-metadata.md`
