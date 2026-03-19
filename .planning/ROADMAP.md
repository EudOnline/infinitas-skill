# Roadmap: infinitas-skill

## Milestones

- ✅ **v9 Registry Trust, Quorum, and Attestation** - Phases 1-5 (completed 2026-03-09)
- ✅ **v10 Publisher Identity and Verified Distribution** - Phases 1-6 (completed 2026-03-15)
- ✅ **v11 Policy-as-Code and Organizational Controls** - Phases 1-3 (completed 2026-03-16)
- ✅ **v12 AI-Usable Skill Ecosystem** - Phases 1-3 (completed 2026-03-16)
- ✅ **v13 Registry Operations and Snapshot Mirroring** - Phases 1-2 (completed 2026-03-17)
- ✅ **v14 Governance Integration and Reviewer Operations** - Phases 1-2 (completed 2026-03-17)
- ✅ **v15 Supply-Chain Transparency and Reproducible Release Metadata** - Phases 1-2 (completed 2026-03-17)
- ✅ **v16 Installed Skill Integrity and Repairable Consumption** - Phases 1-2 (completed 2026-03-18)

## Current Follow-up

- The signer-readiness closeout is now merged on `main`; repository-level signer reporting and steady-state operations guidance are part of the baseline.
- v13 registry-operations work is now merged on `main`, including freshness-aware refresh policy plus immutable snapshot mirrors for offline resolution.
- v14 governance integration is now merged on `main`, including additive platform-native review evidence and reviewer recommendation plus escalation flows.
- v15 supply-chain work is now merged on `main`, including signed released-file inventories, reproducibility metadata, transparency-log publication, and additive audit surfaces.
- v16 is now merged on `main`, including installed-runtime verification against signed release-file inventories, additive integrity summaries in install manifests, exact-source repair, and drift-aware mutation guardrails.
- Older hosted distribution manifests can still lack signed `file_manifest` metadata; install-time integrity now degrades to `unknown` for compatibility, while explicit verification remains strict.
- No post-v16 milestone is committed yet; the next planning slice should stay adjacent to installed-runtime trust and compatibility instead of broadening into hosted-service scope.

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

### ✅ v10 Publisher Identity and Verified Distribution (Completed)

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

#### ✅ Phase 4: CI-native Attestations and Verification
**Goal**: Add CI-generated provenance and attestation paths so release trust can be established from both local and automated workflows.
**Depends on**: Phase 3
**Requirements**: [CI-ATT-01, CI-ATT-02]
**Success Criteria** (what must be TRUE):
  1. CI can emit provenance/attestation records that bind artifact digests to workflow identity, commit SHA, and release metadata.
  2. Local tooling can verify both repository-managed SSH attestations and CI-native attestations with clear trust policy boundaries.
  3. Release/distribution policy can require one or both attestation paths without ambiguity.
**Plans**: 3 plans

Plans:
- [x] 10-10: Add CI workflow(s) that generate signed build provenance for release artifacts
- [x] 10-11: Extend verification tooling and policy config for CI-native attestation trust decisions
- [x] 10-12: Document offline/online verification flows and compatibility with the existing SSH-based path

#### ✅ Phase 5: Search, Discovery, and Consumer UX
**Goal**: Make the registry easier to consume by adding structured discovery, inspectability, and better explanations of install and policy decisions.
**Depends on**: Phase 4
**Requirements**: [UX-01, UX-02, UX-03]
**Success Criteria** (what must be TRUE):
  1. Maintainers and agents can search/filter skills by tags, compatibility, publisher, and status without scraping raw metadata.
  2. Install and upgrade flows can explain what will change, why a skill was chosen, and why a policy block occurred.
  3. Registry consumers can inspect a skill's compatibility, dependency plan, release provenance, and trust status through stable CLI output.
**Plans**: 3 plans

Plans:
- [x] 10-13: Add search/inspect command(s) and catalog fields for tags, compatibility, publisher, and trust state
- [x] 10-14: Add explain-style output for install plans, upgrade choices, and policy rejections
- [x] 10-15: Update docs and release notes so the verified distribution path is the default consumer experience

