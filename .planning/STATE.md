# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-15)

**Core value:** Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.
**Current focus:** v11 Phase 2 — Multi-Team Governance and Exceptions

## Current Position

Phase: v11 Phase 2 of 3 (Multi-Team Governance and Exceptions)
Plan: `docs/plans/2026-03-15-break-glass-exceptions.md`
Status: 11-04 complete; 11-05 is next
Last activity: 2026-03-15 — Completed 11-04 by adding shared exception policy plus exception-aware promotion and release traces

Progress: [█████████▓] 92%

## Performance Metrics

**Velocity:**
- Total plans completed: 36
- Average duration: n/a
- Total execution time: n/a

**By Phase:**
- v9: 14 plans completed across 5 phases
- v10: 18 plans completed across 6 phases
- v11: 4 plans completed across 3 phases

**Recent Trend:**
- Last 5 plans: 10-18, 11-01, 11-02, 11-03, 11-04
- Trend: break-glass exceptions landed; delegated audit export is next

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

- Execute 11-05 so delegated approvals and exception usage are exported cleanly into audit-facing outputs.
- Bootstrap real trusted signer entries in `config/allowed_signers` before the first actual stable release.
- Decide whether CI-native attestations should be additive to, or eventually authoritative over, the repo-managed SSH path.
- Decide how much delegated approval and exception provenance should be exported into release metadata versus separate audit views in 11-05.

### Blockers/Concerns

- `config/allowed_signers` still contains bootstrap guidance comments only; Phase 2 added the bootstrap and doctor flow, but a real production signer ceremony is still pending.
- Phase 2 needs a shared team model that can expand into namespace ownership, reviewer groups, and future exception scopes without duplicating membership lists across policy files.
- 11-05 still needs a clean additive audit surface so delegated approvals and exception usage can be exported without baking transient debug details into release provenance.
- The repository still installs skills by bare folder name for backward compatibility; future v10 work may revisit how far concurrent same-slug publisher installs should go.
- v10 should stay Git-native and private-first; public marketplace features, social features, and on-chain reputation are intentionally deferred.

## Session Continuity

Last session: 2026-03-15 09:00 GMT+8
Stopped at: 11-04 implementation completed; next logical step is planning and executing 11-05
Resume file: `docs/plans/2026-03-15-break-glass-exceptions.md`
