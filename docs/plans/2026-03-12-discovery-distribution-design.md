# Agent-First Discovery and Distribution Design

Date: 2026-03-12

## Goal

Design the next stage of `infinitas-skill` so it becomes easier for multiple agents to:

1. discover installable skills by name
2. install skills from a personal private registry without reading internal governance details
3. fall back to configured external registries safely when the private registry does not have a match
4. track where an installed skill came from and whether a newer stable version exists
5. gradually improve skill-selection quality without turning the project into a public hosted marketplace

The project should remain optimized for **personal use**, **private control**, and **multi-agent interoperability**.

## User-validated product decisions

This design reflects the following product choices validated during brainstorming:

- **Primary priority:** improve installation and sync behavior first
- **Primary UX:** install by skill name
- **Registry resolution order:** private registry first, configured registries second
- **External match policy:** if a match only exists in an external registry, show candidates and require confirmation before installation
- **Version policy:** first install resolves to an exact immutable version; the install remembers its source so later update checks are easy
- **Primary caller:** both humans and agents, but the interface should prioritize machine-readable outputs for agents

## Problem statement

The current platform is strong at governance, immutable release artifacts, and AI-readable publish/pull contracts. It is weaker at the user-facing and agent-facing layer between “I need a skill” and “a verified version is now installed”.

Today, the repository already supports:

- publishing immutable artifacts
- pulling a released skill into a runtime directory
- syncing configured registries
- exporting OpenClaw-compatible folders

However, it still expects too much prior knowledge from the caller:

- the caller must often already know the exact skill identity
- discovery is spread across multiple generated files
- external-registry fallback is not yet a first-class install workflow
- installed copies do not yet serve as a rich source of upgrade intent and source history

For multi-agent personal use, this creates friction. Agents should not have to reverse-engineer policy docs or compose multiple internal commands just to answer a simple request like “install the spreadsheet skill”.

## Core design decision

The recommended architecture is:

**Keep the current immutable release model, but add a thin name-resolution and discovery layer above it.**

This means:

- `publish` and exact-version `pull` remain the trusted low-level substrate
- a new resolver maps human-friendly names to installable immutable releases
- discovery becomes a generated, machine-facing view rather than a human-only documentation exercise
- installed state becomes source-aware so later update checks and upgrades are deterministic

Rejected alternatives:

- **Build a hosted registry service now:** too heavy for a personal private project
- **Allow direct installs from mutable source for convenience:** breaks the current trust model
- **Make external fallback fully automatic:** too risky when names collide across registries
- **Jump straight to full recommendation/search intelligence before fixing install UX:** wrong sequencing for current needs

## Product principles

The next distribution layer should optimize for these principles:

### 1. By-name install must feel simple

A caller should be able to ask for a skill by a short name whenever possible.

### 2. Trust boundaries must remain explicit

The private registry is the default trust domain. External registry results are useful, but they must be surfaced as candidates rather than silently treated as equivalent.

### 3. Immutable release artifacts remain the only stable install source

Name-based convenience must not weaken the existing immutable-only install model.

### 4. Agent interfaces should be contract-shaped

Commands should emit structured JSON with stable fields so different agents can reliably consume the same workflow.

### 5. Selection quality should grow from metadata, not heuristics alone

Long-term recommendation quality should come from explicit skill metadata and verification history, not only fuzzy matching.

## Recommended architectural layers

The platform should now be thought of as five layers:

### 1. Source layer

Human authors and agents create or edit skills inside the repo under the existing governance model.

### 2. Release layer

Published versions become immutable bundles, manifests, digests, and attestations.

### 3. Local registry index layer

This layer exports machine-readable indexes derived from the current registry only, including installable versions and compatibility metadata.

### 4. Federated discovery layer

This layer merges the local registry’s install metadata with already-synced metadata from configured external registries and presents a normalized search and resolution surface.

### 5. Consumption layer

Humans and agents resolve a skill name, inspect any ambiguous matches, install an immutable version, and later check for updates or upgrade from the recorded source.

## Command model

The current exact install path should remain stable, but the platform should add a higher-level command surface above it.

### Existing stable substrate

Keep these existing responsibilities:

- `scripts/publish-skill.sh`: publish a skill into immutable release artifacts
- `scripts/pull-skill.sh`: install a released immutable version into a target directory
- `scripts/sync-registry-source.sh` and `scripts/sync-all-registries.sh`: refresh configured external registry caches

### New recommended commands

Add these machine-facing entrypoints:

#### 1. Resolve a requested skill name

```bash
scripts/resolve-skill.sh <name> [--target-agent <agent>] [--mode auto|confirm]
```

Responsibilities:

1. read the local discovery index
2. search the private registry first
3. fall back to synced external registries only if the private registry has no suitable match
4. rank candidates
5. return a structured resolution result

#### 2. Install by name

