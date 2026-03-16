# Requirements: infinitas-skill

**Defined:** 2026-03-08
**Core Value:** Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.

## v9 Requirements

Requirements committed for milestone `v9`. Each requirement maps to exactly one roadmap phase.

### Registry Sources

- [x] **REG-01**: Maintainer can define per-registry fetch/update policy in repository config, including source pinning mode, trust tier, and allowed update behavior.
- [x] **REG-02**: Registry sync refuses to update a git source when the remote state violates the configured trust or update policy.
- [x] **REG-03**: Resolver and install/sync flows report which registry source and exact commit or tag satisfied the selected skill.

### Dependency Resolution

- [x] **DEP-01**: Maintainer can declare dependency version constraints and source hints for a skill in a machine-validated format.
- [x] **DEP-02**: Validation detects unresolved dependency conflicts, incompatible version requests, and unsafe upgrade plans before promotion or install.
- [x] **DEP-03**: Install or sync operations produce a deterministic dependency resolution plan or fail with actionable conflict details.

### Review Governance

- [x] **REV-01**: Maintainer can configure reviewer groups and quorum rules by stage or risk level in repository policy files.
- [x] **REV-02**: Review tooling records decisions only for configured reviewers and computes effective approval from the latest distinct reviewer decisions.
- [x] **REV-03**: Promotion fails unless required reviewer groups and quorum are satisfied, and blocking rejections are handled explicitly.

### Release Attestation

- [x] **ATT-01**: Maintainer can create a release only from a clean, synchronized source state with the expected signed tag.
- [x] **ATT-02**: Release tooling emits provenance or attestation containing exact source commit or tag, registry context, dependency context, and signer identity.
- [x] **ATT-03**: Maintainer can verify release attestation with asymmetric keys using repository-managed allowed signers before distribution.

## v10 Requirements

Requirements committed for milestone `v10`. Phase 6 is now complete.

### Publisher Identity and Namespace Governance

- [x] **PUB-01**: Skill metadata, dependency refs, and generated catalogs can represent publisher-qualified identities such as `publisher/skill` while preserving legacy unqualified compatibility.
- [x] **PUB-02**: Validation and release checks reject publisher namespace claims or transfers that are not authorized by repository policy.
- [x] **PUB-03**: Machine-readable catalog, install, release-state, and attestation outputs record author, reviewer, releaser, signer, and namespace-governance context for auditability.

### Signing Bootstrap and Operator Doctoring

- [x] **OPS-01**: Maintainer can initialize or reuse an SSH signing key, commit the corresponding public signer entry into `config/allowed_signers`, and wire signer or releaser identities into publisher policy with documented scripted steps.
- [x] **OPS-02**: Maintainer can run doctor diagnostics and a rehearsal regression that explain tag-signing or attestation-verification blockers and validate the first trusted stable release ceremony.

### Verified Artifact Format and Distribution Manifest

- [x] **DIST-01**: Stable releases emit a manifest that identifies the bundle, digests, source snapshot, dependency context, and attestation references for the released skill.
- [x] **DIST-02**: Install and sync operations can consume the immutable distribution manifest instead of inferring release state only from the checked-out working tree.
- [x] **DIST-03**: Historical install, rollback, and verification flows can resolve immutable release artifacts rather than whichever files currently exist in the repository checkout.

### CI-native Attestation and Verification

- [x] **CI-ATT-01**: CI can emit provenance or attestation records that bind artifact digests to workflow identity, commit SHA, ref, and release metadata.
- [x] **CI-ATT-02**: Local tooling can verify repository-managed SSH attestations and CI-native attestations under an explicit trust mode of `ssh`, `ci`, or `both`.

### Search, Discovery, and Consumer UX

- [x] **UX-01**: Maintainers and agents can search and filter skills by tags, compatibility, publisher, and trust state without scraping raw source metadata.
- [x] **UX-02**: Install, update, and upgrade flows explain selection, policy, and version decisions through stable additive output fields.
- [x] **UX-03**: Consumers can inspect compatibility, dependency summaries, provenance references, and distribution-manifest references through stable CLI JSON views.

### Recommendation and Decision Support

- [x] **REC-01**: Maintainers and agents can request a ranked recommendation for a described task, optionally filtered by target agent compatibility, without exposing raw skill source filesystem paths.
- [x] **REC-02**: Recommendation outputs expose machine-readable ranking factors and reasons driven by explicit metadata such as trust state, compatibility, maturity, quality score, and verification freshness.
- [x] **REC-03**: Recommendation flows preserve existing safety constraints, including confirmation requirements for external-only installs and immutable verification requirements for release artifacts.

