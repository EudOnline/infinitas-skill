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
- optional memory signals (advisory only)

## Reading the output

Look at these keys first:

- `recommendation_reason`
- `ranking_factors`
- `confidence`
- `comparative_signals`
- `trust_state`
- `verified_support`
- `use_when`
- `avoid_when`
- `capabilities`
- `runtime_assumptions`
- `maturity`
- `quality_score`
- `memory_signals`

`ranking_factors` should make it clear how compatibility, maturity, trust state, quality, and verification freshness affected the result.

`confidence` is the recommendation layer's machine-readable confidence view for that candidate. Read:

- `confidence.level`
- `confidence.reasons`

`comparative_signals` is the additive cross-candidate view. Read:

- `comparative_signals.rank`
- `comparative_signals.score_gap_from_top`
- `comparative_signals.quality_gap_from_top`
- `comparative_signals.verification_freshness_gap_from_top`
- `comparative_signals.compatibility_gap_from_top`

At the top level, `explanation.comparison_summary` and `explanation.winner_confidence` explain why the winner outranked the closest visible alternative.

When memory-aware recommendation is enabled, also read:

- `explanation.memory_summary`
- `memory_signals.matched_memory_count`
- `memory_signals.applied_boost`
- `memory_signals.memory_types`

`memory_summary` reports whether memory was used, which backend supplied memory, and how many retrieved memories were considered. This layer is advisory only and does not replace compatibility, trust, or immutable install policy checks.

`memory_summary.used` means at least one candidate received a non-zero memory boost. Retrieved memories alone do not set `used=true`.

`memory_summary.status` distinguishes memory states:

- `disabled`: memory layer was not enabled for this recommendation
- `unavailable`: provider has no read capability
- `no-match`: memory retrieval succeeded but returned no usable memories
- `matched`: memory retrieval succeeded with usable memories
- `error`: memory retrieval failed; see optional `memory_summary.error`

Example:

```json
{
  "explanation": {
    "memory_summary": {
      "used": true,
      "backend": "memo0",
      "matched_count": 2,
      "advisory_only": true,
      "status": "matched"
    }
  },
  "results": [
    {
      "qualified_name": "lvxiaoer/consume-infinitas-skill",
      "memory_signals": {
        "matched_memory_count": 2,
        "applied_boost": 35,
        "memory_types": ["user_preference", "experience"]
      }
    }
  ]
}
```

Interpret the example this way:

- memory retrieval found relevant advisory context
- only compatible candidates received a boost
- the boost remained bounded and explainable
- the normal compatibility, trust, and install policy chain still decided what was eligible

`_meta.json` is the canonical source of authored decision metadata. Generated indexes and AI wrappers mirror those same fields so recommend, search, and inspect can stay in sync without inventing separate copies of `use_when`, `avoid_when`, `capabilities`, `runtime_assumptions`, `maturity`, or `quality_score`.

The surfaced decision metadata is the canonical author-owned guidance from `_meta.json`. Use it to explain why a skill fits the task without reopening raw catalogs.

## Safety rules

- recommendation does not bypass immutable install policy
- external recommendations still require confirmation before installation
- high recommendation confidence does not replace inspect-before-install when provenance, trust state, or compatibility matter
- recommendation is advisory; inspect the skill before install when provenance, trust state, or compatibility matters
- memory boost is bounded and cannot lift incompatible candidates above compatible ones
- if memory retrieval fails, recommendation still returns deterministic results and reports the advisory error in `explanation.memory_summary`
