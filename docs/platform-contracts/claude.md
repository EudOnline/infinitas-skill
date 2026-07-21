---
audience: contributors, reviewers, compatibility maintainers
owner: repository maintainers
source_of_truth: legacy platform contract annex
last_reviewed: 2026-07-21
status: legacy
---

# Claude Platform Contract

## Stable assumptions
- Claude Code natively supports Agent Skills as directories containing `SKILL.md` plus optional supporting files.
- Project skills live under `.claude/skills/`; personal skills live under `~/.claude/skills/`; enterprise and plugin scopes are also supported.
- Claude Code loads skill metadata first and loads the body only when relevant or explicitly invoked.
- Custom commands remain compatible but are merged into the Skills model; Skills add supporting files, invocation controls, and automatic discovery.
- Skills can run inline or in a forked subagent context, with Claude-specific frontmatter controlling tools, model, hooks, paths, and invocation.

## Volatile assumptions
- Anthropic may evolve subagent frontmatter keys, supported models, and plugin/distribution mechanisms.
- Built-in helper agents, default permission behavior, and CLI flags may change without matching third-party runtimes.
- Claude-specific skill frontmatter and precedence behavior may evolve independently from the portable Agent Skills core.

## Official sources
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/security
- https://code.claude.com/docs/en/getting-started

## Last verified
2026-07-21

## Verification steps
- Confirm the Skills guide still documents `SKILL.md`, supporting files, progressive loading, and project/personal/plugin scopes.
- Confirm the Skills and Subagents guides still document invocation controls, forked execution, tool controls, model selection, and skill preloading.
- Re-check the security page for the current permission model and approval semantics.

## Known gaps
- Claude Code extends the portable Agent Skills format with runtime-specific frontmatter, so exact behavior beyond `name`, `description`, `SKILL.md`, and supporting files remains adapter-sensitive.
- Enterprise and cloud skill distribution have additional policy and synchronization semantics that local directory validation does not prove.
