# Sustainable Triple-Agent Compatibility Design

Date: 2026-03-12

## Goal

Design the next compatibility architecture for `infinitas-skill` so one private registry can sustainably support:

1. Claude
2. Codex
3. OpenClaw / ClawHub

without treating any single platform's packaging format as the universal source of truth.

The design must optimize for:

- long-term maintainability as platform specs evolve
- explicit trust and release boundaries
- minimal duplication of skill content
- machine-checkable compatibility claims
- full OpenClaw / ClawHub export compatibility for release-ready skills

## User-validated design decisions

This design reflects the following decisions already established in discussion:

- The repository should target **Claude, Codex, and OpenClaw simultaneously**.
- Compatibility must be **verified**, not only declared in metadata.
- OpenClaw / ClawHub compatibility must be treated as a **hard requirement** for public-facing exports, not a best-effort bridge.
- The platform contracts for Claude, Codex, and OpenClaw are expected to **continue evolving**, so the architecture must absorb upstream change with minimal churn.
- The current `_meta.json.agent_compatible` approach is not sufficient as the long-term compatibility model.

## Problem statement

The repository currently mixes three different concerns:

1. **registry governance metadata** (`_meta.json`, review state, release state)
2. **runtime skill content** (`SKILL.md`)
3. **platform compatibility claims** (`agent_compatible`)

This is manageable while the repository is primarily OpenClaw-oriented, but it does not scale to true multi-platform support.

The root problem is that the three target platforms do not expose the same stable contract surface:

- **Claude** now documents skills as directories under `.claude/skills`, where commands are implemented as skills and support docs may be loaded on demand.
- **Codex** documents instructions via `AGENTS.md` and documents skills under `.agents/skills` / `~/.agents/skills`, with `SKILL.md` plus optional metadata in `agents/openai.yaml`.
- **OpenClaw / ClawHub** uses a `SKILL.md`-rooted folder model and applies additional publication rules such as OpenClaw metadata, text-only public bundles, and public-license constraints.

If this repository keeps treating one editable runtime folder as the canonical shape for all three, future spec changes will force repeated migrations across every skill.

## External contract snapshot

As of 2026-03-12, the most important platform surfaces are:

### Claude

- Skills live under `.claude/skills` or `~/.claude/skills`.
- Each skill is a directory with `SKILL.md`.
- Commands are implemented as skills.
- Additional supporting Markdown may be loaded via progressive disclosure.

Primary sources:

- <https://docs.anthropic.com/en/docs/claude-code/skills>
- <https://docs.anthropic.com/en/docs/claude-code/slash-commands#custom-slash-commands>
- <https://docs.anthropic.com/en/docs/claude-code/sub-agents#project-subagents>

### Codex

- Repository instructions are layered through `AGENTS.md`.
- Skills live under `.agents/skills` or `~/.agents/skills`.
- Each skill is a directory with `SKILL.md`.
- Optional metadata may be declared in `agents/openai.yaml`.
- Supporting files can be loaded on demand.

Primary source:

- <https://platform.openai.com/docs/codex/overview#agentsmd>
- <https://platform.openai.com/docs/codex/overview#skills>

### OpenClaw / ClawHub

- A skill is a folder rooted by `SKILL.md`.
- OpenClaw metadata is expressed inside skill frontmatter.
- Public publishing imposes bundle constraints such as text-only content and MIT-0.

Primary sources:

- <https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md>
- <https://github.com/openclaw/clawhub/blob/main/README.md>

## Stable vs volatile platform assumptions

The architecture should separate assumptions that are likely to remain stable from those that are likely to change.

| Platform | Stable assumptions | Volatile assumptions |
| --- | --- | --- |
| Claude | skill directory model, `SKILL.md`, on-demand supporting docs, commands/subagents as first-class concepts | marketplace packaging details, plugin distribution UX, exact feature names |
| Codex | `AGENTS.md`, `.agents/skills`, `SKILL.md`, optional `agents/openai.yaml` metadata | bootstrap UX, installation instructions, optional collaborative features |
| OpenClaw | `SKILL.md`-rooted runtime folder, frontmatter metadata, release/export workflow | exact publish CLI flags, registry hosting conventions, optional ecosystem metadata |

