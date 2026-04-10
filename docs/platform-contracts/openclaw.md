# OpenClaw Platform Contract

## Stable assumptions
- OpenClaw skills are centered on `SKILL.md` and runtime resolution includes workspace-first directories such as `skills` and `.agents/skills`.
- OpenClaw supports native sub-agent delegation, plugin capabilities, background tasks, and cron jobs in maintained runtime flows.
- OpenClaw runtime state and session semantics can be workspace-scoped in addition to user-level directories.
- ClawHub is the public registry for OpenClaw skills and distributes versioned skill bundles.

## Volatile assumptions
- ClawHub moderation, publishing policy, and public-safety requirements may tighten over time.
- OpenClaw plugin capability shape and permission declarations may evolve.
- Background task and cron scheduling behavior can change as OpenClaw runtime releases iterate.
- Runtime precedence between workspace and user-level skill directories may change across releases.

## Official sources
- https://docs.openclaw.ai/tools/skills
- https://docs.openclaw.ai/tools/subagents
- https://docs.openclaw.ai/tools/plugins
- https://docs.openclaw.ai/tools/background-tasks
- https://docs.openclaw.ai/tools/cron-jobs
- https://docs.openclaw.ai/tools/clawhub

## Last verified
2026-04-07

## Verification steps
- Confirm the Skills page still documents `SKILL.md`-based runtime semantics and workspace-oriented skill directory behavior.
- Confirm the Sub-Agents and Plugins pages still document maintained delegation and capability model assumptions.
- Confirm the Background Tasks and Cron Jobs pages still describe maintained scheduled execution semantics.
- Confirm the ClawHub page still describes public versioned bundles and install flow.

## Known gaps
- OpenClaw public publishing rules are product-policy surfaces as well as file-format surfaces, so public readiness must continue to be checked separately.
- ClawHub compatibility is stricter than local OpenClaw runtime compatibility; a local package can still fail public-ready validation.
