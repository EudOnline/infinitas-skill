---
audience: contributors, integrators, operators
owner: repository maintainers
source_of_truth: generated from argparse definitions in src/infinitas_skill
last_reviewed: 2026-04-07
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
usage: infinitas [-h]
                 {compatibility,release,install,discovery,openclaw,registry,policy,server}
                 ...

infinitas project CLI

positional arguments:
  {compatibility,release,install,discovery,openclaw,registry,policy,server}
    compatibility       Compatibility tools
    release             Release readiness, signing, and verification tools
    install             Install planning and workflow tools
    discovery           Discovery and inspection tools
    openclaw            OpenClaw runtime tools
    registry            Hosted registry control-plane tools
    policy              Policy validation and promotion tools
    server              Hosted server operations tools

options:
  -h, --help            show this help message and exit
```

## `infinitas compatibility check-platform-contracts`

```text
usage: infinitas compatibility check-platform-contracts [-h]
                                                        [--max-age-days MAX_AGE_DAYS]
                                                        [--stale-policy {warn,fail}]

Check platform contract-watch documents. OpenClaw is the maintained runtime
gate; other platform documents remain for migration and historical
verification.

options:
  -h, --help            show this help message and exit
  --max-age-days MAX_AGE_DAYS
                        Warn when Last verified is older than this many days.
  --stale-policy {warn,fail}
                        Whether over-age contract docs should warn or fail.
```

## `infinitas discovery`

```text
usage: infinitas discovery [-h] {search,recommend,inspect} ...

Discovery, recommendation, and inspection CLI

positional arguments:
  {search,recommend,inspect}
    search              Search generated discovery surfaces
    recommend           Recommend the best matching skill
    inspect             Inspect one released skill

options:
  -h, --help            show this help message and exit
```

## `infinitas discovery search`

```text
usage: infinitas discovery search [-h] [--publisher PUBLISHER] [--agent AGENT]
                                  [--tag TAG] [--repo-root REPO_ROOT] [--json]
                                  [query]

Search generated discovery surfaces

positional arguments:
  query                 Optional search query

options:
  -h, --help            show this help message and exit
  --publisher PUBLISHER
                        Filter by publisher
  --agent AGENT         Filter by target agent
  --tag TAG             Filter by tag
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas discovery recommend`

```text
usage: infinitas discovery recommend [-h] [--target-agent TARGET_AGENT]
                                     [--limit LIMIT] [--repo-root REPO_ROOT]
                                     [--json]
                                     task

Recommend the best matching skill

positional arguments:
  task                  Task or intent to rank against the discovery index

options:
  -h, --help            show this help message and exit
  --target-agent TARGET_AGENT
                        Optional target runtime/agent
  --limit LIMIT         Maximum ranked results to emit
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas discovery inspect`

```text
usage: infinitas discovery inspect [-h] [--version VERSION]
                                   [--target-agent TARGET_AGENT]
                                   [--repo-root REPO_ROOT] [--json]
                                   name

Inspect one released skill

positional arguments:
  name                  Qualified name or skill name

options:
  -h, --help            show this help message and exit
  --version VERSION     Optional version override
  --target-agent TARGET_AGENT
                        Optional target runtime/agent
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas install resolve-plan`

```text
usage: infinitas install resolve-plan [-h] [--skill-dir SKILL_DIR]
                                      [--registry-entry-json REGISTRY_ENTRY_JSON]
                                      [--target-dir TARGET_DIR]
                                      [--source-registry SOURCE_REGISTRY]
                                      [--source-json SOURCE_JSON]
                                      [--memory-mode MEMORY_MODE]
                                      [--mode {install,sync}] [--json]

Resolve an install or sync dependency plan

options:
  -h, --help            show this help message and exit
  --skill-dir SKILL_DIR
                        Skill directory to resolve from
  --registry-entry-json REGISTRY_ENTRY_JSON
                        Hosted registry entry JSON for object-aware install
                        planning
  --target-dir TARGET_DIR
                        Existing install target directory to plan against
  --source-registry SOURCE_REGISTRY
                        Registry hint for the root skill source
  --source-json SOURCE_JSON
                        Resolved source metadata JSON for the root skill
  --memory-mode MEMORY_MODE
                        Selected memory mode for agent_preset registry
                        installs
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