```bash
scripts/install-by-name.sh <name> <target-dir> [--target-agent <agent>] [--version <semver>] [--mode auto|confirm]
```

Responsibilities:

1. resolve the requested name
2. require explicit confirmation if only external matches are found or if multiple matches remain
3. call the existing immutable install path
4. write a richer local install manifest
5. emit a structured install result

#### 3. Check for updates

```bash
scripts/check-skill-update.sh <installed-name> <target-dir> [--mode auto|confirm]
```

Responsibilities:

1. read the local install manifest
2. re-check the original source registry
3. compare installed exact version to the latest installable stable version
4. return a non-mutating result describing whether an upgrade is available

#### 4. Upgrade an installed skill

```bash
scripts/upgrade-skill.sh <installed-name> <target-dir> [--to-version <semver>] [--mode auto|confirm]
```

Responsibilities:

1. read the original install source from the manifest
2. resolve the requested upgrade target
3. verify the new immutable release artifacts
4. perform an atomic upgrade
5. record the new installed state

## Why new commands are better than overloading `pull-skill.sh`

The current `pull` contract already has a clean meaning: install a released immutable skill once the identity is known. That contract should stay narrow and dependable.

Adding a separate resolver and a separate by-name installer keeps responsibilities clear:

- `pull` remains a low-level exact installer
- `resolve` answers discovery questions
- `install-by-name` offers convenience without changing the trust model
- `check-update` and `upgrade` make source-aware evolution explicit

This separation reduces accidental contract drift and keeps the AI-facing surface understandable.

## Discovery model

Discovery should be implemented as a generated machine-facing layer, not as a hosted search service.

### New generated index

Add a new normalized index:

`catalog/discovery-index.json`

This file should aggregate:

- installable entries from the local registry
- already-synced metadata from configured external registries
- normalized candidate fields needed for by-name resolution and lightweight search

The file should be generated locally from cached registry metadata so results stay deterministic and fast.

### Suggested top-level fields

- `schema_version`
- `generated_at`
- `default_registry`
- `sources`
- `resolution_policy`
- `skills`

### Suggested per-skill fields

- `name`
- `qualified_name`
- `publisher`
- `summary`
- `source_registry`
- `source_priority`
- `match_names`
- `latest_version`
- `default_install_version`
- `available_versions`
- `agent_compatible`
- `maturity`
- `trust_level`
- `quality_score`
- `last_verified_at`
- `install_requires_confirmation`
- `use_when`
- `avoid_when`
- `capabilities`

Not every field must be introduced on day one. The minimum viable set should support name resolution and installation safety first.

## Resolution policy

The install resolver should follow this policy exactly:

### Step 1: Search the private registry first

If the private registry has:

- **one clear match**: resolve it directly
- **multiple plausible matches**: return candidates and require confirmation
- **no suitable match**: continue to external registry caches

### Step 2: Search synced external registries

If external registries have:

- **one clear match**: return it as a candidate that requires confirmation before installation
- **multiple matches**: return ranked candidates and require confirmation
- **no matches**: return a clear not-found result

### Step 3: Rank candidates deterministically

Recommended ranking order:

1. private registry over external registry
2. exact name match over alias match
3. agent-compatible entries over non-compatible entries
4. higher maturity and quality over lower maturity and quality
5. more recently verified entries over stale entries

### Hard rules

- A private-registry match should outrank an external-registry match with the same short name.
- An external-registry-only result should never auto-install without confirmation.
- Name resolution must not silently fall back to mutable source directories.
- Ambiguous results must remain explicit in `confirm` mode.

## Install manifest evolution

The local install manifest should become a first-class contract for source-aware evolution.

Each installed skill should record at minimum:

- `schema_version`
- `name`
- `qualified_name`
- `source_registry`
- `installed_version`
- `resolved_release_digest`
- `installed_at`
- `last_checked_at`
- `install_target`
- `target_agent`
- `install_mode`

Recommended additional fields:

- `publisher`
- `source_registry_ref`
- `default_upgrade_channel`
- `last_available_version`
- `previous_installed_versions`

This enables any agent to answer:

- what is installed here
- where it came from
- which exact immutable version is present
- whether a newer stable version exists in the same source
- what changed after an upgrade

## Agent-facing result schemas

The new commands should return small, stable JSON payloads.

### `resolve-skill.sh` result

Recommended fields:

- `ok`
- `query`
- `state`
- `resolved`
- `candidates`
- `source_used`
- `requires_confirmation`
- `recommended_next_step`

Possible `state` values:

- `resolved-private`
- `resolved-external`
- `ambiguous`
- `not-found`
- `incompatible`

### `install-by-name.sh` result

Recommended fields:

- `ok`
- `query`
- `qualified_name`
- `source_registry`
- `requested_version`
- `resolved_version`
- `target_dir`
- `manifest_path`
- `state`
- `requires_confirmation`
- `next_step`

