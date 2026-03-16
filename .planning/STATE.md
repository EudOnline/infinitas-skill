# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-16)

**Core value:** Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.
**Current focus:** v12 Phase 1 planning — Decision Metadata and AI Result Contracts

## Current Position

Phase: v12 Phase 1 of 3 (Decision Metadata and AI Result Contracts)
Plan: `docs/plans/2026-03-16-ai-decision-metadata-and-contracts.md`
Status: Phase 1 planned; 12-01 is the first implementation slice
Last activity: 2026-03-16 — Selected v12 AI-usable skill ecosystem and wrote the Phase 1 implementation plan

Progress: [----------] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 39
- Average duration: n/a
- Total execution time: n/a

**By Phase:**
- v9: 14 plans completed across 5 phases
- v10: 18 plans completed across 6 phases
- v11: 8 plans completed across 3 phases
- v12: 0 plans completed across 3 phases

**Recent Trend:**
- Last 5 plans: 11-04, 11-05, 11-06, 11-07, 11-08
- Trend: v11 is complete; v12 starts by making AI decision metadata and wrapper contracts canonical before adding more inventory or ranking depth

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

### Pending Todos

- Execute 12-01 so `_meta.json`, templates, and docs can describe `use_when`, `avoid_when`, `capabilities`, and runtime assumptions with validation.
- Follow 12-01 with 12-02 and 12-03 so generated indexes and AI wrapper outputs consume the canonical metadata and stable result schemas.
- Bootstrap real trusted signer entries in `config/allowed_signers` before the first actual stable release.
- Decide whether CI-native attestations should be additive to, or eventually authoritative over, the repo-managed SSH path.
- Decide whether the future registry-ops and supply-chain backlog items belong after v12 or should remain deferred behind ecosystem usefulness work.

### Blockers/Concerns

- `catalog/ai-index.json` currently exposes only one real skill, and that entry still has empty `use_when` / `avoid_when` guidance.
- `publish-skill.sh` and `pull-skill.sh` return JSON, but there are not yet dedicated schema files governing those result payloads.
- `config/allowed_signers` still contains bootstrap guidance comments only; Phase 2 added the bootstrap and doctor flow, but a real production signer ceremony is still pending.
- Future v12 work should avoid slipping back into more registry machinery unless it directly improves AI usability, selection quality, or learnability.
- The repository still installs skills by bare folder name for backward compatibility; future v10 work may revisit how far concurrent same-slug publisher installs should go.
- v10 should stay Git-native and private-first; public marketplace features, social features, and on-chain reputation are intentionally deferred.

## Session Continuity

Last session: 2026-03-16 09:40 GMT+8
Stopped at: v12 Phase 1 planning ready
Resume file: `docs/plans/2026-03-16-ai-decision-metadata-and-contracts.md`
