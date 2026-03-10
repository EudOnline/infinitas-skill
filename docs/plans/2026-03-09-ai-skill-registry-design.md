# AI-First Private Skill Registry Design

Date: 2026-03-09

## Goal

Design `infinitas-skill` as a **private, self-use, AI-first skill registry** with a very high operational standard.

The system should optimize for four properties:

1. **Deterministic publishing**: a published skill version must be immutable, auditable, and reproducible.
2. **Deterministic pulling**: AI must install from verified release artifacts, never from mutable working-tree state.
3. **AI-readable contracts**: AI should not infer workflow from scattered repo internals; it should follow short, explicit machine-facing docs and indexes.
4. **Dual-mode execution**: both human-confirmed and autonomous execution are supported, but the default mode is fully automatic.

## External reference patterns

This design borrows the strongest ideas from adjacent projects without copying their unnecessary complexity.

- **ClawHub / OpenClaw**: versioned skill bundles, install/update/sync workflow, registry-style skill discovery, and strong emphasis on `SKILL.md` as the runtime entrypoint.
- **OpenSkills**: Git-backed skill distribution and agent-friendly skill layout.
- **Agent Skills CLI**: unified installation workflow across multiple agents.

Relevant references:

- [ClawHub documentation](https://docs.openclaw.ai/tools/clawhub)
- [OpenClaw skills documentation](https://docs.openclaw.ai/tools/skills)
- [ClawHub repository](https://github.com/openclaw/clawhub)
- [OpenSkills repository](https://github.com/numman-ali/openskills)
- [Agent Skills CLI documentation](https://www.agentskills.in/docs)

## Core design decision

The recommended architecture is:

**Private Git source + immutable release artifacts + AI protocol index**

This means:

- Git remains the authoring and governance source of truth.
- Every installable version must be materialized as immutable distribution artifacts.
- AI reads a dedicated install protocol surface instead of reconstructing behavior from scripts and governance metadata.

Rejected alternatives:

- **Direct install from `skills/active`**: too ambiguous and not reproducible.
- **Install fallback to mutable source when release artifacts are missing**: convenient, but unsafe for autonomous AI.
- **Separate hosted registry service**: too heavy for a private self-use project.

## Architectural layers

The project should be treated as four layers with clear responsibilities:

### 1. Source layer

Human authors edit skills, templates, policy, schemas, and scripts inside the repo. This layer is mutable and optimized for iteration.

### 2. Release layer

Publishing converts one skill version into immutable artifacts:

- release bundle
- release manifest
- attestation
- cryptographic digest
- indexed release metadata

This layer is optimized for reproducibility and auditability.

### 3. Discovery layer

The registry exports short, stable machine-readable indexes. Governance indexes and AI execution indexes are different views over the same underlying facts.

### 4. Consumption layer

AI resolves a skill version from the AI index, verifies the release artifacts, and installs locally. It never installs directly from mutable source directories.

## AI execution model

The registry supports both:

- **autonomous mode**
- **confirmation mode**

But the default is **autonomous mode**.

That means every public AI-facing operation must be explicit enough to run without human interpretation. Ambiguous defaults should be eliminated from the AI interface even if they remain available to human maintainers internally.

## Publish contract

AI should interact with publishing through one thin entrypoint:

```bash
scripts/publish-skill.sh <skill> [--version <semver>] [--mode auto|confirm]
```

Default mode is `auto`.

Publishing is defined as an atomic state transition from editable source to installable release artifact set.

Required ordered stages:

1. resolve target skill
2. validate skill structure and metadata
3. validate version and changelog intent
4. validate review gate / promotion gate
5. create or verify release tag
6. generate bundle and manifest
7. generate and verify attestation
8. update catalogs and AI index
9. emit structured publish result

Hard rules:

- If any step fails, publish stops immediately.
- No manifest + no attestation means **not published**.
- Catalog updates must not happen before artifact verification succeeds.
- A partially generated release must not be advertised as installable.

Recommended structured result fields:

- `ok`
- `skill`
- `qualified_name`
- `version`
- `state`
- `manifest_path`
- `bundle_path`
- `bundle_sha256`
- `attestation_path`
- `published_at`
- `next_step`

## Pull contract

AI should interact with installation through one thin entrypoint:

```bash
scripts/pull-skill.sh <qualified-name> <target-dir> [--version <semver>] [--mode auto|confirm]
```

Default mode is `auto`.

Pulling is defined as an atomic transition from indexed release metadata to a verified local installation.

Required ordered stages:

1. read AI index
2. resolve requested skill
3. select version
4. verify manifest
5. verify bundle digest
6. verify attestation
7. check compatibility and prerequisites
8. materialize into a temporary location
9. atomically install into target directory
10. write local lock/install manifest
11. emit structured install result

Hard rules:

- AI must not install from `skills/active` or `skills/incubating`.
- If a requested version is absent from the AI index, installation fails.
- Verification failure is terminal.
- Existing installs must not be silently overwritten.
- Temporary files must not be mistaken for successful install state.

Recommended structured result fields:

- `ok`
- `qualified_name`
- `requested_version`
- `resolved_version`
- `target_dir`
- `state`
- `lockfile_path`
- `installed_files_manifest`
- `next_step`

## AI-specific index

Add a dedicated machine-facing index:

`catalog/ai-index.json`

This should be separate from governance-heavy exports such as `catalog/catalog.json`.

Top-level fields:

- `schema_version`
- `generated_at`
- `registry`
- `install_policy`
- `skills`

Recommended `install_policy`:

```json
{
  "mode": "immutable-only",
  "direct_source_install_allowed": false,
  "require_attestation": true,
  "require_sha256": true
}
```

Each skill should include:

- `name`
- `publisher`
- `qualified_name`
- `summary`
- `use_when`
- `avoid_when`
- `agent_compatible`
- `default_install_version`
- `latest_version`
- `available_versions`
- `entrypoints.skill_md`
- `requires.tools`
- `requires.env`
- `versions`

Each version entry should include:

- `manifest_path`
- `bundle_path`
- `bundle_sha256`
- `attestation_path`
- `published_at`
- `stability`
- `installable`
- `resolution.preferred_source = distribution-manifest`
- `resolution.fallback_allowed = false`

## Schema intent

Add a dedicated schema:

`schemas/ai-index.schema.json`

Its purpose is not to mirror every governance field. Its purpose is to validate the minimum set of fields AI requires to make safe install decisions without inference.

The schema should enforce these non-negotiable invariants:

- install policy is immutable-only
- source installs are forbidden
- every listed installable version has manifest, bundle digest, and attestation references
- `default_install_version` must exist in `available_versions`
- every `available_version` must exist in `versions`

## State machines and failure semantics

### Publish state machine

`resolved -> validated -> reviewed -> versioned -> tagged -> bundled -> attested -> indexed -> published`

Any failure transitions to:

`failed`

with a required `failed_at_step` field.

### Pull state machine

`resolved -> selected_version -> verified_manifest -> verified_bundle -> checked_requirements -> materialized -> locked -> installed`

Any failure transitions to:

`failed`

with a required `failed_at_step` field.

Both flows should use structured error codes and actionable next steps rather than free-form success/failure text.

## Documentation required for AI

Add dedicated protocol docs:

- `docs/ai/publish.md`
- `docs/ai/pull.md`

These files should tell AI exactly:

- what the command means
- its allowed inputs
- its default behavior
- required preconditions
- step ordering
- stop conditions
- output format
- prohibited assumptions

These docs should be shorter and more protocol-like than the human-oriented README.

## Recommended repository additions

Add:

- `docs/ai/publish.md`
- `docs/ai/pull.md`
- `catalog/ai-index.json`
- `schemas/ai-index.schema.json`
- `scripts/publish-skill.sh`
- `scripts/pull-skill.sh`

Recommended near-term follow-up improvements:

1. make Python runtime requirements explicit in the repo root
2. keep generated catalog outputs free of machine-specific path noise where possible
3. ensure local verification and CI use the same documented runtime assumptions
4. publish at least 1-3 real skills to validate the release/install protocol end to end

## Final recommendation

For this project, the highest-standard design is:

- **Git for authoring**
- **immutable release artifacts for installation**
- **a dedicated AI execution contract for publish and pull**
- **autonomous by default, but still confirmable when needed**

This keeps the system private and lightweight while still meeting the standards of a serious package/registry workflow.
