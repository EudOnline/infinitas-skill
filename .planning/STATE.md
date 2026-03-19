# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-19)

**Core value:** Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.
**Current focus:** close out v16 planning state after merging installed integrity and repair on `main`; the next milestone is not committed yet.

## Current Position

Phase: v16 complete / post-milestone closeout
Plan: `docs/plans/2026-03-18-installed-skill-integrity-and-repair.md`
Status: v16 is completed and merged on `main`; post-v16 milestone planning has not started yet
Last activity: 2026-03-19 — Re-verified the merged v16 result on `main`, deleted the feature worktree/branch, and restored the local planning drafts for closeout
Progress: [##########] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 67
- Average duration: n/a
- Total execution time: n/a

**By Phase:**
- v9: 14 plans completed across 5 phases
- v10: 18 plans completed across 6 phases
- v11: 8 plans completed across 3 phases
- v12: 9 plans completed across 3 phases
- v13: 6 plans completed across 2 phases
- v14: 4 plans completed across 2 phases
- v15: 4 plans completed across 2 phases
- v16: 4 plans completed across 2 phases

**Recent Trend:**
- Last 5 plans: 2026-03-16-registry-refresh-cadence-and-freshness, 2026-03-17-registry-snapshot-mirroring-and-offline-resolution, 2026-03-17-platform-native-review-evidence-and-reviewer-rotation, 2026-03-17-supply-chain-transparency-and-reproducible-release-metadata, 2026-03-18-installed-skill-integrity-and-repair
- Trend: v16 is now complete on `main`; the next planning slice should stay adjacent to installed-runtime trust, compatibility, and auditability rather than expanding scope dramatically

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
- 2026-03-17: Complete v15 on `main` by merging signed released-file inventories, reproducibility metadata, transparency-log publication, and additive audit summaries.
- 2026-03-18: Start v16 by extending v15's signed `file_manifest` into installed-runtime verification before adding any broader consumer-policy or compliance surface.
- 2026-03-18: Keep repair exact-source and manifest-driven so drift recovery restores the recorded immutable release instead of silently selecting a newer candidate.
- 2026-03-18: Complete v16 on `main` by merging installed-skill verification, persisted integrity summaries, exact-source repair, and drift-aware sync or upgrade guardrails.
- 2026-03-18: Keep install-time compatibility additive for older hosted manifests by degrading missing signed `file_manifest` metadata to `integrity.state = unknown` while preserving strict explicit verification.

### Pending Todos

- Choose the next post-v16 milestone and keep it close to manifest-driven consumer trust, compatibility, or auditability.
- Decide whether repair operations should emit a dedicated audit-history surface beyond the current install-manifest state update.
- Decide whether legacy hosted releases should be backfilled with signed `file_manifest` metadata so `integrity.state = unknown` becomes exceptional.
- Decide whether explicit installed-skill verification results should be exported through a stable audit/report surface.
- Keep future work beyond v16 constrained unless installed-runtime verification exposes a stronger dependency.

### Blockers/Concerns

- `config/allowed_signers` now contains a committed `lvxiaoer` trusted signer entry.
- `operate-infinitas-skill` already has a signed pushed stable tag plus verified provenance.
- Some older hosted distribution manifests still lack signed `file_manifest` metadata, so compatible installs may persist `integrity.state = unknown` until those immutable artifacts are regenerated or backfilled.
- Full hosted-registry e2e remains environment-sensitive and is still skipped when `fastapi`, `httpx`, `jinja2`, or `sqlalchemy` are unavailable in the current Python environment.
- The repository still installs skills by bare folder name for backward compatibility; any future multi-publisher same-slug work should stay compatibility-aware.
- The project should stay Git-native and private-first; public marketplace features, social features, and on-chain reputation remain intentionally deferred.

## Session Continuity

Last session: 2026-03-19 17:49 GMT+8
Stopped at: v16 closed out on `main`; next is post-v16 milestone definition
Resume file: `docs/plans/2026-03-18-installed-skill-integrity-and-repair.md`
