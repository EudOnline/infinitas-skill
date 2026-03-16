# AI Workflow Drills

## Goal

Give agents a small set of realistic drills they can complete using only:

- `README.md`
- `docs/ai/agent-operations.md`
- `docs/ai/discovery.md`
- `docs/ai/search-and-inspect.md`
- `docs/ai/recommend.md`
- `docs/ai/publish.md`
- `docs/ai/pull.md`
- generated JSON such as `catalog/ai-index.json`

For routine workflows, do not open implementation internals or helper-library code. Stay on documented wrapper commands and stable JSON outputs unless the task has turned into debugging.

## Drill 1: Search -> Inspect -> Install Preview

Use this when the user wants a broad list first.

### Commands

```bash
scripts/search-skills.sh release
scripts/inspect-skill.sh lvxiaoer/release-infinitas-skill
scripts/install-by-name.sh release-infinitas-skill ~/.openclaw/skills --mode confirm
```

### Read these keys first

- search result:
  - `qualified_name`
  - `use_when`
  - `runtime_assumptions`
  - `verified_support`
- inspect result:
  - `decision_metadata`
  - `distribution.manifest_path`
  - `provenance.attestation_path`
  - `trust.state`
- install preview:
  - `state`
  - `manifest_path`
  - `attestation_path`
  - `explanation`

### Stop conditions

- no search results
- trust state is unclear and inspect does not surface provenance or distribution references
- install preview does not stay in `--mode confirm`

## Drill 2: Recommend -> Inspect

Use this when the task is clearer than the skill name.

### Commands

```bash
scripts/recommend-skill.sh "publish immutable skill release"
scripts/inspect-skill.sh lvxiaoer/release-infinitas-skill
```

### Read these keys first

- recommendation:
  - `recommendation_reason`
  - `ranking_factors`
  - `confidence`
  - `comparative_signals`
  - `use_when`
  - `avoid_when`
- inspect:
  - `decision_metadata`
  - `compatibility.verified_summary`
  - `provenance.attestation_path`

### Stop conditions

- recommendation output has no `ranking_factors`
- recommendation output has no `confidence` or `comparative_signals`
- the recommended skill conflicts with `avoid_when`
- inspect shows missing immutable distribution references

## Drill 3: Inspect Before Any Mutation

Use this when the user already named a skill, but install or publish still carries trust risk.

### Commands

```bash
scripts/inspect-skill.sh lvxiaoer/consume-infinitas-skill
scripts/pull-skill.sh lvxiaoer/consume-infinitas-skill ~/.openclaw/skills --mode confirm
```

### Read these keys first

- `decision_metadata`
- `compatibility.verified_support`
- `distribution.manifest_path`
- `provenance.attestation_path`
- pull preview `explanation.policy_reasons`

### Stop conditions

- inspect shows missing provenance or manifest paths
- pull preview is not `state: planned`
- the runtime assumptions do not match the target environment

## Drill 4: Publish Preview

Use this when the agent needs to explain what a release would do before mutating the repo.

### Commands

```bash
scripts/check-skill.sh skills/active/release-infinitas-skill
scripts/publish-skill.sh release-infinitas-skill --mode confirm
```

### Read these keys first

- `state`
- `commands`
- `manifest_path`
- `attestation_path`
- `next_step`

### Stop conditions

- `check-skill.sh` fails
- publish preview is not `state: planned`
- preview output does not describe immutable release artifacts

## Drill 5: Pull Preview -> Pull

Use this when the user wants a stable release installed into a runtime directory.

### Commands

```bash
scripts/pull-skill.sh lvxiaoer/release-infinitas-skill ~/.openclaw/skills --mode confirm
scripts/pull-skill.sh lvxiaoer/release-infinitas-skill ~/.openclaw/skills
```

### Read these keys first

- confirm preview:
  - `state`
  - `manifest_path`
  - `bundle_sha256`
  - `attestation_path`
  - `install_command`
  - `explanation`
- final install:
  - `state`
  - `lockfile_path`
  - `installed_files_manifest`
  - `next_step`

### Stop conditions

- preview does not remain side-effect free in `--mode confirm`
- immutable manifest or attestation references are missing
- target runtime assumptions are not met

## Safety Rules

- prefer `--mode confirm` before publish or pull when the user has not asked for immediate mutation
- read generated indexes and structured wrapper output before opening repository internals
- do not treat `skills/active/` or `skills/incubating/` as install artifacts
- inspect first when trust state, compatibility, provenance, or runtime assumptions matter
- if `install-by-name.sh` returns `ambiguous-skill-name`, stop and ask for a `qualified_name`
- if `install-by-name.sh` returns `incompatible-target-agent`, stop and report the compatibility mismatch instead of dropping the agent filter
- if `pull-skill.sh` returns `missing-distribution-fields` or `missing-distribution-file`, stop and ask for rebuild or republish of immutable artifacts
- when immutable artifacts are missing, do not fall back to mutable source folders or local prototypes