This distinction is foundational: **stable assumptions may shape the canonical model; volatile assumptions must stay in adapters or contract-watch logic.**

## Core design decision

The recommended architecture is:

**One canonical skill source + three render adapters + three verification pipelines + a compatibility evidence catalog.**

This means:

- authoring happens in one internal, platform-neutral source model
- generated platform outputs are disposable build artifacts, not the source of truth
- compatibility is computed from fresh verification evidence
- upstream spec changes are isolated inside platform profiles, adapters, and tests

Rejected alternatives:

- **Continue hand-authoring `_meta.json` + `SKILL.md` and declare `agent_compatible` manually:** too fragile and too easy to drift.
- **Pick one platform format as canonical and coerce the others into it:** guarantees repeated breakage when the chosen platform evolves.
- **Maintain three separate copies of each skill:** simplest short-term, highest long-term drift cost.
- **Wait for the three ecosystems to converge naturally:** unrealistic and blocks progress.

## Reference pattern borrowed from Superpowers

The strongest reusable pattern from `superpowers` is not “one magic file works everywhere”. It is:

1. keep one shared skill body library
2. add thin platform-specific wrappers or installers
3. centralize tool and workflow mapping instead of forking skill prose
4. verify behavior on each platform with dedicated tests

This project should adopt that pattern explicitly, but make it more rigorous than `superpowers` by introducing:

- a canonical schema instead of relying on repository convention alone
- machine-readable platform profiles
- compatibility status derived from verification, not only repository layout

## Design principles

### 1. Skill intent is canonical; packaging is not

The canonical model should describe what the skill means, when it triggers, what capabilities it needs, and what output it expects. It should not directly encode one platform's file layout or bootstrap UX.

### 2. Platform-specific details must be isolated

Everything likely to change upstream should live behind a platform adapter, platform profile, or contract-watch document.

### 3. Declared compatibility and verified compatibility are different things

Authors may declare intended support, but the exported catalog must expose verification state separately.

### 4. Graceful degradation is better than false compatibility

If a skill works on one platform only with reduced capabilities, the system should label it `degraded`, not `compatible`.

### 5. Backward-compatible migration matters

The project already has `_meta.json`, `SKILL.md`, templates, release artifacts, and install flows. The design should introduce a better authoring model without requiring an immediate rewrite of all existing flows.

## Recommended architecture layers

The project should now be treated as seven layers.

### 1. Canonical authoring layer

This is the only layer humans should edit for new skills.

Recommended location:

```text
skills-src/
  <skill>/
    skill.yaml
    instructions.md
    references/
    assets/
    scripts/
    platforms/
      claude.yaml
      codex.yaml
      openclaw.yaml
```

### 2. Governance layer

This layer contains repository-only concepts such as review policy, release policy, owners, namespace policy, risk scoring, and promotion state.

Existing `_meta.json` should remain supported during migration, but it should gradually become a **derived registry view** instead of the long-term authoring source.

### 3. Platform profile layer

Each target platform should expose a machine-readable capabilities and constraint profile.

Recommended location:

```text
profiles/
  claude.json
  codex.json
  openclaw.json
```

Each profile should describe:

- stable file layout expectations
- optional metadata files
- supported capability intents
- publish/install constraints
- verification entrypoints
- last verified upstream date

### 4. Adapter layer

Adapters render canonical source into platform-specific outputs.

Recommended scripts:

- `scripts/render-skill.py`
- `scripts/export-claude-skill.sh`
- `scripts/export-codex-skill.sh`
- `scripts/export-openclaw-skill.sh`

`render-skill.py` should be the shared engine. The shell entrypoints should be thin wrappers.

### 5. Verification layer

