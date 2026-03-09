# Roadmap: infinitas-skill

## Milestones

- ✅ **v9 Registry Trust, Quorum, and Attestation** - Phases 1-5 (completed 2026-03-09)

## Phases

### ✅ v9 Registry Trust, Quorum, and Attestation (Completed)

**Milestone Goal:** Turn existing registry governance intent into enforced policy for remote registry updates, dependency resolution, reviewer quorum, and release authenticity.

#### ✅ Phase 1: Registry Source Policy and Safe Sync
**Goal**: Define and enforce remote registry fetch/update policy so sync and resolution are trust-aware and immutable enough for downstream install/release work.
**Depends on**: Nothing (first phase)
**Requirements**: [REG-01, REG-02, REG-03]
**Success Criteria** (what must be TRUE):
  1. Maintainer can declare registry trust, pinning, and update policy in repository configuration that passes validation.
  2. Sync refuses remote states that violate allowed host, allowed ref, or allowed update policy and explains why.
  3. Resolver and install-related commands surface the selected registry plus exact commit or tag for the chosen skill.
  4. Local-development semantics for the `self` registry are explicit, so sync no longer risks destructive surprises.
**Plans**: 3 plans

Plans:
- [x] 01-01: Extend registry source schema, validation, and docs for trust/pinning/update policy
- [x] 01-02: Enforce safe sync semantics in registry fetch/update scripts
- [x] 01-03: Export resolved source identity into resolver, install, and catalog metadata

#### ✅ Phase 2: Dependency Upgrade Planning and Conflict Solver
**Goal**: Make dependency upgrades deterministic by introducing machine-checked constraints, upgrade planning, and actionable conflict reporting across registry sources.
**Depends on**: Phase 1
**Requirements**: [DEP-01, DEP-02, DEP-03]
**Success Criteria** (what must be TRUE):
  1. Maintainer can express dependency version constraints and source hints in validated metadata.
  2. Validation reports incompatible or unresolved dependency graphs before promotion, install, or release.
  3. Install or sync can print a deterministic upgrade/resolution plan and either apply it consistently or fail with actionable conflicts.
**Plans**: 3 plans

Plans:
- [x] 02-01: Define dependency constraint format and registry-aware resolution rules
- [x] 02-02: Add upgrade planning plus conflict detection to integrity and install checks
- [x] 02-03: Wire deterministic resolution output into install/sync workflows and documentation

#### ✅ Phase 3: Reviewer Groups and Quorum Enforcement
**Goal**: Replace mutable review summaries with policy-driven reviewer groups and computed quorum that promotion tooling can enforce.
**Depends on**: Phase 2
**Requirements**: [REV-01, REV-02, REV-03]
**Success Criteria** (what must be TRUE):
  1. Repository policy can define reviewer groups and stage/risk-specific quorum rules.
  2. Review tooling accepts only configured reviewers, computes effective quorum from the latest distinct decisions, and reports unmet group coverage.
  3. Promotion fails when quorum is unmet, required groups are missing, or blocking rejections remain unresolved.
**Plans**: 3 plans

Plans:
- [x] 03-01: Add reviewer-group and quorum policy schema plus defaults
- [x] 03-02: Refactor review request/status/approval scripts to compute authoritative review state
- [x] 03-03: Enforce computed quorum in promotion, catalog generation, and docs

#### ✅ Phase 4: Signed Release Invariants
**Goal**: Make release creation depend on a clean, synchronized repository state and a signed git tag before any release is considered valid.
**Depends on**: Phase 3
**Requirements**: [ATT-01]
**Success Criteria** (what must be TRUE):
  1. Release tooling fails when the worktree is dirty, the branch is out of sync with upstream, or the expected tag state is missing.
  2. Signed tag creation and verification are the default release path for stable releases.
  3. Release output references an immutable, pushed source snapshot rather than best-effort local state.
**Plans**: 2 plans

Plans:
- [x] 04-01: Add clean-tree, upstream-sync, and signed-tag guards to release workflows
- [x] 04-02: Update release docs/checklists to make immutable signed releases the default path

#### ✅ Phase 5: Asymmetric Attestation and Verification
**Goal**: Produce and verify release attestations that capture exact source and dependency context with asymmetric signatures managed by the repository.
**Depends on**: Phase 4
**Requirements**: [ATT-02, ATT-03]
**Success Criteria** (what must be TRUE):
  1. Generated provenance/attestation records source commit or tag, registry resolution context, dependency context, and signer identity.
  2. Repository-managed allowed signers can verify release attestations with asymmetric signatures.
  3. Distribution or release commands reject unattested or unverified artifacts when v9 policy is enabled.
**Plans**: 3 plans

Plans:
- [x] 05-01: Expand provenance schema and generation to capture immutable release context
- [x] 05-02: Make SSH/asymmetric signing and verification first-class in release tooling
- [x] 05-03: Enforce attestation verification in release/distribution paths and document the bootstrap flow

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Registry Source Policy and Safe Sync | v9 | 3/3 | Completed | 2026-03-08 |
| 2. Dependency Upgrade Planning and Conflict Solver | v9 | 3/3 | Completed | 2026-03-08 |
| 3. Reviewer Groups and Quorum Enforcement | v9 | 3/3 | Completed | 2026-03-09 |
| 4. Signed Release Invariants | v9 | 2/2 | Completed | 2026-03-09 |
| 5. Asymmetric Attestation and Verification | v9 | 3/3 | Completed | 2026-03-09 |
