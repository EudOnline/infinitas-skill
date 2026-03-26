# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-20)

**Core value:** Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.
**Current focus:** project complete on `main`, no active milestone.

## Current Position

Phase: steady-state
Plan: `docs/plans/2026-03-20-project-completion-and-steady-state.md`
Status: v20 complete on `main`; the repository is in steady-state until a new milestone is intentionally opened
Last activity: 2026-03-20 — Re-ran the completion regression, installed-integrity regression matrix, distribution/install regressions, and `scripts/check-all.sh` on `main`
Progress: [##########] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 85
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
- v17: 4 plans completed across 2 phases
- v18: 4 plans completed across 2 phases
- v19: 4 plans completed across 2 phases
- v20: 6 plans completed across 3 phases

**Recent Trend:**
- Last 5 plans: 2026-03-18-installed-skill-integrity-and-repair, 2026-03-19-installed-integrity-reporting-and-legacy-backfill, 2026-03-19-installed-integrity-freshness-and-history-retention, 2026-03-19-installed-integrity-stale-verification-guardrails, 2026-03-19-never-verified-policy-and-project-closeout
- Trend: project delivery is complete on `main`; future work should be framed as maintenance or a new deliberate milestone

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
- 2026-03-19: Start v17 by targeting the two remaining post-v16 gaps that most affect installed-runtime trust: legacy immutable artifacts that cannot yet verify fully, and the absence of one stable local installed-integrity report surface.
- 2026-03-19: Prefer deterministic backfill from committed provenance plus bundle artifacts over introducing special-case trust exceptions for older immutable releases.
- 2026-03-19: Complete v17 on the implementation branch `codex/v17-installed-reporting`, then merge it onto `main` on 2026-03-20 with deterministic legacy manifest backfill, release-surface integrity capability summaries, and target-local installed-integrity reporting plus additive event history.
- 2026-03-19: Keep the next milestone local and maintenance-focused by adding explicit freshness classification before considering any broader fleet or hosted runtime service.
- 2026-03-19: Keep current trust summary inline in the install manifest, but plan for sidecar spillover when integrity event volume grows.
- 2026-03-19: Complete v18 on the implementation branch `codex/v17-installed-reporting`, then merge it onto `main` on 2026-03-20 with repo-managed freshness policy, freshness-aware report/list surfaces, bounded inline integrity history, and target-local sidecar snapshot export.
- 2026-03-19: Draft v19 on the implementation branch `codex/v17-installed-reporting` so stale-but-clean installed copies can participate in policy-governed overwrite guardrails without introducing auto-refresh or hosted runtime state.
- 2026-03-19: Complete v19 on the implementation branch `codex/v17-installed-reporting`, then merge it onto `main` on 2026-03-20 with shared stale-policy evaluation, read-only advisory surfaces, mutation guardrails, docs, and full verification.
- 2026-03-19: Propose v20 as a closeout milestone focused on `never-verified` policy, deterministic hosted-registry e2e coverage, and final project completion gates.
- 2026-03-19: Complete v20 on the implementation branch `codex/v17-installed-reporting`, then merge it onto `main` on 2026-03-20 with `freshness.never_verified_policy`, shared mutation-readiness reporting, never-verified mutation guardrails, deterministic CI hosted e2e enforcement, and `docs/project-closeout.md`.
- 2026-03-19: Keep hosted-registry e2e compatibility explicit: CI installs `python3 -m pip install .` and requires the hosted dependency set, while minimal local environments may still skip until those dependencies are installed explicitly.
- 2026-03-20: Treat v20 as complete on `main` and keep the remaining compatibility notes as accepted steady-state maintenance notes unless a concrete defect appears.

### No Active Milestone

- The repository is complete on `main`; open a new plan before starting another milestone.
- Treat the documented compatibility quirks as accepted maintenance notes unless a concrete user-facing defect appears.
- Re-run the closeout verification matrix when future maintenance touches installed-integrity or hosted-registry behavior.

### Blockers/Concerns

- `config/allowed_signers` now contains a committed `lvxiaoer` trusted signer entry.
- `operate-infinitas-skill` already has a signed pushed stable tag plus verified provenance.
- Some older hosted distribution manifests may still remain compatibility-only `unknown` when immutable evidence is incomplete; v17 backfill improves but cannot invent missing provenance.
- Full hosted-registry e2e remains environment-sensitive in minimal local Python environments and still skips unless `fastapi`, `httpx`, `jinja2`, `sqlalchemy`, and `uvicorn` are installed; CI now installs them deterministically via `python3 -m pip install .` and requires the check.
- Legacy installed-integrity reports may classify freshness from `integrity.last_verified_at` while leaving top-level `last_checked_at = null` until an explicit refresh rewrites the canonical field; this remains compatibility-safe but should stay documented.
- The repository still installs skills by bare folder name for backward compatibility; any future multi-publisher same-slug work should stay compatibility-aware.
- The project should stay Git-native and private-first; public marketplace features, social features, and on-chain reputation remain intentionally deferred.

## Session Continuity

Last session: 2026-03-20 GMT+8
Stopped at: Project complete on `main`; future work should start from a new milestone or maintenance plan
Resume file: `docs/project-closeout.md`
