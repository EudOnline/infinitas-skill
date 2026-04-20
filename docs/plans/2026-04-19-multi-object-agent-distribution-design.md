# Multi-Object Agent Distribution Design

Date: 2026-04-19

## Goal

Extend `infinitas-skill` from a skill-only private registry into a shared distribution platform for three first-class object types:

- `skill`
- `agent_code`
- `agent_preset`

The platform must support:

- complete hosted storage for publishable content
- immutable external-source publishing for lightweight GitHub agents
- OpenClaw preset publication for runtime configurations such as `soul`
- install-time memory variants such as `without-memory`, `with-local-memory`, and `with-shared-memory`
- shared discovery, release, exposure, and install flows across all three object types

## Current State And Gap

The repository currently supports two materially different release paths.

The repository-native release path already supports complete bundle storage. `scripts/release-skill.sh` produces deterministic `skill.tar.gz` archives from a full skill directory, writes verified distribution manifests, and updates catalog indexes under `catalog/distributions/...`.

The hosted private-first path does not yet persist complete content. The authoring model stores:

- skill metadata
- `content_ref`
- `metadata_json`
- sealed digests derived from those two values

The hosted release worker currently materializes a bundle containing only a content reference snapshot and metadata snapshot. This is enough for provenance around an immutable reference, but not enough to make the hosted platform the durable home for a full skill, a lightweight agent codebase, or an OpenClaw preset package.

That gap blocks the desired product direction because users need the hosted platform to share:

- full skill bundles
- lightweight agent code bundles
- pure runtime presets that may not have a code repository of their own

## Product Model

The platform should expose three independent installable object types.

### 1. Skill

A `skill` remains a reusable capability package. It is typically directory-shaped and should continue to support full-bundle deterministic release artifacts.

Examples:

- repository operation skills
- workflow guidance skills
- integration skills

### 2. Agent Code

`agent_code` is a lightweight runnable agent implementation, commonly sourced from GitHub or another immutable repository reference.

Examples:

- NanoClaw-style lightweight agents
- simple CLI-driven agent projects
- agent starter repos with one runtime entrypoint

`agent_code` must support both:

- complete hosted bundle storage
- publish-from-immutable-reference workflows

### 3. Agent Preset

`agent_preset` is a runtime configuration object. It captures how an agent should behave, not necessarily the source code that implements the runtime.

Examples:

- OpenClaw `soul`
- prompt and tool policy presets
- model and memory configuration presets

`agent_preset` is the natural object for sharing OpenClaw agents between users and teams.

## Relationship Model

The three object types are peers in the product model, not parent-child special cases.

The allowed dependency relationships are:

- `agent_preset -> agent_code` optional single pinned dependency
- `agent_preset -> skill` zero or more pinned dependencies
- `agent_preset -> memory_profile` optional embedded or referenced configuration
- `agent_code -> skill` optional runtime dependencies when explicitly declared

The install/share entrypoint remains flexible:

- a user may install a `skill` directly
- a user may install an `agent_code` directly
- a user may install an `agent_preset` directly

The highest-value shared object is usually the preset, because it can describe the full runnable experience by pinning code and attached skills.

## Memory Model

Memory must be modeled as a runtime capability, not as hidden state inside agent code.

Each `agent_preset` should declare:

- `memory_mode`: `none | local | shared`
- `memory_profile`: structured configuration for provider, scope, retention, and write policies
- `supported_memory_modes`: which install-time variants are allowed
- `default_memory_mode`: which variant should be presented first

This allows a single preset version to expose install variants such as:

- `without-memory`
- `with-local-memory`
- `with-shared-memory`

The preset payload should store policy and configuration intent, not live memory data.

The platform must not attempt to export or publish actual user memory contents as part of preset sharing.

## Content Storage Model

All three object types should support a shared content abstraction with two modes.

### Inline Bundle

The platform stores the complete publishable content in object storage and can reproduce install bundles from its own durable artifacts.

Recommended default usage:

- `skill`
- `agent_preset`
- some `agent_code`

### External Immutable Reference

The platform stores a verified immutable reference and later materializes a platform-owned release artifact from that source.

Recommended default usage:

- GitHub-hosted lightweight `agent_code`
- advanced repository-backed `skill` or `agent_code` workflows

Hard rule:

Once an object is released, the platform must always produce its own installable immutable bundle plus signed manifest and provenance, even when authoring began from an external immutable reference.

This keeps downstream installation stable and makes shared objects independent from future external repository drift.

## Shared Release Core

Externally, the product surface should remain type-specific:

- `/api/v1/skills`
- `/api/v1/agent-codes`
- `/api/v1/agent-presets`

Internally, the release lifecycle should be unified around a shared core:

- object
- draft
- sealed version
- release
- artifact
- exposure
- discovery/install projection

This avoids copying the current skill release pipeline three times.

## Data Model

The recommended durable model is:

- `registry_objects`
- `object_drafts`
- `object_versions`
- `releases`
- `artifacts`
- `exposures`
- `review_cases`

