---
audience: contributors, integrators, operators
owner: repository maintainers
source_of_truth: generated from argparse definitions in src/infinitas_skill
last_reviewed: 2026-03-30
status: maintained
---

# CLI Reference

This file is generated from the maintained argparse definitions under `src/infinitas_skill/`.

Regenerate and review it with:

```bash
uv run python3 -m infinitas_skill.cli.reference
```

## Top-level CLI

```text
usage: infinitas [-h] {compatibility,release,install,registry} ...

infinitas project CLI

positional arguments:
  {compatibility,release,install,registry}
    compatibility       Compatibility tools
    release             Release tools
    install             Install planning tools
    registry            Hosted registry control-plane tools

options:
  -h, --help            show this help message and exit
```

## `infinitas compatibility check-platform-contracts`

```text
usage: infinitas compatibility check-platform-contracts [-h]
                                                        [--max-age-days MAX_AGE_DAYS]
                                                        [--stale-policy {warn,fail}]

Check platform contract-watch documents.

options:
  -h, --help            show this help message and exit
  --max-age-days MAX_AGE_DAYS
                        Warn when Last verified is older than this many days.
  --stale-policy {warn,fail}
                        Whether over-age contract docs should warn or fail.
```

## `infinitas install resolve-plan`

```text
usage: infinitas install resolve-plan [-h] --skill-dir SKILL_DIR
                                      [--target-dir TARGET_DIR]
                                      [--source-registry SOURCE_REGISTRY]
                                      [--source-json SOURCE_JSON]
                                      [--mode {install,sync}] [--json]

Resolve an install or sync dependency plan

options:
  -h, --help            show this help message and exit
  --skill-dir SKILL_DIR
                        Skill directory to resolve from
  --target-dir TARGET_DIR
                        Existing install target directory to plan against
  --source-registry SOURCE_REGISTRY
                        Registry hint for the root skill source
  --source-json SOURCE_JSON
                        Resolved source metadata JSON for the root skill
  --mode {install,sync}
                        Whether to plan an install or sync flow
  --json                Print machine-readable plan output
```

## `infinitas install check-target`

```text
usage: infinitas install check-target [-h] [--source-registry SOURCE_REGISTRY]
                                      [--source-json SOURCE_JSON]
                                      [--mode {install,sync}] [--json]
                                      skill_dir target_dir

Check whether an install target is dependency-safe

positional arguments:
  skill_dir             Skill directory to validate
  target_dir            Install target directory to validate against

options:
  -h, --help            show this help message and exit
  --source-registry SOURCE_REGISTRY
                        Registry hint for the root skill source
  --source-json SOURCE_JSON
                        Resolved source metadata JSON for the root skill
  --mode {install,sync}
                        Whether to check an install or sync flow
  --json                Print machine-readable plan output
```

## `infinitas registry`

```text
usage: infinitas registry [-h] [--base-url BASE_URL] [--token TOKEN]
                          {skills,drafts,releases,exposures,grants,tokens,reviews}
                          ...

Hosted registry private-first control plane CLI

positional arguments:
  {skills,drafts,releases,exposures,grants,tokens,reviews}
    skills              Manage private-first skill records
    drafts              Manage editable drafts and immutable version sealing
    releases            Create and inspect immutable releases
    exposures           Manage audience exposure and share policy
    grants              Inspect grant policy scaffolding for token-scoped
                        access
    tokens              Inspect token identity and release authorization
    reviews             Manage review cases for public-facing exposures

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Hosted registry API base URL
  --token TOKEN         Bearer token for hosted registry API
```

## `infinitas release check-state`

```text
usage: infinitas release check-state [-h]
                                     [--mode {preflight,local-preflight,local-tag,stable-release}]
                                     [--json] [--debug-policy]
                                     skill

Check stable release invariants for a skill

positional arguments:
  skill                 Skill name or path

options:
  -h, --help            show this help message and exit
  --mode {preflight,local-preflight,local-tag,stable-release}
                        Which release invariant set to enforce
  --json                Print machine-readable state
  --debug-policy        Print a human-readable policy trace
```