## `infinitas install resolve-skill`

```text
usage: infinitas install resolve-skill [-h] [--target-agent TARGET_AGENT]
                                       [--repo-root REPO_ROOT] [--json]
                                       query

Resolve one install candidate from the discovery index

positional arguments:
  query                 Skill name or qualified_name to resolve

options:
  -h, --help            show this help message and exit
  --target-agent TARGET_AGENT
                        Optional target runtime/agent
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas install exact`

```text
usage: infinitas install exact [-h] [--version VERSION] [--registry REGISTRY]
                               [--snapshot SNAPSHOT] [--force] [--no-deps]
                               [--repo-root REPO_ROOT] [--json]
                               name target_dir

Install one exact released skill and apply its dependency plan

positional arguments:
  name                  Skill name or qualified_name to install exactly
  target_dir            Target directory for the installed skill

options:
  -h, --help            show this help message and exit
  --version VERSION     Optional released version override
  --registry REGISTRY   Optional source registry override
  --snapshot SNAPSHOT   Optional registry snapshot selector
  --force               Overwrite the root target if the resolved plan needs
                        to replace it
  --no-deps             Fail instead of applying dependency installs or
                        upgrades
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas install by-name`

```text
usage: infinitas install by-name [-h] [--version VERSION]
                                 [--target-agent TARGET_AGENT]
                                 [--mode {auto,confirm}]
                                 [--repo-root REPO_ROOT] [--json]
                                 query target_dir

Resolve and install one released skill by discovery-first name lookup

positional arguments:
  query                 Skill name or qualified_name to install
  target_dir            Target directory for the installed skill

options:
  -h, --help            show this help message and exit
  --version VERSION     Optional released version override
  --target-agent TARGET_AGENT
                        Optional target runtime/agent
  --mode {auto,confirm}
                        Whether to install immediately or only confirm the
                        plan
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas install sync`

```text
usage: infinitas install sync [-h] [--force] [--repo-root REPO_ROOT] [--json]
                              installed_name target_dir

Sync one installed skill to the latest releasable state from its source

positional arguments:
  installed_name        Installed skill name or qualified_name
  target_dir            Target directory holding the installed skill

options:
  -h, --help            show this help message and exit
  --force               Bypass stale or never-verified readiness gates after
                        drift checks
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas install check-update`

```text
usage: infinitas install check-update [-h] [--repo-root REPO_ROOT] [--json]
                                      installed_name target_dir

Check whether an installed skill has a newer same-registry release

positional arguments:
  installed_name        Installed skill name or qualified_name
  target_dir            Target directory holding the install manifest

options:
  -h, --help            show this help message and exit
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas install switch`

```text
usage: infinitas install switch [-h] [--to-version TO_VERSION] [--to-active]
                                [--registry REGISTRY]
                                [--qualified-name QUALIFIED_NAME] [--force]
                                [--repo-root REPO_ROOT] [--json]
                                installed_name target_dir

Switch one installed skill to another releasable source revision

positional arguments:
  installed_name        Installed skill name or qualified_name
  target_dir            Target directory holding the installed skill

options:
  -h, --help            show this help message and exit
  --to-version TO_VERSION
                        Switch to an exact released version
  --to-active           Switch to the currently resolved active source instead
                        of an exact version
  --registry REGISTRY   Optional source registry override
  --qualified-name QUALIFIED_NAME
                        Optional qualified_name override
  --force               Bypass stale or never-verified readiness gates after
                        drift checks
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas install rollback`

```text
usage: infinitas install rollback [-h] [--steps STEPS] [--force]
                                  [--repo-root REPO_ROOT] [--json]
                                  installed_name target_dir

Rollback one installed skill to a recorded prior manifest entry

positional arguments:
  installed_name        Installed skill name or qualified_name
  target_dir            Target directory holding the installed skill

options:
  -h, --help            show this help message and exit
  --steps STEPS         How many history entries to walk back
  --force               Bypass stale or never-verified readiness gates after
                        drift checks
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas install upgrade`

