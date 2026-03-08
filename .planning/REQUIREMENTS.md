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

- [ ] **REV-01**: Maintainer can configure reviewer groups and quorum rules by stage or risk level in repository policy files.
- [ ] **REV-02**: Review tooling records decisions only for configured reviewers and computes effective approval from the latest distinct reviewer decisions.
- [ ] **REV-03**: Promotion fails unless required reviewer groups and quorum are satisfied, and blocking rejections are handled explicitly.

### Release Attestation

- [ ] **ATT-01**: Maintainer can create a release only from a clean, synchronized source state with the expected signed tag.
- [ ] **ATT-02**: Release tooling emits provenance or attestation containing exact source commit or tag, registry context, dependency context, and signer identity.
- [ ] **ATT-03**: Maintainer can verify release attestation with asymmetric keys using repository-managed allowed signers before distribution.

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
| REV-01 | Phase 3 | Pending |
| REV-02 | Phase 3 | Pending |
| REV-03 | Phase 3 | Pending |
| ATT-01 | Phase 4 | Pending |
| ATT-02 | Phase 5 | Pending |
| ATT-03 | Phase 5 | Pending |

**Coverage:**
- v9 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-08 after Phase 2 implementation*