#### ✅ Phase 6: Recommendation and Decision Support
**Goal**: Add an AI-usable recommendation layer that can rank and justify skill choices using explicit metadata, compatibility evidence, trust state, and verification freshness.
**Depends on**: Phase 5
**Requirements**: [REC-01, REC-02, REC-03]
**Success Criteria** (what must be TRUE):
  1. Maintainers and agents can request deterministic ranked recommendations for a described task without scraping raw metadata or filesystem paths.
  2. Recommendation results expose machine-readable reasons, ranking factors, trust state, compatibility, maturity, quality, and verification freshness.
  3. Recommendation flows preserve existing safety rules such as external-install confirmation and immutable verification requirements, and they are covered by focused plus `check-all` regression tests.
**Plans**: 3 plans

Plans:
- [x] 10-16: Expose recommendation metadata in generated catalogs and discovery surfaces
- [x] 10-17: Add `recommend-skill.sh` plus deterministic ranking and explanation helpers
- [x] 10-18: Document recommendation workflows and wire Phase 6 regression coverage

### ✅ v11 Policy-as-Code and Organizational Controls (Completed)

**Milestone Goal:** Extend the private registry from single-maintainer governance into explainable, team-oriented policy enforcement with federation-ready controls.

#### ✅ Phase 1: Policy Packs and Explainable Decisions (Completed 2026-03-15)
**Goal**: Move repository policy toward reusable, inspectable policy packs with explicit decision traces.
**Depends on**: v10 completed
**Requirements**: [POL-01, POL-02]
**Success Criteria** (what must be TRUE):
  1. Reusable policy bundles can describe reviewer, release, install, and distribution requirements without hardcoding every rule into scripts.
  2. Tooling can emit explainable decision traces for policy allow/deny outcomes.
  3. Policy changes remain Git-reviewable and deterministic in local and CI execution.
**Plans**: 2 plans

Plans:
- [x] 11-01: Define policy-pack structure plus repository-level loading/override rules
- [x] 11-02: Add explain/debug output for policy evaluation across validation, promotion, and release flows

#### ✅ Phase 2: Multi-Team Governance and Exceptions (Completed 2026-03-15)
**Goal**: Support team-level ownership, delegated approval scopes, and explicit break-glass exceptions without weakening auditability.
**Depends on**: Phase 1
**Requirements**: [TEAM-01, TEAM-02, TEAM-03]
**Success Criteria** (what must be TRUE):
  1. Teams or groups can own namespaces and approval scopes without collapsing into a single global maintainer list.
  2. Time-bounded or reviewable exceptions can be granted for urgent releases and clearly recorded.
  3. Audit outputs can reconstruct who approved, who overrode, and why.
**Plans**: 3 plans

Plans:
- [x] 11-03: Add team/group ownership models and delegated namespace or review policy scopes
- [x] 11-04: Add break-glass / exception records with expiration and justification fields
- [x] 11-05: Extend audit exports and release metadata to capture exception usage and delegated approvals

#### ✅ Phase 3: Federation, Mirrors, and Audit Export (Completed 2026-03-16)
**Goal**: Prepare the registry for multi-workspace and multi-registry operation without losing trust guarantees or operator visibility.
**Depends on**: Phase 2
**Requirements**: [FED-01, FED-02]
**Success Criteria** (what must be TRUE):
  1. The registry can mirror or federate selected upstream sources while preserving publisher identity, trust policy, and immutable artifact verification.
  2. Consumers can export audit and inventory views suitable for external review or developer portal integration.
  3. Federation rules do not silently bypass local policy or signer trust roots.
**Plans**: 3 plans

Plans:
- [x] 11-06: Define mirror/federation rules for trusted upstream registries and namespace mapping
- [x] 11-07: Add audit/inventory export formats for portal, compliance, or reporting integrations
- [x] 11-08: Document federation trust boundaries, failure modes, and recovery procedures

### ✅ v12 AI-Usable Skill Ecosystem (Completed 2026-03-16)

**Milestone Goal:** Turn the trustworthy registry core into a small but genuinely useful AI-facing skill ecosystem with canonical decision metadata, schema-stable wrapper contracts, and enough real skills to make ranking meaningful.

#### ✅ Phase 1: Decision Metadata and AI Result Contracts (Completed 2026-03-16)
**Goal**: Make skill-selection metadata and AI wrapper JSON contracts first-class, validated, and exported through canonical indexes instead of hand-maintained or empty defaults.
**Depends on**: v11 completed
**Requirements**: [ECO-01, ECO-02, ECO-03]
**Success Criteria** (what must be TRUE):
  1. Authors can declare `use_when`, `avoid_when`, capabilities, runtime assumptions, and related decision metadata in validated `_meta.json`.
  2. `catalog/ai-index.json` and `catalog/discovery-index.json` surface canonical decision metadata from source records rather than hardcoded empty arrays or ad-hoc defaults.
  3. `publish-skill.sh` and `pull-skill.sh` outputs are backed by dedicated JSON schemas plus regression tests and docs.
