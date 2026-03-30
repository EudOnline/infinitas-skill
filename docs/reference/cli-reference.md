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
usage: infinitas [-h] {compatibility,release} ...

infinitas project CLI

positional arguments:
  {compatibility,release}
    compatibility       Compatibility tools
    release             Release tools

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
