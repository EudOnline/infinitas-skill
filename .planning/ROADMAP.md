# Roadmap: infinitas-skill

## Milestones

- ✅ **v9 Registry Trust, Quorum, and Attestation** - Phases 1-5 (completed 2026-03-09)
- 🚧 **v10 Publisher Identity and Verified Distribution** - Phases 1-5 (in progress)
- 🗂️ **v11 Policy-as-Code and Organizational Controls** - Phases 1-3 (planned)

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

### 🚧 v10 Publisher Identity and Verified Distribution (In Progress)

**Milestone Goal:** Turn the hardened Git-native registry into a verified distribution system with explicit publisher identity, bootstrap-safe signing, and consumer-friendly install/search flows.

#### ✅ Phase 1: Publisher / Namespace Model
**Goal**: Introduce first-class publisher and namespace identity so skill ownership, release authority, and trusted actors are explicit instead of implied by repository write access.
**Depends on**: v9 completed
**Requirements**: [PUB-01, PUB-02, PUB-03]
**Success Criteria** (what must be TRUE):
  1. Skill metadata and catalogs can represent a fully-qualified identity such as `publisher/skill`, plus owners and maintainers.
  2. Validation and release tooling reject namespace claims or transfers that are not authorized by repository policy.
  3. Author, reviewer, releaser, and signer identities are recorded in machine-readable outputs so governance decisions are auditable.
**Plans**: 3 plans

Plans:
- [x] 10-01: Define publisher/namespace metadata schema, migration rules, and compatibility behavior for legacy unqualified skill names
- [x] 10-02: Enforce namespace ownership plus actor-role recording in validation, promotion, and release tooling
- [x] 10-03: Export fully-qualified identities in catalogs, install manifests, and user-facing docs/CLI output

#### ✅ Phase 2: Signing Bootstrap and Operator Doctoring
**Goal**: Make the first trusted-signer setup repeatable, diagnosable, and safe for maintainers who are not already signing experts.
**Depends on**: Phase 1
**Requirements**: [OPS-01, OPS-02]
**Success Criteria** (what must be TRUE):
  1. Maintainers can initialize signer material or wire existing signer identities into repository policy with documented, scripted steps.
  2. Doctor/diagnostic tooling explains exactly why tag signing or attestation verification is blocked and how to fix it.
  3. A first stable release rehearsal can be completed without manual spelunking through repo internals.
**Plans**: 3 plans

Plans:
- [x] 10-04: Add signing bootstrap helpers and docs for `allowed_signers`, SSH signing, and first stable tag flow
- [x] 10-05: Add doctor-style diagnostics for signer state, tag signing readiness, and attestation verification prerequisites
- [x] 10-06: Write and test an end-to-end bootstrap rehearsal for the first trusted stable release

#### ✅ Phase 3: Verified Artifact Format and Distribution Manifest
**Goal**: Promote release output from ad-hoc repository state into a versioned, immutable distribution unit with manifest, digest, and attached verification material.
**Depends on**: Phase 2
**Requirements**: [DIST-01, DIST-02, DIST-03]
**Success Criteria** (what must be TRUE):
  1. Stable releases emit a manifest that identifies the artifact, its digests, source snapshot, attestation bundle, and dependency context.
  2. Install and sync can consume the distribution manifest instead of inferring everything from working-tree layout.
  3. Historical installs and verification resolve immutable release artifacts, not just whichever files are currently checked out.
**Plans**: 3 plans

Plans:
- [x] 10-07: Define stable skill bundle / manifest format plus catalog references to digests and attestation payloads
- [x] 10-08: Teach install/sync flows to fetch and verify distribution manifests before mutating target directories
- [x] 10-09: Document historical install and rollback behavior against immutable release artifacts

#### Phase 4: CI-native Attestations and Verification
**Goal**: Add CI-generated provenance and attestation paths so release trust can be established from both local and automated workflows.
**Depends on**: Phase 3
**Requirements**: [CI-ATT-01, CI-ATT-02]
**Success Criteria** (what must be TRUE):
  1. CI can emit provenance/attestation records that bind artifact digests to workflow identity, commit SHA, and release metadata.
  2. Local tooling can verify both repository-managed SSH attestations and CI-native attestations with clear trust policy boundaries.
  3. Release/distribution policy can require one or both attestation paths without ambiguity.
**Plans**: 3 plans

Plans:
- [ ] 10-10: Add CI workflow(s) that generate signed build provenance for release artifacts
- [ ] 10-11: Extend verification tooling and policy config for CI-native attestation trust decisions
- [ ] 10-12: Document offline/online verification flows and compatibility with the existing SSH-based path

