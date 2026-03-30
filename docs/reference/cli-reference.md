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

Status labels used in this reference:

- `maintained`: canonical `infinitas ...` entrypoint defined in `src/infinitas_skill/`
- `shim`: temporary script wrapper still available during the reset
- `legacy-only`: intentionally omitted from this maintained reference; use [CLI Command Map](cli-command-map.md) for bridge inventory details

## Top-level CLI

Status: `maintained` umbrella CLI. `legacy-only` surfaces should migrate behind one of the documented families below.

```text
usage: infinitas [-h]
                 {compatibility,release,install,registry,policy,server} ...

infinitas project CLI

positional arguments:
  {compatibility,release,install,registry,policy,server}
    compatibility       Compatibility tools
    release             Release tools
    install             Install planning tools
    registry            Hosted registry control-plane tools
    policy              Policy validation and promotion tools
    server              Hosted server operations tools

options:
  -h, --help            show this help message and exit
```

## `infinitas compatibility check-platform-contracts`

Status: `maintained`. Shim: `python3 scripts/check-platform-contracts.py ...`.

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

Status: `maintained`. Shim: `python3 scripts/resolve-install-plan.py ...`.

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

Status: `maintained`. Shim: `python3 scripts/check-install-target.py ...`.

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

## `infinitas policy`

Status: `maintained` family. Shims: `python3 scripts/check-policy-packs.py` and `python3 scripts/check-promotion-policy.py ...`.

```text
usage: infinitas policy [-h] {check-packs,check-promotion} ...

Policy validation and promotion CLI

positional arguments:
  {check-packs,check-promotion}
    check-packs         Validate policy-pack selector and active pack files
    check-promotion     Check active promotion policy for one or more skills

options:
  -h, --help            show this help message and exit
```

## `infinitas policy check-packs`

Status: `maintained`. Shim: `python3 scripts/check-policy-packs.py`.

```text
usage: infinitas policy check-packs [-h]

Validate policy-pack selector and active pack files

options:
  -h, --help  show this help message and exit
```

## `infinitas policy check-promotion`

Status: `maintained`. Shim: `python3 scripts/check-promotion-policy.py ...`.

```text
usage: infinitas policy check-promotion [-h] [--as-active] [--json]
                                        [--debug-policy]
                                        [targets ...]

Check active promotion policy for one or more skills

positional arguments:
  targets         Skill directory path(s) to check

options:
  -h, --help      show this help message and exit
  --as-active     Evaluate targets as active-stage skills
  --json          Print machine-readable output
  --debug-policy  Print a human-readable policy trace
```

## `infinitas registry`

Status: `maintained`. Shim: `python3 scripts/registryctl.py ...`.

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

Status: `maintained`. Shim: `python3 scripts/check-release-state.py ...`.

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

## `infinitas server`

Status: `maintained` family. Legacy server-operation wrapper scripts are deleted; use the canonical `infinitas server ...` entrypoints directly.

```text
usage: infinitas server [-h]
                        {healthcheck,backup,render-systemd,prune-backups,worker,inspect-state}
                        ...

Hosted server operations CLI

positional arguments:
  {healthcheck,backup,render-systemd,prune-backups,worker,inspect-state}
    healthcheck         Run hosted server health checks
    backup              Create a hosted registry backup set
    render-systemd      Render a hosted registry systemd deployment bundle
    prune-backups       Prune older hosted registry backup snapshots
    worker              Run the hosted registry worker loop
    inspect-state       Inspect hosted registry queue and release state

options:
  -h, --help            show this help message and exit
```

## `infinitas server healthcheck`

Status: `maintained`. Legacy shim deleted; use this canonical entrypoint directly.

```text
usage: infinitas server healthcheck [-h] --api-url API_URL --repo-path
                                    REPO_PATH --artifact-path ARTIFACT_PATH
                                    --database-url DATABASE_URL
                                    [--token TOKEN] [--json]

Hosted registry server health check

options:
  -h, --help            show this help message and exit
  --api-url API_URL     Hosted registry API base URL or /healthz URL
  --repo-path REPO_PATH
                        Path to the server-owned git checkout
  --artifact-path ARTIFACT_PATH
                        Path to the hosted artifact directory
  --database-url DATABASE_URL
                        Database URL, currently sqlite:///... only
  --token TOKEN         Reserved for future authenticated probes
  --json                Emit machine-readable JSON output
```

