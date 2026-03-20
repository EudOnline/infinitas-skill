# infinitas-skill

## What This Is

`infinitas-skill` is a private skill registry and operations toolkit for Claude Code, Codex, and OpenClaw. It keeps private skills, templates, validation scripts, promotion controls, install/sync helpers, and release tooling in one Git-native repository so maintainers can evolve agent skills without turning the registry into an uncontrolled prompt dump.

## Core Value

Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.

## Current Milestone: Project Complete on Main

**Goal:** Record the v20 closeout milestone as complete on `main`, keep steady-state expectations explicit, and avoid reopening closeout scope without a new milestone.

**Status:** v20 is complete on `main`. The project is now in steady-state unless a new milestone is intentionally started. The merged baseline includes `never_verified_policy`, shared mutation readiness, never-verified mutation guardrails, deterministic CI hosted e2e enforcement, and the final closeout checklist.

**Completed feature set:**
- A validated `never_verified_policy` that lets maintainers ignore, warn, or block overwrite-style mutation for legacy `never-verified` installs
- One shared mutation-readiness contract that unifies drift, stale, and never-verified guidance for read-only and mutation flows
- Deterministic hosted-registry end-to-end verification in CI plus one final closeout checklist that defines when the project is ready to merge and declare complete

## Requirements

### Validated

- ✓ Maintainer can scaffold a new skill from templates and place it into the lifecycle directories via `scripts/new-skill.sh` and `templates/*`.
- ✓ Maintainer can validate skill metadata, registry integrity, namespace policy, and promotion policy locally and in CI via `scripts/check-skill.sh`, `scripts/check-all.sh`, and `.github/workflows/validate.yml`.
- ✓ Maintainer can promote approved skills and regenerate install/search catalogs via `scripts/promote-skill.sh` and `scripts/build-catalog.sh`.
- ✓ Maintainer can install, sync, switch, and roll back skills into agent-local directories via `scripts/install-skill.sh`, `scripts/sync-skill.sh`, `scripts/switch-installed-skill.sh`, and `scripts/rollback-installed-skill.sh`.
- ✓ Maintainer can preview a release, verify stable release invariants, create signed tags, emit dependency-aware release attestations, and verify those attestations via `scripts/check-release-state.py`, `scripts/release-skill-tag.sh`, `scripts/release-skill.sh`, `scripts/generate-provenance.py`, and `scripts/verify-attestation.py`.
- ✓ Maintainer can generate and verify CI-native attestation payloads, and release policy can require `ssh`, `ci`, or `both`, via `.github/workflows/release-attestation.yml`, `scripts/generate-ci-attestation.py`, `scripts/verify-ci-attestation.py`, and `config/signing.json`.
- ✓ Skill metadata, dependency refs, catalogs, release state, and attestations can now carry publisher-qualified identity plus author/reviewer/releaser/signer audit fields.
- ✓ Maintainer can bootstrap SSH signer material, wire trusted signer identities into repository policy, diagnose release blockers, and rehearse the first stable release via `scripts/bootstrap-signing.py`, `scripts/doctor-signing.py`, and `scripts/test-signing-bootstrap.py`.
- ✓ Maintainer can inspect repository-level signing readiness, including trusted signer enrollment, local SSH signing configuration, stable tag verification, and provenance verification, via `scripts/report-signing-readiness.py` and `scripts/test-signing-readiness-report.py`.
- ✓ Stable releases emit immutable bundles and distribution manifests, and install or sync can materialize from those manifests instead of only the live working tree.
- ✓ Consumers can search, inspect, explain, and recommend skills via `scripts/search-skills.sh`, `scripts/inspect-skill.sh`, `scripts/resolve-skill.sh`, `scripts/install-by-name.sh`, `scripts/check-skill-update.sh`, `scripts/upgrade-skill.sh`, and `scripts/recommend-skill.sh`.

### Active