#### Phase 5: Search, Discovery, and Consumer UX
**Goal**: Make the registry easier to consume by adding structured discovery, inspectability, and better explanations of install and policy decisions.
**Depends on**: Phase 4
**Requirements**: [UX-01, UX-02, UX-03]
**Success Criteria** (what must be TRUE):
  1. Maintainers and agents can search/filter skills by tags, compatibility, publisher, and status without scraping raw metadata.
  2. Install and upgrade flows can explain what will change, why a skill was chosen, and why a policy block occurred.
  3. Registry consumers can inspect a skill's compatibility, dependency plan, release provenance, and trust status through stable CLI output.
**Plans**: 3 plans

Plans:
- [ ] 10-13: Add search/inspect command(s) and catalog fields for tags, compatibility, publisher, and trust state
- [ ] 10-14: Add explain-style output for install plans, upgrade choices, and policy rejections
- [ ] 10-15: Update docs and release notes so the verified distribution path is the default consumer experience

### 🗂️ v11 Policy-as-Code and Organizational Controls (Planned)

**Milestone Goal:** Extend the private registry from single-maintainer governance into explainable, team-oriented policy enforcement with federation-ready controls.

#### Phase 1: Policy Packs and Explainable Decisions
**Goal**: Move repository policy toward reusable, inspectable policy packs with explicit decision traces.
**Depends on**: v10 completed
**Requirements**: [POL-01, POL-02]
**Success Criteria** (what must be TRUE):
  1. Reusable policy bundles can describe reviewer, release, install, and distribution requirements without hardcoding every rule into scripts.
  2. Tooling can emit explainable decision traces for policy allow/deny outcomes.
  3. Policy changes remain Git-reviewable and deterministic in local and CI execution.
**Plans**: 2 plans

Plans:
- [ ] 11-01: Define policy-pack structure plus repository-level loading/override rules
- [ ] 11-02: Add explain/debug output for policy evaluation across validation, promotion, and release flows

#### Phase 2: Multi-Team Governance and Exceptions
**Goal**: Support team-level ownership, delegated approval scopes, and explicit break-glass exceptions without weakening auditability.
**Depends on**: Phase 1
**Requirements**: [TEAM-01, TEAM-02, TEAM-03]
**Success Criteria** (what must be TRUE):
  1. Teams or groups can own namespaces and approval scopes without collapsing into a single global maintainer list.
  2. Time-bounded or reviewable exceptions can be granted for urgent releases and clearly recorded.
  3. Audit outputs can reconstruct who approved, who overrode, and why.
**Plans**: 3 plans

Plans:
- [ ] 11-03: Add team/group ownership models and delegated namespace or review policy scopes
- [ ] 11-04: Add break-glass / exception records with expiration and justification fields
- [ ] 11-05: Extend audit exports and release metadata to capture exception usage and delegated approvals

#### Phase 3: Federation, Mirrors, and Audit Export
**Goal**: Prepare the registry for multi-workspace and multi-registry operation without losing trust guarantees or operator visibility.
**Depends on**: Phase 2
**Requirements**: [FED-01, FED-02]
**Success Criteria** (what must be TRUE):
  1. The registry can mirror or federate selected upstream sources while preserving publisher identity, trust policy, and immutable artifact verification.
  2. Consumers can export audit and inventory views suitable for external review or developer portal integration.
  3. Federation rules do not silently bypass local policy or signer trust roots.
**Plans**: 3 plans

Plans:
- [ ] 11-06: Define mirror/federation rules for trusted upstream registries and namespace mapping
- [ ] 11-07: Add audit/inventory export formats for portal, compliance, or reporting integrations
- [ ] 11-08: Document federation trust boundaries, failure modes, and recovery procedures

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Registry Source Policy and Safe Sync | v9 | 3/3 | Completed | 2026-03-08 |
| 2. Dependency Upgrade Planning and Conflict Solver | v9 | 3/3 | Completed | 2026-03-08 |
| 3. Reviewer Groups and Quorum Enforcement | v9 | 3/3 | Completed | 2026-03-09 |
| 4. Signed Release Invariants | v9 | 2/2 | Completed | 2026-03-09 |
| 5. Asymmetric Attestation and Verification | v9 | 3/3 | Completed | 2026-03-09 |
| 1. Publisher / Namespace Model | v10 | 3/3 | Completed | 2026-03-09 |
| 2. Signing Bootstrap and Operator Doctoring | v10 | 3/3 | Completed | 2026-03-09 |
| 3. Verified Artifact Format and Distribution Manifest | v10 | 3/3 | Completed | 2026-03-09 |
| 4. CI-native Attestations and Verification | v10 | 0/3 | Planned | - |
| 5. Search, Discovery, and Consumer UX | v10 | 0/3 | Planned | - |
| 1. Policy Packs and Explainable Decisions | v11 | 0/2 | Planned | - |
| 2. Multi-Team Governance and Exceptions | v11 | 0/3 | Planned | - |
| 3. Federation, Mirrors, and Audit Export | v11 | 0/3 | Planned | - |