```text
usage: infinitas install upgrade [-h] [--to-version TO_VERSION]
                                 [--registry REGISTRY] [--mode {auto,confirm}]
                                 [--force] [--repo-root REPO_ROOT] [--json]
                                 installed_name target_dir

Upgrade one installed skill in place from the recorded source registry

positional arguments:
  installed_name        Installed skill name or qualified_name
  target_dir            Target directory holding the installed skill

options:
  -h, --help            show this help message and exit
  --to-version TO_VERSION
                        Optional released version override
  --registry REGISTRY   Optional source registry override; cross-source
                        upgrade is rejected
  --mode {auto,confirm}
                        Whether to upgrade immediately or only confirm the
                        plan
  --force               Bypass stale/never-verified readiness gates after
                        drift checks
  --repo-root REPO_ROOT
                        Repository root containing generated catalog artifacts
  --json                Emit pretty JSON output
```

## `infinitas openclaw`

```text
usage: infinitas openclaw [-h] {profile,workspace,skill,plugin} ...

Inspect and validate the maintained OpenClaw runtime contract

positional arguments:
  {profile,workspace,skill,plugin}
    profile             Inspect the canonical OpenClaw runtime profile
    workspace           OpenClaw workspace resolution tools
    skill               OpenClaw skill validation tools
    plugin              OpenClaw plugin capability tools

options:
  -h, --help            show this help message and exit
```

## `infinitas openclaw profile`

```text
usage: infinitas openclaw profile [-h] [--json]

Inspect the canonical OpenClaw runtime profile

options:
  -h, --help  show this help message and exit
  --json      Print machine-readable output
```

## `infinitas openclaw workspace resolve`

```text
usage: infinitas openclaw workspace resolve [-h] [--home HOME] [--json]
                                            workspace_root

Resolve OpenClaw skill-directory precedence for one workspace

positional arguments:
  workspace_root  Workspace root to resolve skill directories for

options:
  -h, --help      show this help message and exit
  --home HOME     Override the home directory used for ~/ expansion
  --json          Print machine-readable output
```

## `infinitas openclaw skill validate`

```text
usage: infinitas openclaw skill validate [-h] [--json] skill_dir

Validate one skill directory against the OpenClaw runtime contract

positional arguments:
  skill_dir   Skill directory to validate against the OpenClaw contract

options:
  -h, --help  show this help message and exit
  --json      Print machine-readable output
```

## `infinitas openclaw plugin inspect`

```text
usage: infinitas openclaw plugin inspect [-h] [--json] plugin_path

Inspect and normalize declared OpenClaw plugin capabilities

positional arguments:
  plugin_path  Plugin JSON payload to inspect

options:
  -h, --help   show this help message and exit
  --json       Print machine-readable output
```

## `infinitas policy`

```text
usage: infinitas policy [-h]
                        {check-packs,check-promotion,recommend-reviewers,review-status}
                        ...

Policy validation and promotion CLI

positional arguments:
  {check-packs,check-promotion,recommend-reviewers,review-status}

options:
  -h, --help            show this help message and exit
```

## `infinitas policy check-packs`

```text
usage: infinitas policy check-packs [-h]

Validate policy-pack selector and active pack files

options:
  -h, --help  show this help message and exit
```

## `infinitas policy check-promotion`

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

## `infinitas policy recommend-reviewers`

```text
usage: infinitas policy recommend-reviewers [-h] [--as-active] [--stage STAGE]
                                            [--json]
                                            skill

Recommend reviewers and escalation paths for one skill

positional arguments:
  skill

options:
  -h, --help     show this help message and exit
  --as-active
  --stage STAGE
  --json
```

## `infinitas policy review-status`

```text
usage: infinitas policy review-status <skill-name-or-path> [--require-pass] [--as-active] [--stage STAGE] [--json] [--show-recommendations]

Show review gate status for one skill

positional arguments:
  skill

options:
  -h, --help            show this help message and exit
  --require-pass
  --as-active
  --stage STAGE
  --json
  --show-recommendations
```

## `infinitas registry`

