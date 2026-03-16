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

Do not scrape raw source paths from `skills/active/` or `skills/incubating/` for consumer discovery.

## Recommend

Use `scripts/recommend-skill.sh` when the caller describes a task instead of an exact skill name.

The recommendation output should explain why the top result won through:

- `recommendation_reason`
- `ranking_factors`
- trust state
- compatibility
- maturity
- verification freshness

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

This explanation layer is the fast way to answer:

- why a private match won
- why an external match needs confirmation
- why a version was selected
- why a cross-source upgrade is blocked

## Recommended flow

1. search with `scripts/search-skills.sh`
2. inspect with `scripts/inspect-skill.sh`
3. preview with `scripts/install-by-name.sh ... --mode confirm`
4. install or upgrade only after trust state, compatibility, provenance, and distribution manifest checks look correct