Plus type-specific extension tables:

- `skill_specs`
- `agent_code_specs`
- `agent_preset_specs`

### Base Object Fields

`registry_objects` should include:

- `id`
- `kind`
- `namespace_id`
- `slug`
- `display_name`
- `summary`
- `status`
- `default_visibility_profile`
- created/updated metadata

### Draft Fields

`object_drafts` should include:

- `object_id`
- `base_version_id`
- `state`
- `content_mode`
- `content_ref`
- `content_artifact_id`
- `metadata_json`
- updated metadata

This is the key hosted-storage fix. The current hosted path only stores `content_ref` and `metadata_json`. The new model adds `content_artifact_id` so complete uploaded content can be stored and sealed.

### Version Fields

`object_versions` should include:

- `object_id`
- `version`
- `content_digest`
- `metadata_digest`
- `sealed_manifest_json`
- `created_from_draft_id`

`sealed_manifest_json` should capture the exact frozen install contract for the version, including pinned dependencies and supported install variants.

### Type Extension Fields

`agent_code_specs` should include:

- runtime family
- language
- entrypoint
- supported launch contract
- optional upstream source repository metadata

`agent_preset_specs` should include:

- runtime family such as `openclaw`
- system prompt and related prompt fields
- model defaults
- tool policy
- pinned `agent_code` dependency
- pinned `skill` dependencies
- memory declarations

## Release Artifact Model

All released objects should emit the same artifact family:

- immutable bundle
- manifest
- provenance
- signature

The bundle contents differ by object type.

### Skill Bundle

Contains the full skill directory.

### Agent Code Bundle

Contains the runnable lightweight agent code tree or equivalent staged package contents.

### Agent Preset Bundle

Contains a structured preset document and any small supporting assets required for installation. This should usually be much smaller than a code bundle.

## Install Model

Installation should be object-aware but pipeline-shared.

### Install Skill

Materialize the skill bundle into the target skill directory and write an install manifest as today.

### Install Agent Code

Materialize the code bundle into the target runtime location and write a runtime-oriented install manifest.

### Install Agent Preset

Resolve the preset's pinned dependencies, then install:

- the preset configuration
- any referenced `agent_code`
- any referenced `skill` dependencies
- the chosen memory variant configuration

The install UI or CLI must explicitly present memory choices when multiple supported variants are available.

## Discovery Model

Discovery indexes should continue to be audience-scoped and install-oriented, but they must become multi-object aware.

Each discovery/install record should include:

- `kind`
- `qualified_name`
- `version`
- object summary
- artifact paths
- compatibility/runtime information
- install variants
- dependency summary

For `agent_preset`, install records should also expose:

- pinned `agent_code`
- attached `skill` set
- supported memory modes
- default memory mode

## Migration Strategy

### Phase 1: Hosted Complete Content Storage

Introduce shared object content artifacts and update the hosted release worker so a hosted release can store and publish complete content, not only reference snapshots.

This phase fixes the existing hosted storage gap and is the minimum foundational change required before new object types are introduced.

### Phase 2: Agent Preset Object Type

Add `agent_preset` support first.

This unlocks the highest-value user outcome:

- share OpenClaw presets such as `soul`
- choose memory variants
- attach skills

This phase does not yet require full GitHub import automation for lightweight agents.

### Phase 3: Agent Code Object Type And External Import

Add `agent_code` support with:

- hosted inline bundle publication
- immutable external reference publication
- GitHub import and freeze workflow

This phase completes the model for NanoClaw-style lightweight agents.

## MVP Recommendation

The smallest product slice that satisfies the new direction is:

1. add hosted complete-content storage for releaseable objects
2. add `agent_preset`
3. support memory variants for presets
4. allow presets to pin attached skills
5. defer automated GitHub import for `agent_code`

This gives users immediate shared OpenClaw preset publishing while minimizing migration risk.

## Risks And Guardrails

### Risk: Accidental Model Explosion

Three product types can lead to duplicated release logic.

Guardrail:

- keep a shared release core
- isolate type-specific fields in extension tables

### Risk: Memory Coupled To Environment

Shared memory backends are environment-specific and can create broken shared installs.

Guardrail:

- publish memory policy and requirements, not live memory data
- make unsupported memory modes fail fast at install time

### Risk: External GitHub Refs Are Not Durable Enough

An upstream repo may disappear or become inaccessible after publishing.

Guardrail:

- require platform-owned immutable release artifacts for every released object
- never install directly from mutable upstream state

### Risk: Preset Dependency Drift

If a preset refers to floating code or skills, installs become non-reproducible.

Guardrail:

- `agent_preset` versions must pin exact dependency versions at seal time

## Success Criteria

The design is successful when:

- hosted publishing can fully store and re-materialize a skill bundle
- OpenClaw presets can be published and shared as first-class objects
- users can choose `without-memory` or `with-memory` install variants for supported presets
- lightweight GitHub agents can eventually be imported without weakening immutability or auditability
- discovery, release, and install stay unified instead of fragmenting into per-type silos