```text
usage: infinitas registry [-h] [--base-url BASE_URL] [--token TOKEN]
                          {skills,drafts,agent-presets,agent-codes,releases,exposures,grants,tokens,reviews}
                          ...

Hosted registry private-first control plane CLI

positional arguments:
  {skills,drafts,agent-presets,agent-codes,releases,exposures,grants,tokens,reviews}
    skills              Manage private-first skill records
    drafts              Manage editable drafts and immutable version sealing
    agent-presets       Manage publishable agent preset objects
    agent-codes         Manage publishable agent code objects
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

## `infinitas registry skills`

```text
usage: infinitas registry skills [-h] [--base-url BASE_URL] [--token TOKEN]
                                 {create,get} ...

Manage private-first skill records

positional arguments:
  {create,get}
    create             Create a new skill namespace entry
    get                Fetch one skill by id

options:
  -h, --help           show this help message and exit
  --base-url BASE_URL  Hosted registry API base URL
  --token TOKEN        Bearer token for hosted registry API
```

## `infinitas registry drafts`

```text
usage: infinitas registry drafts [-h] [--base-url BASE_URL] [--token TOKEN]
                                 {create,update,seal} ...

Manage editable drafts and immutable version sealing

positional arguments:
  {create,update,seal}
    create              Create an editable draft for a skill
    update              Patch an open draft
    seal                Seal draft into an immutable skill version

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Hosted registry API base URL
  --token TOKEN         Bearer token for hosted registry API
```

## `infinitas registry agent-presets`

```text
usage: infinitas registry agent-presets [-h] [--base-url BASE_URL]
                                        [--token TOKEN]
                                        {create,create-draft,seal-draft} ...

Manage publishable agent preset objects

positional arguments:
  {create,create-draft,seal-draft}
    create              Create a new agent preset object
    create-draft        Create a draft payload for an agent preset
    seal-draft          Seal an agent preset draft

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Hosted registry API base URL
  --token TOKEN         Bearer token for hosted registry API
```

## `infinitas registry agent-codes`

```text
usage: infinitas registry agent-codes [-h] [--base-url BASE_URL]
                                      [--token TOKEN]
                                      {create,create-draft,seal-draft} ...

Manage publishable agent code objects

positional arguments:
  {create,create-draft,seal-draft}
    create              Create a new agent code object
    create-draft        Create an external-import draft for agent code
    seal-draft          Seal an agent code draft

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Hosted registry API base URL
  --token TOKEN         Bearer token for hosted registry API
```

## `infinitas registry releases`

```text
usage: infinitas registry releases [-h] [--base-url BASE_URL] [--token TOKEN]
                                   {create,get,artifacts} ...

Create and inspect immutable releases

positional arguments:
  {create,get,artifacts}
    create              Create or fetch a release for one skill version
    get                 Fetch one release by id
    artifacts           List artifacts for one release

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Hosted registry API base URL
  --token TOKEN         Bearer token for hosted registry API
```

## `infinitas registry exposures`

```text
usage: infinitas registry exposures [-h] [--base-url BASE_URL] [--token TOKEN]
                                    {create,update,activate,revoke} ...

Manage audience exposure and share policy

positional arguments:
  {create,update,activate,revoke}
    create              Create a new audience exposure for one release
    update              Patch share policy on an existing exposure
    activate            Activate an exposure
    revoke              Revoke an exposure

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Hosted registry API base URL
  --token TOKEN         Bearer token for hosted registry API
```

## `infinitas registry grants`

```text
usage: infinitas registry grants [-h] [--base-url BASE_URL] [--token TOKEN]
                                 {list,create-token,revoke} ...

Inspect grant policy scaffolding for token-scoped access

positional arguments:
  {list,create-token,revoke}
    list                Reserved command for upcoming grant listing APIs
    create-token        Reserved command for issuing grant tokens
    revoke              Reserved command for revoking a grant

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Hosted registry API base URL
  --token TOKEN         Bearer token for hosted registry API
```

## `infinitas registry tokens`

```text
usage: infinitas registry tokens [-h] [--base-url BASE_URL] [--token TOKEN]
                                 {me,check-release} ...

Inspect token identity and release authorization

positional arguments:
  {me,check-release}
    me                 Show the current access identity from the bearer token
    check-release      Check release access for the current credential

