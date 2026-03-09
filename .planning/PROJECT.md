# infinitas-skill

## What This Is

`infinitas-skill` is a private skill registry and operations toolkit for Claude Code, Codex, and OpenClaw. It keeps private skills, templates, validation scripts, promotion controls, install/sync helpers, and release tooling in one Git-native repository so maintainers can evolve agent skills without turning the registry into an uncontrolled prompt dump.

## Core Value

Maintainers can publish and distribute private skills with deterministic, auditable trust and upgrade behavior.

## Current Milestone: v9 Registry Trust, Quorum, and Attestation

**Goal:** Turn the repository's existing governance intent into enforceable controls for remote registry updates, dependency resolution, reviewer quorum, and release authenticity.

**Target features:**
- Remote registry fetch/update policy with trust, pinning, and drift handling
- Dependency upgrade planning plus deterministic conflict detection/resolution
- Reviewer-group and quorum configuration enforced by tooling
- Asymmetric tag signing and release attestation as release invariants

## Requirements

### Validated

- ✓ Maintainer can scaffold a new skill from templates and place it into the lifecycle directories via `scripts/new-skill.sh` and `templates/*`.
- ✓ Maintainer can validate skill metadata, registry integrity, and promotion policy locally and in CI via `scripts/check-skill.sh`, `scripts/check-all.sh`, and `.github/workflows/validate.yml`.
- ✓ Maintainer can promote approved skills and regenerate install/search catalogs via `scripts/promote-skill.sh` and `scripts/build-catalog.sh`.
- ✓ Maintainer can install, sync, switch, and roll back skills into agent-local directories via `scripts/install-skill.sh`, `scripts/sync-skill.sh`, `scripts/switch-installed-skill.sh`, and `scripts/rollback-installed-skill.sh`.
- ✓ Maintainer can preview a release, verify stable release invariants, create signed tags, and emit immutable release notes/provenance via `scripts/check-release-state.py`, `scripts/release-skill-tag.sh`, `scripts/release-skill.sh`, and `scripts/generate-provenance.py`.

### Active

- [ ] Registry sync respects explicit remote fetch/update policy, trust enforcement, and immutable source selection.
- ✓ Dependency upgrade planning can detect and reject cross-source or cross-version conflicts deterministically.
- [x] Promotion depends on computed reviewer-group quorum instead of mutable review metadata.
- [ ] Releases require asymmetric attestation payloads and repository-managed verification beyond the signed-tag invariant.

### Out of Scope

- Hosted registry service, database, or web UI — v9 hardens the existing file-system and Git-based model.
- Rebuilding the lifecycle, templating, or catalog system from scratch — v9 extends current workflows instead of replacing them.
- Public marketplace/package-manager integration — not needed to deliver private-registry trust goals.
- Full reconstruction of v1-v8 planning history — the repository does not contain authoritative phase-by-phase planning records for those versions.

## Context

- Brownfield GSD initialization started on 2026-03-08 after creating a fresh `.planning/codebase/` map for the existing repository.
- The repository already models a multi-registry world through `config/registry-sources.json`, `scripts/sync-registry-source.sh`, and `scripts/resolve-skill-source.py`, but current trust values are descriptive rather than enforced.
- The current self-registry points at `origin/main`, while local `main` is ahead of `origin/main` by 2 commits; any destructive sync policy must account for local-development semantics before execution work starts.
- Dependency validation exists today (`scripts/check-registry-integrity.py`, `scripts/check-install-target.py`), but deterministic upgrade planning and conflict solving did not exist before v9.
- Review and promotion governance exists today (`scripts/request-review.sh`, `scripts/approve-skill.sh`, `scripts/review-status.py`, `policy/promotion-policy.json`), and Phase 3 made computed review state authoritative.
- Stable release tooling now rejects dirty or out-of-sync repositories, requires a verified signed `skill/<name>/v<version>` tag, and records immutable pushed source snapshots in release output.
- `config/allowed_signers` is still bootstrapped with guidance comments only; maintainers must commit real trusted signer entries before the first actual stable release or Phase 5 attestation verification can succeed.

## Constraints

- **Tech stack**: Keep v9 changes native to Bash, Python, JSON, and Markdown — the repository is already built around lightweight CLI tooling.
- **Compatibility**: Preserve the existing local-filesystem plus Git workflow so current install/sync/promotion commands remain usable.
- **Security**: Shared-secret-only signing is insufficient for release authenticity; asymmetric verification must become the trusted path.
- **Governance**: Reviewer and quorum rules must be repository-configurable so policy changes are versioned and reviewable.
- **History**: GSD planning begins at v9; earlier release history may be referenced, but not reconstructed as authoritative planning data.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Start GSD-managed planning history at v9 with phase numbering from 1 | The repo existed before `.planning/` and does not contain authoritative prior phase plans | — Pending |
| Skip a separate research stage for v9 | The codebase map and repository docs already expose the required problem space for this milestone | ✓ Good |
| Keep the v9 implementation shell/python/json-native | This minimizes migration risk and fits the current execution model | ✓ Good |
| Treat computed quorum and asymmetric attestation as enforcement points, not documentation-only guidance | The highest-risk gaps are governance and authenticity paths that are currently optional or mutable | ✓ Good |
| Make stable release output depend on verified, pushed `skill/<name>/v<version>` tags | Release notes and provenance must resolve against immutable source snapshots instead of best-effort local branch state | ✓ Good |

---
*Last updated: 2026-03-09 after Phase 4 implementation*
