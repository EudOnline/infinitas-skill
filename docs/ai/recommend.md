# Recommendation Workflow

## Goal

Help an agent choose the best skill when it knows the job to do, but not the exact skill name.

## Command

```bash
scripts/recommend-skill.sh "Need a codex skill for repository operations"
scripts/recommend-skill.sh "Need an OpenClaw publishing helper" --target-agent openclaw
```

## When to use it

- use `scripts/search-skills.sh` when you want a broad list of possible matches
- use `scripts/recommend-skill.sh` when you want the best-ranked candidate for a task
- use `scripts/inspect-skill.sh` after recommendation to confirm trust state, provenance, and distribution details

## Ranking factors

Recommendation ranking is deterministic and should consider:

- private registry preference
- compatibility with the target agent
- task-term match strength
- trust state
- maturity
- quality score
- verification freshness

## Reading the output

Look at these keys first:

- `recommendation_reason`
- `ranking_factors`
- `trust_state`
- `verified_support`

`ranking_factors` should make it clear how compatibility, maturity, trust state, quality, and verification freshness affected the result.

## Safety rules

- recommendation does not bypass immutable install policy
- external recommendations still require confirmation before installation
- recommendation is advisory; inspect the skill before install when provenance, trust state, or compatibility matters