options:
  -h, --help           show this help message and exit
  --base-url BASE_URL  Hosted registry API base URL
  --token TOKEN        Bearer token for hosted registry API
```

## `infinitas registry reviews`

```text
usage: infinitas registry reviews [-h] [--base-url BASE_URL] [--token TOKEN]
                                  {open-case,get-case,decide} ...

Manage review cases for public-facing exposures

positional arguments:
  {open-case,get-case,decide}
    open-case           Open a review case for one exposure
    get-case            Fetch one review case by id
    decide              Record a review decision

options:
  -h, --help            show this help message and exit
  --base-url BASE_URL   Hosted registry API base URL
  --token TOKEN         Bearer token for hosted registry API
```

## `infinitas release`

```text
usage: infinitas release [-h]
                         {check-state,signing-readiness,doctor-signing,bootstrap-signing}
                         ...

Release CLI

positional arguments:
  {check-state,signing-readiness,doctor-signing,bootstrap-signing}

options:
  -h, --help            show this help message and exit
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

## `infinitas release signing-readiness`

```text
usage: infinitas release signing-readiness [-h] [--skill SKILL] [--json]

Report repository-level SSH signing readiness

options:
  -h, --help     show this help message and exit
  --skill SKILL  Skill name or path to inspect (repeatable, defaults to all
                 active skills)
  --json         Print machine-readable output
```

## `infinitas release doctor-signing`

```text
usage: infinitas release doctor-signing [-h] [--identity IDENTITY]
                                        [--provenance PROVENANCE] [--json]
                                        [skill]

Diagnose SSH signing bootstrap, release-tag readiness, and attestation
prerequisites

positional arguments:
  skill                 Skill name or path to diagnose

options:
  -h, --help            show this help message and exit
  --identity IDENTITY   Expected signer identity to use in fix suggestions
  --provenance PROVENANCE
                        Existing provenance JSON to verify
  --json                Print machine-readable doctor output
```

## `infinitas release bootstrap-signing`

```text
usage: infinitas release bootstrap-signing [-h]
                                           {init-key,add-allowed-signer,configure-git,authorize-publisher}
                                           ...

Bootstrap SSH signing and repository signer policy

positional arguments:
  {init-key,add-allowed-signer,configure-git,authorize-publisher}
    init-key            Generate a new SSH signing key pair
    add-allowed-signer  Add or update a trusted signer entry
    configure-git       Configure git to use SSH signing with a key path
    authorize-publisher
                        Authorize signer or releaser identities for a
                        publisher

options:
  -h, --help            show this help message and exit
```

## `infinitas server`

```text
usage: infinitas server [-h]
                        {healthcheck,backup,render-systemd,prune-backups,worker,inspect-state,memory-health,memory-curation,memory-observability,memory-baselines}
                        ...

Hosted server operations CLI

positional arguments:
  {healthcheck,backup,render-systemd,prune-backups,worker,inspect-state,memory-health,memory-curation,memory-observability,memory-baselines}
    healthcheck         Run hosted server health checks
    backup              Create a hosted registry backup set
    render-systemd      Render a hosted registry systemd deployment bundle
    prune-backups       Prune older hosted registry backup snapshots
    worker              Run the hosted registry worker loop
    inspect-state       Inspect hosted registry queue and release state
    memory-health       Inspect hosted registry memory writeback health
    memory-curation     Inspect hosted registry memory curation candidates
    memory-observability
                        Inspect hosted registry memory operations health
    memory-baselines    Inspect rolling memory baselines

options:
  -h, --help            show this help message and exit
```

## `infinitas server healthcheck`

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
                                       [--curation-on-calendar CURATION_ON_CALENDAR]
                                       [--curation-action {archive,prune}]
                                       [--curation-max-actions CURATION_MAX_ACTIONS]
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
  --curation-on-calendar CURATION_ON_CALENDAR
                        Optional systemd OnCalendar expression for scheduled
                        memory curation enqueue
  --curation-action {archive,prune}
                        Action scheduled memory curation should enqueue
  --curation-max-actions CURATION_MAX_ACTIONS
                        Maximum candidates each scheduled memory curation run
                        should touch
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
