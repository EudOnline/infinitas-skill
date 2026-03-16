# Stable Usage Guide

## Goal

This is the stable high-level guide for humans and agents.

Use it to decide when to use the public AI-facing commands without opening implementation internals first. Then drop into `docs/ai/agent-operations.md`, `docs/ai/workflow-drills.md`, or the protocol docs when you need deeper detail.

## Read Order

- `README.md`
- `docs/ai/usage-guide.md`
- `docs/ai/agent-operations.md`
- `docs/ai/workflow-drills.md`
- protocol docs such as `docs/ai/discovery.md`, `docs/ai/recommend.md`, `docs/ai/publish.md`, and `docs/ai/pull.md`

## When To Use Which Command

### Search

Use `scripts/search-skills.sh` when to use a skill is still unclear and you want a broad candidate list first.

```bash
scripts/search-skills.sh release
scripts/search-skills.sh --publisher lvxiaoer --agent codex
```

Choose this path when the user knows a topic, tag, publisher, or target agent but not the best exact skill name yet.

### Recommend

Use `scripts/recommend-skill.sh` when the task is clearer than the skill name and you want the best-ranked candidate.

```bash
scripts/recommend-skill.sh "publish immutable skill release"
```

Read `recommendation_reason`, `ranking_factors`, `confidence`, and `comparative_signals` before deciding whether to move forward.

### Inspect

Use `scripts/inspect-skill.sh` before install or publish whenever trust state, compatibility, provenance, or dependency context matters.

```bash
scripts/inspect-skill.sh lvxiaoer/release-infinitas-skill
```

Inspect is the safest way to verify a candidate before mutation.

### Publish

Use `scripts/publish-skill.sh` when a registry-managed skill is ready to emit immutable release artifacts for other agents.

```bash
scripts/publish-skill.sh lvxiaoer/release-infinitas-skill --mode confirm
scripts/publish-skill.sh lvxiaoer/release-infinitas-skill
```

Start with `--mode confirm` when the user wants a plan or when you need to show what will happen before mutating the repository.

### Pull

Use `scripts/pull-skill.sh` when another agent needs a released skill installed into a runtime directory from immutable artifacts.

```bash
scripts/pull-skill.sh lvxiaoer/release-infinitas-skill ~/.openclaw/skills --mode confirm
scripts/pull-skill.sh lvxiaoer/release-infinitas-skill ~/.openclaw/skills
```

Use this instead of copying from `skills/active/` or `skills/incubating/`.

### Verify

Use `scripts/check-skill.sh` to verify one skill before review or publish. Use `scripts/check-all.sh` to verify the broader repository contract before finishing a larger change.

```bash
scripts/check-skill.sh skills/active/release-infinitas-skill
scripts/check-all.sh
```

If the task is “is this safe to ship?” or “did we break the platform?”, verify before you publish or tell another agent to pull.

## Confirm-First Rule

Prefer `--mode confirm` when:

- the user asks what will happen
- you are about to mutate the repo or a runtime install target
- a skill name, version, or registry choice may be ambiguous
- you need to present a plan to another agent or a human first

## Minimal Safe Flow

1. Search or recommend.
2. Inspect the chosen skill.
3. Preview with `--mode confirm` when mutation is involved.
4. Publish or pull only after trust state, compatibility, provenance, and version selection look correct.
5. Verify with `scripts/check-skill.sh` or `scripts/check-all.sh` when the task includes release readiness or platform safety.

## Stop Conditions

- Search or recommend results are ambiguous enough that the user must choose.
- Inspect shows missing provenance, missing immutable artifacts, or incompatible runtime assumptions.
- Publish or pull preview returns a structured failure payload.
- Verification fails.

When any of these happen, stop and switch to the deeper protocol docs or `docs/ai/workflow-drills.md` instead of guessing.