Each platform needs its own compatibility verifier.

Recommended scripts:

- `scripts/check-claude-compat.py`
- `scripts/check-codex-compat.py`
- `scripts/check-openclaw-compat.py`
- `scripts/check-platform-contracts.py`

### 6. Compatibility evidence layer

Verification outputs should be normalized into a single internal evidence format.

Recommended location:

```text
catalog/compatibility-evidence/
  <platform>/<skill>/<version>.json
```

### 7. Published compatibility catalog layer

`catalog/compatibility.json` should be regenerated from evidence, not from author-declared tags alone.

## Canonical skill model

The canonical authoring schema should capture three types of information:

1. **identity and intent**
2. **capabilities and degradation rules**
3. **verification expectations**

Recommended top-level fields for `skill.yaml`:

```yaml
schema_version: 1
name: brainstorming
summary: Refine rough ideas into an implementable design.
description: Use before creating features or changing behavior.
triggers:
  - before creative implementation work
  - when user asks for design exploration
examples:
  - "Design this feature before we build it"
instructions_body: instructions.md
tool_intents:
  required:
    - plan_tracking
    - file_read
  optional:
    - subagent_dispatch
degrades_to:
  no_subagent_dispatch: sequential-review-mode
distribution:
  public_publish_allowed: false
  text_only_required: true
verification:
  smoke_prompts:
    - prompts/default.txt
  required_platforms:
    - claude
    - codex
    - openclaw
```

### Why tool intents matter

Canonical skills should not directly say “call `TodoWrite`” or “call `Task`”. Those are platform tool names, not platform-neutral requirements.

Instead, the canonical schema should express tool **intent**:

- `plan_tracking`
- `subagent_dispatch`
- `shell_execution`
- `file_read`
- `file_write`
- `web_lookup`
- `background_process`
- `structured_review_output`

Adapters then map tool intents into platform-specific names, examples, or helper references.

## Platform-specific overlays

Each platform overlay should contain only the delta from the canonical model.

### `platforms/claude.yaml`

Use for:

- whether a wrapper skill should also emit a slash-command entry
- whether a dedicated subagent export is required
- Claude-specific discoverability wording

### `platforms/codex.yaml`

Use for:

- whether `AGENTS.md` fallback text should be emitted
- whether optional `agents/openai.yaml` metadata should be generated
- whether collab/subagent capability is required or optional

### `platforms/openclaw.yaml`

Use for:

- `metadata.openclaw.requires`
- public publish mode vs private runtime-only export
- license gating and text-only constraints

Overlay files must not duplicate the canonical instructions body. If an adapter needs a platform-specific wording block, it should reference a short supplement instead of forking the entire skill.

## Recommended repository layout

The target layout should be:

```text
skills-src/
  <skill>/
    skill.yaml
    instructions.md
    references/
    assets/
    scripts/
    platforms/
      claude.yaml
      codex.yaml
      openclaw.yaml

schemas/
  skill-canonical.schema.json
  platform-profile.schema.json

profiles/
  claude.json
  codex.json
  openclaw.json

build/
  claude/
  codex/
  openclaw/

catalog/
  compatibility.json
  compatibility-evidence/

docs/platform-contracts/
  claude.md
  codex.md
  openclaw.md
```

Existing `skills/incubating`, `skills/active`, and `skills/archived` can remain as governance/release views during migration.

## Output model by platform

### Claude output

The Claude adapter should generate a project- or user-installable skill tree under a Claude-compatible directory shape.

Recommended outputs:

- `.claude/skills/<skill>/SKILL.md`
- optional wrapper entries for command-style invocation
- optional subagent export when the skill represents a reviewer/specialist agent

Important design choice:

- **Do not make Claude marketplace packaging the canonical target.**
- Marketplace or plugin metadata should be a thin release/distribution layer added only if needed.

This keeps the design aligned to Claude's documented runtime skill surface instead of a more volatile packaging surface.

### Codex output

The Codex adapter should generate:

