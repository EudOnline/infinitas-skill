# OpenClaw Platform Contract

## Stable assumptions
- OpenClaw skills are centered on `SKILL.md` and follow an AgentSkills-compatible layout.
- OpenClaw requires at least `name` and `description` in frontmatter and supports additional `metadata.openclaw` gating fields.
- ClawHub is the public registry for OpenClaw skills and distributes versioned skill bundles.
- Workspace skills under `<workspace>/skills` remain a primary installation/runtime surface.

## Volatile assumptions
- ClawHub moderation, publishing policy, and public-safety requirements may tighten over time.
- The exact OpenClaw parser rules for frontmatter, metadata normalization, and UI-only fields may evolve.
- Runtime precedence between workspace, bundled, and extra-dir skills may change across releases.

## Official sources
- https://docs.openclaw.ai/tools/skills
- https://docs.openclaw.ai/tools/clawhub

## Last verified
2026-03-12

## Verification steps
- Confirm the Skills page still documents required `SKILL.md` frontmatter and the single-line `metadata` constraints.
- Confirm the gating fields under `metadata.openclaw.requires` remain the documented compatibility contract.
- Confirm the ClawHub page still describes public versioned bundles, install flow, and workspace-oriented runtime resolution.

## Known gaps
- OpenClaw public publishing rules are product-policy surfaces as well as file-format surfaces, so public readiness must continue to be checked separately.
- ClawHub compatibility is stricter than local OpenClaw runtime compatibility; a local export can still fail public-ready validation.