**Plans**: 3 plans

Plans:
- [x] 12-01: Extend skill metadata schema, templates, and docs for AI decision fields
- [x] 12-02: Emit canonical decision metadata into AI/discovery indexes and recommendation/search surfaces
- [x] 12-03: Add AI wrapper result schemas and publish/pull contract validation

#### ✅ Phase 2: Real Skill Inventory and Learnability (Completed 2026-03-16)
**Goal**: Add enough real, well-described skills and task-level protocol drills that agents can succeed using the public AI surfaces instead of repo internals.
**Depends on**: Phase 1
**Requirements**: [ECO-04, ECO-05]
**Success Criteria** (what must be TRUE):
  1. The registry contains multiple non-fixture skills with meaningful selection guidance, runtime assumptions, and verified compatibility evidence.
  2. End-to-end publish/pull/search/recommend drills can be completed using AI docs and generated indexes alone.
  3. Failure-path tests cover missing artifacts, wrong versions, and ambiguous names with actionable output.
**Plans**: 3 plans

Plans:
- [x] 12-04: Add real registry skills with explicit runtime assumptions and decision metadata
- [x] 12-05: Add AI-only workflow drills for search, recommend, inspect, publish, and pull
- [x] 12-06: Add failure-path regression coverage for ambiguous resolution and missing immutable artifacts

#### ✅ Phase 3: Comparative Ranking and Usage Guide (Completed 2026-03-16)
**Goal**: Make multi-skill selection explainable by adding stronger comparative signals and a stable usage guide for humans and agents.
**Depends on**: Phase 2
**Requirements**: [ECO-06, ECO-07]
**Success Criteria** (what must be TRUE):
  1. Recommendation outputs can compare multiple eligible skills using explicit quality, confidence, freshness, and compatibility signals.
  2. Decision metadata duplication between author source, generated indexes, and docs is reduced or documented behind one canonical source.
  3. Humans and agents have a stable guide for when to search, recommend, inspect, publish, pull, and verify.
**Plans**: 3 plans

Plans:
- [x] 12-07: Add comparative quality/confidence signals to recommendation outputs
- [x] 12-08: Reduce duplicated decision metadata across source, generated indexes, and docs
- [x] 12-09: Publish the stable platform usage guide for humans and agents

### 🚧 v13 Registry Operations and Snapshot Mirroring

**Milestone Goal:** Make remote registry operation predictable and offline-safe by adding explicit refresh cadence policy, operator-visible freshness status, and immutable snapshot mirrors that resolution and install can trust.

#### ✅ Phase 1: Registry Refresh Cadence and Freshness Policy (Completed 2026-03-17)
**Goal**: Add machine-validated refresh cadence, cache expiry, and stale-cache policy so registry caches are no longer treated as indefinitely valid by convention.
**Depends on**: v12 completed
**Requirements**: [REG-04]
**Success Criteria** (what must be TRUE):
  1. Maintainers can define refresh cadence, max cache age, and stale-cache response policy for remote registries in validated configuration.
  2. Sync and resolver surfaces record or expose freshness age, last successful refresh, and stale reasons for cached registries.
  3. Policy can warn or fail when a registry cache is too old for the requested workflow instead of silently trusting stale data.
**Plans**: 3 plans

Plans:
- [x] 13-01: Define refresh cadence and stale-cache policy schema plus validation defaults
- [x] 13-02: Record registry freshness state and add operator-facing freshness status output
- [x] 13-03: Enforce stale-cache policy in sync, resolution, and documentation flows

#### ✅ Phase 2: Immutable Snapshot Mirrors and Offline Resolution (Completed 2026-03-17)
**Goal**: Let operators materialize immutable snapshots of remote registries and use them for offline or disaster-recovery resolution without weakening trust semantics.
**Depends on**: Phase 1
**Requirements**: [REG-05]
**Success Criteria** (what must be TRUE):
  1. Operators can create immutable local snapshots of an external registry that preserve source identity, trust policy, and refresh metadata.
  2. Resolver, install, and sync can consume a declared snapshot source for offline or recovery workflows without falling back to mutable live state.
  3. Snapshot mirrors remain auditable and non-authoritative by default unless explicitly selected, preserving existing federation and mirror rules.