- [x] Plan and implement v13 Phase 1: registry refresh cadence and freshness policy (`REG-04`).
- [x] Plan and implement v13 Phase 2: immutable snapshot mirrors and offline resolution (`REG-05`).
- [x] Plan and implement v14 Phase 1: platform-native approval evidence ingestion (`REV-04`).
- [x] Plan and implement v14 Phase 2: reviewer rotation and escalation suggestions (`REV-05`).
- [x] Plan and implement v15 Phase 1: reproducible release metadata and full file manifests (`ATT-05`).
- [x] Plan and implement v15 Phase 2: external transparency log publication and verification (`ATT-04`).
- [x] Plan and implement v16 Phase 1: installed skill integrity and drift detection (`INST-01`).
- [x] Plan and implement v16 Phase 2: exact-source repair and update guardrails (`INST-02`).
- [x] Plan and implement v17 Phase 1: legacy distribution backfill and integrity capability reporting (`INST-03`).
- [x] Plan and implement v17 Phase 2: installed integrity audit history and local reports (`INST-04`).
- [x] Plan and implement v18 Phase 1: freshness policy and stale verification reporting (`INST-05`).
- [x] Plan and implement v18 Phase 2: history retention and target-local snapshot artifact (`INST-06`).
- [x] Plan and implement v19 Phase 1: stale-policy advisory surfaces and shared freshness-gate helpers (`INST-07`).
- [x] Plan and implement v19 Phase 2: stale verification guardrails for overwrite-style mutation flows (`INST-08`).
- [x] Plan and implement v20 Phase 1: never-verified policy and shared mutation readiness (`INST-09`).
- [x] Plan and implement v20 Phase 2: never-verified mutation guardrails and recovery paths (`INST-10`).
- [x] Plan and implement v20 Phase 3: deterministic hosted e2e verification and project closeout (`OPS-03`, `OPS-04`).

### Out of Scope

- Hosted registry service, database, web UI, or background daemon — the repository remains intentionally Git-native and file-based for v20.
- Rebuilding the lifecycle, templating, or catalog system from scratch — current planning extends existing workflows instead of replacing them.
- Public marketplace/package-manager integration — not needed to deliver private-registry distribution goals.
- Full reconstruction of v1-v8 planning history — the repository does not contain authoritative phase-by-phase planning records for those versions.

## Context