## `infinitas server backup`

Status: `maintained`. Legacy shim deleted; use this canonical entrypoint directly.

```text
usage: infinitas server backup [-h] --repo-path REPO_PATH --database-url
                               DATABASE_URL --artifact-path ARTIFACT_PATH
                               --output-dir OUTPUT_DIR [--label LABEL]
                               [--json]

Create a hosted registry backup set

options:
  -h, --help            show this help message and exit
  --repo-path REPO_PATH
                        Path to the server-owned git checkout
  --database-url DATABASE_URL
                        Database URL, currently sqlite:///... only
  --artifact-path ARTIFACT_PATH
                        Path to the hosted artifact directory
  --output-dir OUTPUT_DIR
                        Directory where backup snapshots should be created
  --label LABEL         Optional label appended to the backup directory name
  --json                Emit machine-readable JSON output
```

## `infinitas server inspect-state`

Status: `maintained`. Legacy shim deleted; use this canonical entrypoint directly.

```text
usage: infinitas server inspect-state [-h] --database-url DATABASE_URL
                                      [--limit LIMIT]
                                      [--max-queued-jobs MAX_QUEUED_JOBS]
                                      [--max-running-jobs MAX_RUNNING_JOBS]
                                      [--max-failed-jobs MAX_FAILED_JOBS]
                                      [--max-warning-jobs MAX_WARNING_JOBS]
                                      [--alert-webhook-url ALERT_WEBHOOK_URL]
                                      [--alert-fallback-file ALERT_FALLBACK_FILE]
                                      [--json]

Inspect hosted registry queue and release state

options:
  -h, --help            show this help message and exit
  --database-url DATABASE_URL
                        Database URL, currently sqlite:///... only
  --limit LIMIT         Number of recent jobs to include in detail lists
  --max-queued-jobs MAX_QUEUED_JOBS
                        Alert when queued job count exceeds this threshold
  --max-running-jobs MAX_RUNNING_JOBS
                        Alert when running job count exceeds this threshold
  --max-failed-jobs MAX_FAILED_JOBS
                        Alert when failed job count exceeds this threshold
  --max-warning-jobs MAX_WARNING_JOBS
                        Alert when jobs with WARNING log entries exceed this
                        threshold
  --alert-webhook-url ALERT_WEBHOOK_URL
                        Optional webhook URL for alert summary delivery
  --alert-fallback-file ALERT_FALLBACK_FILE
                        Optional file path for storing the latest alert
                        summary JSON
  --json                Emit machine-readable JSON output
```

## `infinitas server render-systemd`

Status: `maintained`. Legacy shim deleted; use this canonical entrypoint directly.