**Plans**: 3 plans

Plans:
- [x] 13-04: Define immutable registry snapshot format, metadata, and catalog visibility
- [x] 13-05: Add snapshot mirror creation and verification tooling
- [x] 13-06: Teach resolver, install, and sync flows to consume offline registry snapshots

### ✅ v14 Governance Integration and Reviewer Operations (Completed)

**Milestone Goal:** Extend review governance beyond repo-local approvals by ingesting normalized platform-native approval evidence and guiding operators toward the right reviewers when quorum is incomplete.

#### ✅ Phase 1: Platform-Native Approval Evidence (Completed 2026-03-17)
**Goal**: Let maintainers import or mirror normalized approval evidence from external platforms and count it as additive quorum input without weakening Git-native determinism.
**Depends on**: v13 completed
**Requirements**: [REV-04]
**Success Criteria** (what must be TRUE):
  1. Maintainers can define and validate a normalized review-evidence contract for one skill that records reviewer identity, source platform, decision, timestamp, and stable source reference.
  2. Review, promotion, release, and catalog surfaces can count approved imported evidence alongside `reviews.json` while preserving provenance about where each decision came from.
  3. Imported evidence remains additive and auditable: missing or stale platform evidence never silently rewrites repo-local decisions, and unsupported sources fail clearly.
**Plans**: 2 plans

Plans:
- [x] 14-01: Define normalized platform approval evidence format, loader, and policy-safe merge rules
- [x] 14-02: Count imported approval evidence in review quorum plus release/catalog outputs

#### ✅ Phase 2: Reviewer Rotation and Escalation Suggestions (Completed 2026-03-17)
**Goal**: Help operators close review gaps faster by generating deterministic reviewer recommendations and escalation guidance from existing groups, teams, and recent review history.
**Depends on**: Phase 1
**Requirements**: [REV-05]
**Success Criteria** (what must be TRUE):
  1. Operators can ask for reviewer suggestions for one skill and get deterministic results scoped to the missing quorum groups, owner constraints, and configured teams.
  2. Suggestions include escalation guidance when no eligible reviewer is currently available for a required group.
  3. Review-request and review-status workflows can surface or reference those suggestions without introducing a new stateful scheduling service.
**Plans**: 2 plans

Plans:
- [x] 14-03: Define reviewer recommendation and escalation output contract
- [x] 14-04: Surface reviewer guidance in review CLI flows and docs

### ✅ v15 Supply-Chain Transparency and Reproducible Release Metadata (Completed 2026-03-17)

**Milestone Goal:** Make released artifacts independently auditable by extending signed release metadata with full file inventories and reproducibility context, then anchoring those attestations in an external transparency log without weakening local verification.

#### ✅ Phase 1: Reproducible Release Metadata and Full File Manifests (Completed 2026-03-17)
**Goal**: Make signed release artifacts commit to exactly which files were released and under what normalized build context so bundle verification becomes stronger than bundle-digest-only checks.
**Depends on**: v14 completed
**Requirements**: [ATT-05]
**Success Criteria** (what must be TRUE):
  1. Stable provenance and distribution manifests include a deterministic per-file manifest with relative paths, digests, and archived metadata for the released bundle.
  2. Release outputs record normalized build metadata such as tool versions, archive parameters, and reproducibility-relevant environment fields without depending on ephemeral local noise.
  3. Verification fails when the signed file inventory, archived bundle contents, or declared reproducibility metadata diverge.
**Plans**: 2 plans

Plans:
- [x] 15-01: Define signed file-manifest and reproducible-build metadata contract
- [x] 15-02: Thread reproducible release metadata through release, verification, and distribution surfaces

#### ✅ Phase 2: Transparency Log Publication and Verification (Completed 2026-03-17)
**Goal**: Publish release attestations to an external transparency log and retain enough proof metadata in repo-managed artifacts for later verification and policy decisions.
**Depends on**: Phase 1
**Requirements**: [ATT-04]
**Success Criteria** (what must be TRUE):
  1. Maintainers can submit one signed release attestation to a configured transparency log endpoint and capture a stable entry identifier plus inclusion proof reference.
  2. Provenance, release-state, and distribution surfaces preserve transparency publication status and proof metadata without making local verification depend on network access.
  3. Policy can treat transparency publication as advisory or required, with clear operator-facing errors when submission or proof verification fails.
