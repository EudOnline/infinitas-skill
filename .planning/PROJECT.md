# infinitas-skill

## What This Is

`infinitas-skill` is a private skill registry and operations toolkit for Claude Code, Codex, and OpenClaw. It keeps private skills, templates, validation scripts, promotion controls, install/sync helpers, and release tooling in one Git-native repository so maintainers can evolve agent skills without turning the registry into an uncontrolled prompt dump.

## Core Value

Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.

## Current Milestone: v14 Governance Integration and Reviewer Operations

**Goal:** Make review governance easier to integrate and operate by ingesting platform-native approval evidence as additive quorum input and generating deterministic reviewer rotation or escalation suggestions from existing policy groups.

**Target features:**
- Normalized platform approval evidence that can be committed or mirrored into the repo and counted alongside `reviews.json`
- Review, promotion, release, and catalog surfaces that preserve whether approvals came from repo-native or imported platform evidence
- Deterministic reviewer recommendation and escalation output based on configured groups, team scopes, owners, and recent review history

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
- [ ] Plan and implement v14 Phase 1: platform-native approval evidence ingestion (`REV-04`).
- [ ] Plan and implement v14 Phase 2: reviewer rotation and escalation suggestions (`REV-05`).
- [ ] Keep future work beyond v14 narrowed to supply-chain transparency (`ATT-04/ATT-05`) unless governance-integration work exposes a stronger dependency.

### Out of Scope

- Hosted registry service, database, or web UI — the repository remains intentionally Git-native and file-based for v14.
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
- Future requirements now point most directly at governance integration through imported platform review evidence and reviewer guidance.

## Constraints

- **Tech stack**: Keep v12 changes native to Bash, Python, JSON, and Markdown — the repository is already built around lightweight CLI tooling.
- **Architecture discipline**: Improve author metadata, generated indexes, tests, and docs before adding more registry services or background automation.
- **Compatibility**: Preserve the existing local-filesystem plus Git workflow so current install/sync/promotion commands remain usable.
- **Security**: Shared-secret-only signing is insufficient for release authenticity; asymmetric verification remains the trusted path.
- **Governance**: Publisher ownership, reviewer evidence, and release actor identity must be repository-configurable so policy changes are versioned and reviewable.
- **Private-first**: Keep the repository Git-native and private-registry-first; do not turn v12 into public marketplace or hosted-service scope creep.
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
| Adopt `M2: AI-usable skill ecosystem` as v12 instead of another release-engineering milestone | The platform review shows the core registry mechanics are strong enough; the main remaining gap is decision-useful content and metadata | ✓ Good |
| Start v12 with canonical decision metadata and wrapper result schemas | The current AI index already carries trust and compatibility, but still hardcodes empty selection guidance and lacks dedicated publish/pull schemas | ✓ Good |
| Keep v12 additive and Git-native | The goal is to make the existing registry more useful to AI agents, not replace it with a new service layer | ✓ Good |

---
*Last updated: 2026-03-17 after completing v13 on `main` and starting v14 governance-integration planning*