- Brownfield GSD initialization started on 2026-03-08 after creating a fresh `.planning/codebase/` map for the existing repository.
- Phase 1 of v10 introduced `policy/namespace-policy.json` and `scripts/skill_identity_lib.py` so publisher ownership, approved transfers, and authorized actor lists are repository-managed.
- Qualified dependency refs such as `publisher/skill@1.2.3` now resolve through the same deterministic dependency planner as legacy refs.
- Release state and attestation outputs now record publisher identity, review audit entries, releaser identity, signer identity, and namespace-policy context.
- Phase 2 added stepwise bootstrap helpers, a signing doctor, and an automated first-release rehearsal so operators no longer need to spelunk through repo internals to wire the first trusted signer.
- Phase 3 added immutable bundles, distribution manifests, and manifest-aware install or sync behavior for stable releases.
- Phase 4 added GitHub Actions-backed CI attestation generation plus local verification policy gates for `ssh`, `ci`, and `both`.
- Phase 5 added stable search, inspect, and explain-oriented consumer surfaces on top of generated discovery indexes and distribution manifests.
- Phase 6 added deterministic recommendation ranking driven by trust state, compatibility evidence, maturity, quality score, and verification freshness.
- v11 Phase 1 added reusable policy packs with ordered pack-to-local override resolution for promotion, namespace, signing, and registry source policy domains.
- v11 Phase 1 also added additive policy evaluation traces plus structured validation error output so allow/deny decisions can be debugged without breaking existing CLI flows.
- 11-03 added a shared team policy plus team-backed namespace ownership and reviewer-group resolution without breaking existing direct actor lists.
- 11-04 added a shared exception policy, stable promotion/release blocker ids, and additive `exception_usage` plus `policy_trace.exceptions` output for active waivers.
- 11-05 extends `check-release-state --json` and release provenance with stable delegated audit metadata such as review quorum context, delegated publisher teams, and applied release exception usage, while intentionally stopping short of a separate export product.
- 11-06 adds validated `registry_sources.federation` rules for `mirror` and `federated` upstreams, mapped publisher namespaces, additive resolver/catalog identity fields, and explicit non-authoritative mirror behavior while intentionally leaving standalone export formats to 11-07.
- 11-07 adds `catalog/inventory-export.json` and `catalog/audit-export.json`, generated from catalog and provenance artifacts, plus repository validation so portal/compliance consumers can rely on a stable JSON contract without depending on debug traces or live release-state recomputation.
- 11-08 adds a dedicated federation operations guide that defines authoritative surfaces, common failure modes, and operator recovery order for policy drift, stale mirrors, missing provenance, and stale export artifacts.
- `docs/platform-review-memo.md` recommends treating the current system as "M1 complete: AI-first registry core" and shifting the next milestone to "M2: AI-usable skill ecosystem".
- v12 completed the AI-usable skill ecosystem milestone by shipping canonical decision metadata, schema-backed publish/pull contracts, real skill inventory, AI-only workflow drills, failure-path hardening, comparative recommendation signals, and a stable usage guide.
- `catalog/ai-index.json` now exposes multiple real skills with authored selection guidance, runtime assumptions, verified compatibility evidence, and additive comparative recommendation signals.
- The post-v12 signer readiness closeout is now merged on `main`, including repository-level readiness reporting plus steady-state signer operations guidance.
- `config/allowed_signers` now contains a committed `lvxiaoer` trusted signer entry.
- `operate-infinitas-skill` already has a signed pushed stable tag plus verified provenance in `catalog/provenance/operate-infinitas-skill-0.1.1.json`.
- v13 Phase 1 and Phase 2 are now merged on `main`, adding validated refresh cadence policy, persisted refresh state, stale-cache enforcement, immutable registry snapshots, and explicit snapshot-backed resolve/install/sync flows.
- v14 is now merged on `main`, adding normalized `review-evidence.json` support, provenance-aware quorum evaluation, and deterministic reviewer recommendation plus escalation output in review CLI flows.
- v15 is now merged on `main`, adding signed released-file inventories, reproducibility metadata, transparency-log proof capture, and additive audit summaries across attestation, release-state, and catalog surfaces.
- v16 is now merged on `main`, adding `verify-installed-skill.py`, persisted install-manifest integrity summaries, `repair-installed-skill.sh`, drift-aware sync or upgrade guardrails, and compatibility fallback to `integrity.state = unknown` when older hosted manifests lack signed `file_manifest` entries.
- v17 is complete on `main`, adding deterministic legacy distribution-manifest backfill, installed-integrity capability summaries in release indexes, `scripts/report-installed-integrity.py`, and additive `integrity_events` in local install manifests.
- v18 is complete on `main`, adding repo-managed freshness policy, freshness-aware report/list output, bounded inline `integrity_events`, and deterministic target-local sidecar snapshot export for older retained history.
- The installed-runtime local trust surface is now materially more complete: immutable release verification stays separate, while target-local freshness and history lifecycle are explicit and bounded.
- v19 is complete on `main`, adding `stale_policy`, shared freshness-gate evaluation, read-only update guidance, stale mutation guardrails, and explicit refresh-first operator messaging.
- v20 is now complete on `main`, adding `freshness.never_verified_policy`, one shared mutation-readiness contract, never-verified overwrite guardrails, and `docs/project-closeout.md` as the final operator steady-state checklist.
- GitHub validation now installs repository package dependencies with `python3 -m pip install .` before running `scripts/check-all.sh`, and sets `INFINITAS_REQUIRE_HOSTED_E2E_TESTS=1` so hosted-registry e2e is deterministic in CI.
- Minimal local Python environments may still skip hosted-registry e2e until the same dependency set is installed explicitly; this is now a documented local workflow boundary rather than an implicit CI gap.