- `.agents/skills/<skill>/SKILL.md`
- optional support documents
- optional `agents/openai.yaml` metadata
- optional `AGENTS.md` bootstrap snippet for repository-level instruction layering

Important design choice:

- treat `AGENTS.md` as **instruction-layer support**, not as the skill format itself
- treat `.agents/skills` as the primary runtime skill output

### OpenClaw / ClawHub output

The OpenClaw adapter should generate a fully publishable skill folder, not just a copied release bundle.

Required properties for public-ready output:

- correct `SKILL.md` frontmatter
- correct `metadata.openclaw.requires`
- text-only bundle checks
- size-budget checks
- license-policy checks
- optional `.clawhubignore` generation if the ecosystem expects it

Important design choice:

- OpenClaw export must be **normalized**, not only materialized.
- If the public publish contract changes upstream, only the OpenClaw adapter and verifier should need updating.

## Governance model for compatibility

The system should distinguish four concepts clearly.

### 1. Declared support

What the author intends the skill to support.

### 2. Renderable support

Whether the adapter can successfully generate a platform artifact.

### 3. Verified support

Whether tests or validation have confirmed the artifact behaves correctly.

### 4. Published support

Whether the compatibility result is recent enough to be exported in public catalogs.

These should not collapse into one boolean.

## Compatibility states

Each platform result should use one of these states:

- `native`
- `adapted`
- `degraded`
- `unsupported`
- `unknown`

Definitions:

- `native`: platform supports the skill without semantic loss
- `adapted`: platform-specific wrapper needed, behavior remains materially equivalent
- `degraded`: skill works with reduced capability or different UX
- `unsupported`: cannot be safely rendered or verified
- `unknown`: not yet verified or verification expired

## Compatibility evidence format

Recommended evidence shape:

```json
{
  "schema_version": 1,
  "skill": "brainstorming",
  "version": "1.2.3",
  "platform": "codex",
  "profile_version": "2026-03-12",
  "adapter_version": "0.3.0",
  "state": "adapted",
  "verified_at": "2026-03-12T09:00:00Z",
  "verification_command": "python3 scripts/check-codex-compat.py --skill brainstorming",
  "artifacts": [
    "build/codex/brainstorming/SKILL.md"
  ],
  "notes": [
    "Codex export uses tool-intent mapping for plan_tracking -> update_plan"
  ]
}
```

`catalog/compatibility.json` should aggregate these files and expose both:

- declared support
- verified support

## Contract-watch model

Because the three ecosystems will continue evolving, the repository needs a first-class contract-watch process.

Recommended new docs:

```text
docs/platform-contracts/
  claude.md
  codex.md
  openclaw.md
```

Each contract doc should contain:

- stable assumptions
- volatile assumptions
- current official source links
- last verified date
- verification steps
- known gaps

`scripts/check-platform-contracts.py` should then:

1. confirm the upstream source URLs still resolve
2. confirm key terms or anchors still exist
3. fail or warn if a contract has not been reviewed within the allowed age window

This turns upstream change into an explicit maintenance task instead of a surprise regression.

## Versioning strategy

Do not use one version number for everything.

The design should track at least:

- `skill_version`
- `canonical_schema_version`
- `adapter_version.<platform>`
- `platform_profile_version.<platform>`
- `compatibility_contract_version`

This gives the project clean change boundaries:

- skill prose changes do not imply adapter changes
- platform export fixes do not imply schema changes
- upstream platform contract shifts do not imply a new skill semantic version

## CI and verification strategy

Compatibility should be enforced in CI through three kinds of checks.

### 1. Schema checks

Validate canonical source and profile files.

### 2. Adapter checks

Validate generated outputs structurally.

### 3. Behavior checks

Validate real or simulated platform behavior.

Recommended CI tasks:

- `python3 scripts/check-canonical-schema.py`
- `python3 scripts/check-claude-compat.py`
- `python3 scripts/check-codex-compat.py`
- `python3 scripts/check-openclaw-compat.py`
- `python3 scripts/check-platform-contracts.py`
- `scripts/build-catalog.sh`