### `check-skill-update.sh` result

Recommended fields:

- `ok`
- `qualified_name`
- `source_registry`
- `installed_version`
- `latest_available_version`
- `update_available`
- `state`
- `next_step`

### `upgrade-skill.sh` result

Recommended fields:

- `ok`
- `qualified_name`
- `source_registry`
- `from_version`
- `to_version`
- `target_dir`
- `state`
- `manifest_path`
- `next_step`

## Selection-quality follow-on

Although the immediate priority is distribution, the discovery layer should be designed so recommendation quality can improve without major rework.

That means the metadata model should gradually grow toward explicit selection fields:

- `use_when`
- `avoid_when`
- `capabilities`
- `inputs`
- `side_effects`
- `trust_level`
- `maturity`
- `quality_score`
- `last_verified_at`

This creates a clean path to future commands such as:

```bash
scripts/search-skills.sh <query> [--target-agent <agent>]
scripts/recommend-skill.sh <task-description> [--target-agent <agent>]
```

The key idea is sequencing: first fix install and upgrade UX, then make recommendations smarter using explicit metadata and verification history.

## Error handling model

Error behavior should remain strict and explicit.

### Resolution errors

- missing query → fail with structured usage error
- no matching skill → return `not-found`
- ambiguous candidates → return `ambiguous` and never guess silently
- incompatible agent target → return `incompatible`

### External-source safety errors

- external candidate found but confirmation not granted → stop with `confirmation-required`
- stale or missing external cache → return `external-cache-unavailable`
- source registry disabled by policy → return `source-disabled`

### Install and upgrade errors

- requested version not installable → fail before mutation
- digest or attestation verification failure → fail before mutation
- target directory collision → fail without partial overwrite
- manifest write failure after install staging → roll back staged install and report failure

## Testing strategy

This design should be validated with focused regression coverage before broadening behavior.

### Resolver tests

Add tests for:

- private-only exact match
- private-registry ambiguity
- external-only match requiring confirmation
- same-name private and external match where private wins
- agent compatibility filtering
- deterministic candidate ordering

### Install-by-name tests

Add tests for:

- successful private-registry install by short name
- refusal to auto-install an external-only result
- confirm-mode output for ambiguous results
- install manifest recording source registry and exact version

### Update and upgrade tests

Add tests for:

- no-update case
- newer stable version available in same source
- explicit upgrade to a requested version
- refusal to upgrade across source registries silently
- rollback behavior when upgrade verification fails

### Catalog and cache tests

Add tests for:

- discovery-index generation from local registry only
- discovery-index generation from local plus synced registry caches
- handling of missing or malformed external cache data
- schema-version compatibility for new manifest fields

## Non-goals

This design intentionally does not do the following in the first phase:

- build a hosted public registry service
- replace `catalog/ai-index.json` as the authoritative install index for the local registry
- allow direct installation from mutable `skills/active/` or `skills/incubating/`
- auto-install external matches without confirmation
- introduce workspace-wide profile sync or `skills.lock` as the main workflow
- redesign `SKILL.md` runtime semantics

## Delivery phases

### Phase 1: By-name install foundation

Focus on the shortest path to better multi-agent distribution.

Deliver:

- `resolve-skill.sh`
- `install-by-name.sh`
- `catalog/discovery-index.json`
- source-aware install manifest fields
- regression tests for private-first resolution and external confirmation behavior

Success criteria:

- a caller can request a skill by short name
- a private-registry match installs cleanly from immutable artifacts
- an external-only match returns candidates and requires confirmation
- the resulting install records source and exact version

### Phase 2: Source-aware updates and upgrades

Deliver:

- `check-skill-update.sh`
- `upgrade-skill.sh`
- richer manifest history fields
- update/upgrade regression coverage

Success criteria:

- any agent can inspect an installed skill and determine whether an update exists
- upgrades happen from the recorded source only unless the caller explicitly chooses otherwise
- failed upgrades do not leave partial install state behind

### Phase 3: Better discovery and recommendation

Deliver:

- richer metadata fields for skill selection
- `search-skills.sh`
- `recommend-skill.sh`
- ranking logic that incorporates compatibility, trust, maturity, and verification freshness

Success criteria:

- agents can discover candidate skills without reading governance docs
- agents can justify why a skill was recommended
- private skills still outrank equivalent public candidates by default

## Recommendation

For the current stage of the project, the best next move is:

**Do not build a ClawHub clone. Build a private-first install and discovery layer on top of the existing immutable registry core.**

That gives the project the missing convenience of “install by name” while preserving the properties that already make the platform valuable:

- deterministic installs
- explicit trust boundaries
- machine-readable AI contracts
- safe multi-agent reuse and evolution

In practical terms, the recommended execution order is:

1. by-name install
2. check-update and upgrade
3. search and recommendation

That order improves real daily usability first and lets selection intelligence grow from a stable foundation.