## Constraints

- **Tech stack**: Keep v20 changes native to Bash, Python, JSON, Markdown, and the existing GitHub Actions workflow — the repository is already built around lightweight CLI tooling.
- **Architecture discipline**: Improve author metadata, generated indexes, tests, and docs before adding more registry services or background automation.
- **Compatibility**: Preserve the existing local-filesystem plus Git workflow so current install/sync/promotion commands remain usable.
- **Security**: Shared-secret-only signing is insufficient for release authenticity; asymmetric verification remains the trusted path.
- **Governance**: Publisher ownership, reviewer evidence, and release actor identity must be repository-configurable so policy changes are versioned and reviewable.
- **Private-first**: Keep the repository Git-native and private-registry-first; do not turn v20 into public marketplace or hosted-service scope creep.
- **History**: GSD planning begins at v9; earlier release history may be referenced, but not reconstructed as authoritative planning data.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Start GSD-managed planning history at v9 with phase numbering from 1 | The repo existed before `.planning/` and does not contain authoritative prior phase plans | ✓ Good |
| Skip a separate research stage for v9 | The codebase map and repository docs already expose the required problem space for this milestone | ✓ Good |
| Keep the v9/v10 implementation shell/python/json-native | This minimizes migration risk and fits the current execution model | ✓ Good |
| Treat computed quorum and asymmetric attestation as enforcement points, not documentation-only guidance | The highest-risk gaps are governance and authenticity paths that are currently optional or mutable | ✓ Good |
| Make stable release output depend on verified, pushed `skill/<name>/v<version>` tags | Release notes and provenance must resolve against immutable source snapshots instead of best-effort local branch state | ✓ Good |
| Require verified SSH attestations for written release artifacts | Release notes and distribution output need source, dependency, and signer context bound to a repo-managed trust root | ✓ Good |
| Preserve legacy unqualified names while adding first-class `publisher/skill` identity | Existing install/sync consumers must keep working during the namespace transition | ✓ Good |
| Keep namespace ownership and approved transfers in repository policy | Publisher governance must be explicit, reviewable, and machine-enforced | ✓ Good |
| Record author, reviewer, releaser, signer, and namespace context in machine-readable release outputs | Governance decisions need a durable audit trail instead of implied operator knowledge | ✓ Good |
| Prefer stepwise signing bootstrap helpers over one-shot automation | Trusted signer enrollment changes both repo policy and local git config, so operators should be able to review and commit each step explicitly | ✓ Good |
| Keep signing doctor diagnostics non-mutating and fix-oriented | Phase 2 should improve operator visibility and onboarding without weakening existing release invariants or attestation enforcement | ✓ Good |
| Keep CI-native attestation as a second explicit trust path with policy-selectable `ssh`, `ci`, or `both` modes | Local and automated release trust need clear boundaries instead of replacing one proof system with another | ✓ Good |
| Reuse generated discovery indexes and immutable manifests for search, inspect, explain, and recommend flows | Consumer features should stay deterministic and file-backed instead of inventing a new service layer | ✓ Good |
| Make recommendation deterministic and metadata-driven | Agents need explainable, reviewable ranking instead of fuzzy install shortcuts | ✓ Good |
| Keep federation policy in `config/registry-sources.json` instead of env-var mirror settings | Mirror hooks are operational details, but federation trust rules must be consumer-visible, reviewable, and pack-compatible | ✓ Good |
| Keep `mirror` registries visible but non-authoritative for default resolution | Operators need inventory visibility without letting backup surfaces silently outrank trusted federated sources | ✓ Good |
| Derive inventory exports from generated catalog state and audit exports from committed provenance | Integrations need stable, reviewable artifacts; recomputing live release state would make export results depend on mutable workspace conditions | ✓ Good |
| Keep boundary and recovery guidance in one dedicated operations doc | Operators need a single place to understand disagreement between policy, exports, provenance, and mirrors without piecing together multiple partial docs | ✓ Good |
| Treat immutable registry snapshots as additive artifacts derived from an existing registry, not as a new authoritative registry kind | Offline recovery should be explicit and auditable without changing the existing trust and federation surface by default | ✓ Good |
| Keep platform-native approvals additive, normalized, and file-backed rather than live-API-dependent | Review quorum should remain deterministic, testable, and Git-native even when outside systems supply approval evidence | ✓ Good |
| Derive reviewer rotation and escalation suggestions from existing policy groups plus recent review history instead of introducing a scheduler | Operators need actionable reviewer guidance without adding a new stateful service or ownership model | ✓ Good |
| Sequence v15 as reproducible release metadata before external transparency publication | Transparency entries are more trustworthy if the signed artifact already commits to a full file inventory and normalized build context | ✓ Good |
| Keep transparency log publication additive and policy-driven | Local SSH and CI verification must remain usable offline even when transparency submission is unavailable or advisory | ✓ Good |
| Reuse v15's signed `file_manifest` as the installed-runtime integrity contract | The next trust gap is no longer release creation, but whether local installed copies still match the immutable artifact that was verified at install time | ✓ Good |
| Keep drift repair manifest-driven and exact-source | Repair should restore the recorded immutable version from the install manifest, not silently resolve whatever version happens to be latest today | ✓ Good |
| Regenerate legacy distribution manifests from committed provenance plus bundle evidence instead of accepting permanent compatibility-only gaps | When immutable artifacts already exist, backfill can restore full installed-integrity verification without changing the release trust model or adding a mutable exception path | ✓ Good |
| Keep installed-integrity reports local and manifest-driven instead of pushing runtime trust state into repo-scoped catalog exports | Installed runtime trust belongs to one target directory, so its durable audit surface should stay local, additive, and offline-usable | ✓ Good |
| Treat freshness as explicit policy-governed state, not an implicit interpretation of timestamps | Operators and agents should not have to guess whether a previously `verified` local result is still recent enough to trust | ✓ Good |
| Keep current trust summary inline but spill older integrity events into a target-local sidecar artifact when history grows | Long-lived installs need bounded manifest size without losing offline auditability or inventing repo-scoped runtime state | ✓ Good |
| Treat stale installed verification like a policy-governed mutation guardrail instead of a report-only hint | Once freshness is explicit, overwrite-style commands should be able to respect that signal without inventing any new runtime source of truth | ✓ Good |
| Keep `never-verified` as a distinct policy-governed state instead of silently collapsing it into stale or drifted behavior | Legacy installs and incomplete immutable evidence need explicit operator guidance without rewriting immutable trust semantics | ✓ Good |
| Make hosted-registry e2e deterministic in CI before declaring the project complete | A closeout milestone should remove routine verification skips from supported CI paths, even if local minimal environments may still opt into the dependency set explicitly | ✓ Good |
| Treat the next milestone as closeout work, not more platform expansion | The remaining gaps are behavioral clarity, deterministic verification, and completion gates rather than new registry capabilities | ✓ Good |
| Adopt `M2: AI-usable skill ecosystem` as v12 instead of another release-engineering milestone | The platform review shows the core registry mechanics are strong enough; the main remaining gap is decision-useful content and metadata | ✓ Good |
| Start v12 with canonical decision metadata and wrapper result schemas | The current AI index already carries trust and compatibility, but still hardcodes empty selection guidance and lacks dedicated publish/pull schemas | ✓ Good |
| Keep v12 additive and Git-native | The goal is to make the existing registry more useful to AI agents, not replace it with a new service layer | ✓ Good |

---
*Last updated: 2026-03-20 after confirming the project complete state on `main`*
