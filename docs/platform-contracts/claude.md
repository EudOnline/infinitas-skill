# Claude Platform Contract

## Stable assumptions
- Claude Code supports custom subagents defined as Markdown files with YAML frontmatter.
- Project-level subagents live under `.claude/agents/`; user-level subagents live under `~/.claude/agents/`.
- Subagent configuration can include tool restrictions, model choice, permission mode, hooks, memory, and a `skills` field.

## Volatile assumptions
- Anthropic may evolve subagent frontmatter keys, supported models, and plugin/distribution mechanisms.
- Built-in helper agents, default permission behavior, and CLI flags may change without matching third-party runtimes.
- The relationship between Claude subagents and reusable skill packs is still less stable than Codex/OpenClaw's explicit skill directory contracts.

## Official sources
- https://code.claude.com/docs/en/sub-agents
- https://docs.anthropic.com/en/docs/claude-code/security
- https://docs.anthropic.com/en/docs/claude-code/getting-started

## Last verified
2026-03-12

## Verification steps
- Confirm the subagents guide still documents Markdown + YAML frontmatter and the storage scopes for `.claude/agents/` and `~/.claude/agents/`.
- Confirm the documented config surface still includes tool controls, model selection, and `skills` support.
- Re-check the security page for the current permission model and approval semantics.

## Known gaps
- Anthropic documents subagents directly; it does not currently publish a first-class “skill bundle” contract matching Codex/OpenClaw one-to-one.
- This repository therefore treats Claude compatibility as an adapter target over the subagent/runtime model, not as proof of native artifact parity.