```text
usage: infinitas server render-systemd [-h] --output-dir OUTPUT_DIR
                                       --repo-root REPO_ROOT --python-bin
                                       PYTHON_BIN --env-file ENV_FILE
                                       [--service-prefix SERVICE_PREFIX]
                                       [--service-user SERVICE_USER]
                                       [--listen-host LISTEN_HOST]
                                       [--listen-port LISTEN_PORT]
                                       [--worker-poll-interval WORKER_POLL_INTERVAL]
                                       --backup-output-dir BACKUP_OUTPUT_DIR
                                       [--backup-on-calendar BACKUP_ON_CALENDAR]
                                       [--backup-label BACKUP_LABEL]
                                       [--mirror-remote MIRROR_REMOTE]
                                       [--mirror-branch MIRROR_BRANCH]
                                       [--mirror-on-calendar MIRROR_ON_CALENDAR]
                                       [--prune-on-calendar PRUNE_ON_CALENDAR]
                                       [--prune-keep-last PRUNE_KEEP_LAST]
                                       [--inspect-on-calendar INSPECT_ON_CALENDAR]
                                       [--inspect-limit INSPECT_LIMIT]
                                       [--inspect-max-queued-jobs INSPECT_MAX_QUEUED_JOBS]
                                       [--inspect-max-running-jobs INSPECT_MAX_RUNNING_JOBS]
                                       [--inspect-max-failed-jobs INSPECT_MAX_FAILED_JOBS]
                                       [--inspect-max-warning-jobs INSPECT_MAX_WARNING_JOBS]
                                       [--inspect-alert-webhook-url INSPECT_ALERT_WEBHOOK_URL]
                                       [--inspect-alert-fallback-file INSPECT_ALERT_FALLBACK_FILE]
                                       [--artifact-path ARTIFACT_PATH]
                                       [--database-url DATABASE_URL]
                                       [--repo-lock-path REPO_LOCK_PATH]

Render a hosted registry systemd deployment bundle

options:
  -h, --help            show this help message and exit
  --output-dir OUTPUT_DIR
                        Directory where rendered files will be written
  --repo-root REPO_ROOT
                        Hosted registry repository checkout path
  --python-bin PYTHON_BIN
                        Python binary used by the hosted services
  --env-file ENV_FILE   System path to the deployed environment file
  --service-prefix SERVICE_PREFIX
                        Prefix used for service names
  --service-user SERVICE_USER
                        User account that should run the hosted services
  --listen-host LISTEN_HOST
                        Host binding for the hosted API
  --listen-port LISTEN_PORT
                        Port binding for the hosted API
  --worker-poll-interval WORKER_POLL_INTERVAL
                        Worker poll interval in seconds
  --backup-output-dir BACKUP_OUTPUT_DIR
                        Directory where scheduled backups should be written
  --backup-on-calendar BACKUP_ON_CALENDAR
                        systemd OnCalendar expression for backups
  --backup-label BACKUP_LABEL
                        Backup label passed to the backup helper
  --mirror-remote MIRROR_REMOTE
                        Optional outward mirror remote; when set, render
                        mirror service and timer
  --mirror-branch MIRROR_BRANCH
                        Optional branch passed to the mirror helper; defaults
                        to current branch when omitted
  --mirror-on-calendar MIRROR_ON_CALENDAR
                        systemd OnCalendar expression for optional outward
                        mirroring
  --prune-on-calendar PRUNE_ON_CALENDAR
                        systemd OnCalendar expression for backup retention
                        pruning
  --prune-keep-last PRUNE_KEEP_LAST
                        How many newest backup directories the prune job
                        should keep
  --inspect-on-calendar INSPECT_ON_CALENDAR
                        systemd OnCalendar expression for queue inspection
                        runs
  --inspect-limit INSPECT_LIMIT
                        Number of recent rows included in each inspection run
  --inspect-max-queued-jobs INSPECT_MAX_QUEUED_JOBS
                        Alert when queued job count exceeds this threshold
  --inspect-max-running-jobs INSPECT_MAX_RUNNING_JOBS
                        Alert when running job count exceeds this threshold
  --inspect-max-failed-jobs INSPECT_MAX_FAILED_JOBS
                        Alert when failed job count exceeds this threshold
  --inspect-max-warning-jobs INSPECT_MAX_WARNING_JOBS
                        Alert when jobs with WARNING log entries exceed this
                        threshold
  --inspect-alert-webhook-url INSPECT_ALERT_WEBHOOK_URL
                        Optional webhook URL for scheduled inspect alert
                        delivery
  --inspect-alert-fallback-file INSPECT_ALERT_FALLBACK_FILE
                        Optional file path for storing the latest inspect
                        alert snapshot when webhook delivery is unavailable
  --artifact-path ARTIFACT_PATH
                        Override artifact path for the env template and backup
                        service
  --database-url DATABASE_URL
                        Override database URL for the env template and backup
                        service
  --repo-lock-path REPO_LOCK_PATH
                        Override repo lock path for the env template
```

## `infinitas server prune-backups`

Status: `maintained`. Legacy shim deleted; use this canonical entrypoint directly.

```text
usage: infinitas server prune-backups [-h] --backup-root BACKUP_ROOT
                                      --keep-last KEEP_LAST [--json]

Prune older hosted registry backup snapshots

options:
  -h, --help            show this help message and exit
  --backup-root BACKUP_ROOT
                        Directory containing hosted backup snapshot
                        directories
  --keep-last KEEP_LAST
                        How many newest recognized backup directories to keep
  --json                Emit machine-readable JSON output
```

## `infinitas server worker`

Status: `maintained`. Legacy shim deleted; use this canonical entrypoint directly.

```text
usage: infinitas server worker [-h] [--poll-interval POLL_INTERVAL] [--once]
                               [--limit LIMIT]

Run the hosted registry worker loop

options:
  -h, --help            show this help message and exit
  --poll-interval POLL_INTERVAL
                        Seconds to wait between empty queue polls
  --once                Drain the queue once and exit
  --limit LIMIT         Maximum jobs to process per loop iteration
```
