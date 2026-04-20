---
audience: contributors, integrators, automation authors
owner: repository maintainers
source_of_truth: legacy ai protocol annex
last_reviewed: 2026-04-21
status: legacy
---

# Search and Inspect

## Goal

Give consumers a stable, index-first workflow for:

- finding installable skills
- inspecting trust state before install
- reading compatibility, dependency, and provenance views
- understanding explain-style install and upgrade decisions

## Commands

```bash
scripts/search-skills.sh operate
scripts/search-skills.sh --publisher lvxiaoer --agent codex
scripts/recommend-skill.sh "Need a codex skill for repository operations"
scripts/search-skills.sh --tag operations
scripts/inspect-skill.sh lvxiaoer/operate-infinitas-skill
scripts/install-by-name.sh operate-infinitas-skill ~/.openclaw/skills --mode confirm
scripts/upgrade-skill.sh operate-infinitas-skill ~/.openclaw/skills --mode confirm
```

## Search

Use `scripts/search-skills.sh` when the caller knows only a topic, publisher, agent, or tag.

The output is built from `catalog/discovery-index.json` and includes:

- `qualified_name`
- `publisher`
- `latest_version`
- `trust_state`
- `verified_support`
- `use_when`
- `avoid_when`
- `capabilities`
- `runtime_assumptions`
- `maturity`
- `quality_score`
- `attestation_formats`
- `source_registry`

These fields are mirrored from the canonical author-owned decision metadata in each skill's `_meta.json`, then projected through generated indexes for stable consumer use.

Do not scrape raw source paths from `skills/active/` or `skills/incubating/` for consumer discovery.

## Recommend

Use `scripts/recommend-skill.sh` when the caller describes a task instead of an exact skill name.

The recommendation output should explain why the top result won through:

- `recommendation_reason`
- `ranking_factors`
- `confidence`
- `comparative_signals`
- trust state
- compatibility
- maturity
- verification freshness

When multiple candidates are eligible, prefer the additive comparison fields over ad-hoc prose:

- `confidence.level` and `confidence.reasons`
- `comparative_signals.rank`
- `comparative_signals.score_gap_from_top`
- `comparative_signals.quality_gap_from_top`
- `comparative_signals.verification_freshness_gap_from_top`
- `comparative_signals.compatibility_gap_from_top`
- `explanation.comparison_summary`

Search gives a broad candidate set. Recommend gives a ranked best-fit view.

## Inspect

Use `scripts/inspect-skill.sh` before install when you need:

- trust state
- compatibility verified summary
- canonical `decision_metadata` for fit checks
- dependency root and steps summary
- provenance paths and attestation policy
- verified distribution manifest and bundle references

The inspect surface is built from the generated AI index, distribution manifest, and release provenance. It is the preferred way to inspect a stable release without opening raw catalog internals.

Read `decision_metadata` first when you need the author-owned selection hints:

- `use_when`
- `avoid_when`
- `capabilities`
- `runtime_assumptions`
- `maturity`
- `quality_score`

Treat `_meta.json` as the canonical source and search / recommend / inspect outputs as projections of that same metadata, not separate authored copies.

## Verified distribution manifests

verified distribution manifests are the default consumer path.

- install and upgrade should resolve released artifacts from `catalog/distributions/...`
- provenance should come from `catalog/provenance/...`
- stable consumers should not copy mutable working-tree folders directly

If trust is unclear, inspect the skill first and confirm the manifest path, provenance path, attestation formats, and trust state.

## Explain-style output

`scripts/resolve-skill.sh`, `scripts/install-by-name.sh`, `scripts/check-skill-update.sh`, and `scripts/upgrade-skill.sh` may include an additive `explanation` object.

Read these keys first:

- `selection_reason`
- `policy_reasons`
- `version_reason`
- `next_actions`

For recommendation flows, also read:

- `recommendation_reason`
- `ranking_factors`
- `confidence`
- `comparative_signals`

This explanation layer is the fast way to answer:

- why a private match won
- why an external match needs confirmation
- why a version was selected
- why a cross-source upgrade is blocked
- how strongly the top recommendation outranks the next-best candidate

## Recommended flow

1. search with `scripts/search-skills.sh`
2. inspect with `scripts/inspect-skill.sh`
3. preview with `scripts/install-by-name.sh ... --mode confirm`
4. install or upgrade only after trust state, compatibility, provenance, and distribution manifest checks look correct