### Minimum behavior coverage per platform

#### Claude

- skill folder renders successfully
- trigger text remains valid
- command/subagent wrappers render when configured
- at least one prompt-based smoke test confirms intended activation behavior

#### Codex

- skill folder renders successfully
- `SKILL.md` frontmatter is valid
- optional `agents/openai.yaml` metadata validates when emitted
- at least one smoke test confirms intended discovery / activation behavior

#### OpenClaw

- export folder renders successfully
- frontmatter and OpenClaw metadata validate
- publish constraints pass
- a publish dry-run or equivalent validation succeeds

## Migration plan from the current repository

The current repository should migrate incrementally.

### Phase 0: documentation and contracts

- add platform contract docs
- add this design doc
- add compatibility-state terminology to repo docs

### Phase 1: canonical schema introduction

- add `schemas/skill-canonical.schema.json`
- add `skills-src/` for new skills
- keep existing `skills/` folders as legacy-compatible inputs
- make renderers dual-read canonical or legacy layouts

### Phase 2: adapter engine

- add `scripts/render-skill.py`
- refactor `scripts/export-openclaw-skill.sh` to use the shared renderer
- add Codex and Claude export entrypoints

### Phase 3: verification and evidence

- add platform compatibility checks
- add compatibility evidence files
- regenerate `catalog/compatibility.json` from evidence

### Phase 4: governance convergence

- derive more of `_meta.json` from canonical source + governance overlay
- shrink the amount of duplicated author-maintained metadata

### Phase 5: public-ready OpenClaw hardening

- enforce license and text-only gates for publishable exports
- add dry-run publish validation to CI

## Backward-compatibility strategy

This migration should follow a dual-read / single-write model.

- readers accept legacy `skills/<stage>/<name>/` source folders
- new tooling writes canonical-source-based outputs
- compatibility catalogs continue exporting current fields during the migration window
- legacy `_meta.json.agent_compatible` remains readable, but it should stop being the authoritative compatibility result

## Risks and mitigations

### Risk: canonical schema becomes too abstract

Mitigation:

- keep the canonical model narrow
- only store platform-neutral intent there
- push all uncertain fields into platform overlays

### Risk: adapter logic becomes a second product

Mitigation:

- keep one shared renderer engine
- keep shell wrappers thin
- keep platform profiles declarative

### Risk: verification becomes flaky

Mitigation:

- split structural checks from behavior checks
- allow behavior tests to run in tiers
- mark stale verification as `unknown` instead of pretending it still holds

### Risk: authors keep editing generated outputs by hand

Mitigation:

- document generated directories clearly
- make renderers overwrite build outputs deterministically
- prefer storing generated artifacts under `build/` or release folders only

## Non-goals

- Do not build a hosted multi-tenant registry service in this phase.
- Do not require exact feature parity across platforms when a platform truly lacks a capability.
- Do not freeze upstream platform semantics inside this repository.
- Do not automatically public-publish to ClawHub by default.

## Success criteria

This design is successful when the repository can truthfully say all of the following:

- every new skill is authored once in canonical source
- Claude, Codex, and OpenClaw outputs are generated from that source
- compatibility claims are evidence-backed and timestamped
- upstream spec changes are localized to profiles, adapters, and tests
- OpenClaw public exports are normalized and validated before publication
- repository maintainers can tell the difference between `declared`, `adapted`, `verified`, and `published` compatibility

## Immediate implementation follow-on

The next implementation plan should focus on the smallest durable slice:

1. add canonical schema and `skills-src/`
2. add shared renderer engine
3. refactor OpenClaw export onto the renderer
4. add Codex export
5. add Claude export
6. add compatibility evidence generation
7. add contract-watch and CI checks

That sequence maximizes reuse, improves OpenClaw first where the current gap is hardest, and avoids building three unrelated one-off exporters.