## v11 Requirements

Requirements committed for milestone `v11`. 11-08 completed the final Phase 3 documentation work on 2026-03-16.

### Policy Packs and Explainable Decisions

- [x] **POL-01**: Reusable policy packs can describe reviewer, release, install, and distribution requirements without hardcoding every rule into a single repository-local file.
- [x] **POL-02**: Repository tooling can load policy packs plus repository-local overrides deterministically so future allow or deny decisions can be traced and explained.

### Multi-Team Governance and Exceptions

- [x] **TEAM-01**: Teams or groups can own namespaces and approval scopes without collapsing into a single global maintainer list.
- [x] **TEAM-02**: Time-bounded or reviewable exceptions can be granted for urgent releases and clearly recorded.
- [x] **TEAM-03**: Audit outputs can reconstruct who approved, who overrode, and why.

### Federation, Mirrors, and Audit Export

- [x] **FED-01**: The registry can mirror or federate selected upstream sources while preserving publisher identity, trust policy, and immutable artifact verification.
- [x] **FED-02**: Consumers can export audit and inventory views suitable for external review or developer-portal integration.

## Future Requirements

### Registry Operations

- **REG-04**: Maintainer can define automatic registry refresh cadence and cache expiry policy.
- **REG-05**: Maintainer can mirror an external registry into an immutable local snapshot for offline resolution.

### Governance Integration

- **REV-04**: Repository can ingest platform-native approvals (for example branch protection or review APIs) as additional quorum evidence.
- **REV-05**: Repository can generate reviewer rotation or escalation suggestions from configured review groups.

### Supply Chain

- **ATT-04**: Repository can publish attestations to an external transparency log.
- **ATT-05**: Release bundles can include full file manifests and reproducible build metadata.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Hosted registry backend or database | The current repository is intentionally Git-native and file-based |
| Web UI for review or release management | v9 focuses on enforcement in CLI workflows, not a new surface area |
| Replacing all symmetric signing paths immediately | Backward compatibility may require a transition period; v9 focuses on making asymmetric verification authoritative |
| Reconstructing detailed milestone artifacts for v1-v8 | There is not enough authoritative historical data in-repo |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REG-01 | Phase 1 | Complete |
| REG-02 | Phase 1 | Complete |
| REG-03 | Phase 1 | Complete |
| DEP-01 | Phase 2 | Complete |
| DEP-02 | Phase 2 | Complete |
| DEP-03 | Phase 2 | Complete |
| REV-01 | Phase 3 | Complete |
| REV-02 | Phase 3 | Complete |
| REV-03 | Phase 3 | Complete |
| ATT-01 | Phase 4 | Complete |
| ATT-02 | Phase 5 | Complete |
| ATT-03 | Phase 5 | Complete |
| PUB-01 | v10 Phase 1 | Complete |
| PUB-02 | v10 Phase 1 | Complete |
| PUB-03 | v10 Phase 1 | Complete |
| OPS-01 | v10 Phase 2 | Complete |
| OPS-02 | v10 Phase 2 | Complete |
| DIST-01 | v10 Phase 3 | Complete |
| DIST-02 | v10 Phase 3 | Complete |
| DIST-03 | v10 Phase 3 | Complete |
| CI-ATT-01 | v10 Phase 4 | Complete |
| CI-ATT-02 | v10 Phase 4 | Complete |
| UX-01 | v10 Phase 5 | Complete |
| UX-02 | v10 Phase 5 | Complete |
| UX-03 | v10 Phase 5 | Complete |
| REC-01 | v10 Phase 6 | Complete |
| REC-02 | v10 Phase 6 | Complete |
| REC-03 | v10 Phase 6 | Complete |
| POL-01 | v11 Phase 1 | Complete |
| POL-02 | v11 Phase 1 | Complete |
| TEAM-01 | v11 Phase 2 | Complete |
| TEAM-02 | v11 Phase 2 | Complete |
| TEAM-03 | v11 Phase 2 | Complete |
| FED-01 | v11 Phase 3 | Complete |
| FED-02 | v11 Phase 3 | Complete |

**Coverage:**
- v9 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓
- v10 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓
- v11 requirements: 7 total
- Mapped to phases: 7
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-16 after 11-08 federation trust boundary documentation completion*