**Plans**: 2 plans

Plans:
- [x] 15-03: Define transparency-log policy and proof-record contract
- [x] 15-04: Add transparency publication, verification, and operator docs

### ✅ v16 Installed Skill Integrity and Repairable Consumption (Completed 2026-03-18)

**Milestone Goal:** Extend the verified-distribution trust model into installed agent runtime directories by comparing local files against signed released-file inventories, then enabling exact-source repair and drift-aware mutation guardrails without weakening offline workflows.

#### ✅ Phase 1: Installed Skill Integrity and Drift Detection (Completed 2026-03-18)
**Goal**: Let operators and agents verify that an installed skill directory still matches the exact immutable artifact that was previously resolved and verified during install.
**Depends on**: v15 completed
**Requirements**: [INST-01]
**Success Criteria** (what must be TRUE):
  1. Operators can run one command against an installed skill and compare local files to the signed `file_manifest` recorded by the immutable distribution source.
  2. Machine-readable output reports clean vs drifted state, including missing, modified, and unexpected relative paths, without depending on network access.
  3. Install-manifest entries and read-only status surfaces preserve additive integrity summaries without breaking compatibility for older manifests.
**Plans**: 2 plans

Plans:
- [x] 16-01: Define installed-skill integrity verification contract and drift report
- [x] 16-02: Persist integrity state in install manifests and consumer status surfaces

#### ✅ Phase 2: Exact-Source Repair and Update Guardrails (Completed 2026-03-18)
**Goal**: Repair drifted installs back to their recorded immutable source and make sync, switch, rollback, and upgrade flows explicitly aware of local trust drift.
**Depends on**: Phase 1
**Requirements**: [INST-02]
**Success Criteria** (what must be TRUE):
  1. Operators can repair a drifted install back to the exact recorded version and source registry using the local install manifest.
  2. Sync, switch, rollback, and upgrade flows warn or fail clearly before overwriting drifted local files unless the caller explicitly forces replacement.
  3. Operator and AI docs explain how to verify, repair, and intentionally override drift while keeping immutable-release semantics intact.
**Plans**: 2 plans

Plans:
- [x] 16-03: Add exact-source repair flow for drifted installs
- [x] 16-04: Thread drift-aware guardrails into sync, rollback, switch, and upgrade commands

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
| 4. CI-native Attestations and Verification | v10 | 3/3 | Completed | 2026-03-14 |
| 5. Search, Discovery, and Consumer UX | v10 | 3/3 | Completed | 2026-03-14 |
| 6. Recommendation and Decision Support | v10 | 3/3 | Completed | 2026-03-15 |
| 1. Policy Packs and Explainable Decisions | v11 | 2/2 | Completed | 2026-03-15 |
| 2. Multi-Team Governance and Exceptions | v11 | 3/3 | Completed | 2026-03-15 |
| 3. Federation, Mirrors, and Audit Export | v11 | 3/3 | Completed | 2026-03-16 |
| 1. Decision Metadata and AI Result Contracts | v12 | 3/3 | Completed | 2026-03-16 |
| 2. Real Skill Inventory and Learnability | v12 | 3/3 | Completed | 2026-03-16 |
| 3. Comparative Ranking and Usage Guide | v12 | 3/3 | Completed | 2026-03-16 |
| 1. Registry Refresh Cadence and Freshness Policy | v13 | 3/3 | Completed | 2026-03-17 |
| 2. Immutable Snapshot Mirrors and Offline Resolution | v13 | 3/3 | Completed | 2026-03-17 |
| 1. Platform-Native Approval Evidence | v14 | 2/2 | Completed | 2026-03-17 |
| 2. Reviewer Rotation and Escalation Suggestions | v14 | 2/2 | Completed | 2026-03-17 |
| 1. Reproducible Release Metadata and Full File Manifests | v15 | 2/2 | Completed | 2026-03-17 |
| 2. Transparency Log Publication and Verification | v15 | 2/2 | Completed | 2026-03-17 |
| 1. Installed Skill Integrity and Drift Detection | v16 | 2/2 | Completed | 2026-03-18 |
| 2. Exact-Source Repair and Update Guardrails | v16 | 2/2 | Completed | 2026-03-18 |
