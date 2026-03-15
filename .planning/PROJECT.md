# infinitas-skill

## What This Is

`infinitas-skill` is a private skill registry and operations toolkit for Claude Code, Codex, and OpenClaw. It keeps private skills, templates, validation scripts, promotion controls, install/sync helpers, and release tooling in one Git-native repository so maintainers can evolve agent skills without turning the registry into an uncontrolled prompt dump.

## Core Value

Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.

## Current Milestone: v11 Policy-as-Code and Organizational Controls

**Goal:** Extend the private registry from single-maintainer governance into explainable, team-oriented policy enforcement with federation-ready controls.

**Target features:**
- Reusable policy packs and repository-level loading or override rules
- Explainable policy traces for validation, promotion, release, install, and distribution decisions
- Team ownership models, delegated approval scopes, and explicit break-glass exceptions
- Federation or mirror rules plus audit and inventory export surfaces

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
- ✓ Stable releases emit immutable bundles and distribution manifests, and install or sync can materialize from those manifests instead of only the live working tree.
- ✓ Consumers can search, inspect, explain, and recommend skills via `scripts/search-skills.sh`, `scripts/inspect-skill.sh`, `scripts/resolve-skill.sh`, `scripts/install-by-name.sh`, `scripts/check-skill-update.sh`, `scripts/upgrade-skill.sh`, and `scripts/recommend-skill.sh`.

### Active

- [x] Policy packs and repository-level loading rules are complete for v11 Phase 1.
- [x] Explainable policy decision traces are complete for validation, promotion, release, and registry debug flows.
- [x] Team governance plus delegated namespace/review scopes are complete for 11-03.
- [ ] Break-glass exceptions and delegated audit exports are the current v11 focus.

### Out of Scope

- Hosted registry service, database, or web UI — the repository remains intentionally Git-native and file-based.
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
- `config/allowed_signers` is still intentionally bootstrapped with guidance comments only; maintainers must commit real trusted signer entries before the first actual stable release is operationally complete.

## Constraints

- **Tech stack**: Keep v10/v11 changes native to Bash, Python, JSON, and Markdown — the repository is already built around lightweight CLI tooling.
- **Compatibility**: Preserve the existing local-filesystem plus Git workflow so current install/sync/promotion commands remain usable.
- **Security**: Shared-secret-only signing is insufficient for release authenticity; asymmetric verification remains the trusted path.
- **Governance**: Publisher ownership, reviewer evidence, and release actor identity must be repository-configurable so policy changes are versioned and reviewable.
- **v11 rollout**: Policy packs must stay additive at first; existing file paths should remain valid until pack loading is proven stable.
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

---
*Last updated: 2026-03-15 after v11 Phase 1 completion and Phase 2 planning kickoff*
