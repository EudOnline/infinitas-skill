# Server-Hosted Private Skill Registry Design

Date: 2026-03-13

## Goal

Design the next operating model for `infinitas-skill` so the registry can run as a **server-hosted private skill platform** instead of requiring GitHub and local clones as the primary operating surface.

The design must support:

1. a server-owned source of truth
2. small-team collaboration
3. Web and CLI entrypoints
4. private distribution without cloning the full repository
5. controlled review and release governance
6. signed, immutable release artifacts for Claude, Codex, and OpenClaw

## User-validated design decisions

This design reflects the following decisions already established in discussion:

- The operator wants the registry to be deployable on a server, not only consumed through GitHub.
- The server should become the **single source of truth**.
- GitHub should remain a **mirror / backup target**, not the operational authority.
- The expected user group is a **small team** rather than a single-user workstation or a multi-organization SaaS.
- The operating model should be **Web + CLI**: humans should have a browser UI, while agents and automation should use APIs or a CLI.
- Governance should be **half-strict**:
  - regular contributors may submit and request review
  - maintainers may approve and may directly publish
- Consumers on other machines should be able to install released skills **without cloning the full repository**.
- The existing governance and release chain in this repository should be preserved wherever practical:
  - review gates
  - promotion rules
  - signed tags
  - provenance
  - distribution manifests
  - compatibility evidence

## Problem statement

The current repository already has a strong internal lifecycle:

- author under `skills/incubating/`
- validate with local scripts
- request / approve review
- promote to `skills/active/`
- release immutable bundles and provenance
- install from generated catalogs

That model is strong enough for a disciplined local registry, but it still assumes that the operator or another machine has local filesystem access to a cloned checkout. That creates three problems:

1. **distribution friction**
   - install clients still rely on a local registry checkout or cache
   - other machines cannot treat the registry as a hosted product surface
2. **submission friction**
   - contributors need repository-level git access and local knowledge of repository structure
   - Web-native contribution and review are missing
3. **operational coupling to GitHub**
   - the repo is mirrored there, but GitHub still feels like the practical center of gravity
   - that is the opposite of a self-hosted private registry platform

The design goal is to preserve the existing repository’s strongest properties while moving the system boundary from “a Git repo with scripts” to “a hosted registry platform powered by a Git repo”.

## Scope and non-goals

### In scope

- a server-hosted source of truth
- hosted API and Web UI
- CLI access for automation and agents
- release artifact distribution over HTTPS
- server-side review, promotion, and publish execution
- GitHub mirroring and backup strategy
- role-based access control, signer isolation, and auditable release actions

### Out of scope for the first design pass

- public marketplace behavior as the default workflow
- multi-tenant organization boundaries
- real-time collaborative editing
- arbitrary user code execution inside the UI
- automatic public `clawhub publish`
- replacing the current immutable release model

## Reuse surface from the current repository

The best path is to **reuse the current supply-chain logic** instead of replacing it.

The hosted system should continue to treat these current repository features as canonical implementation primitives:

- `scripts/check-skill.sh`
- `scripts/build-catalog.sh`
- `scripts/request-review.sh`
- `scripts/approve-skill.sh`
- `scripts/review-status.py`
- `scripts/promote-skill.sh`
- `scripts/publish-skill.sh`
- `scripts/release-skill.sh`
- `scripts/doctor-signing.py`
- `scripts/verify-attestation.py`
- generated release outputs under `catalog/`

The hosted platform therefore should not invent a second review or release system. It should provide a safer and more convenient control plane that drives the existing one.

## Core design decision

The recommended architecture is:

**Server-owned Git registry + database-backed control plane + worker-executed release pipeline + HTTPS artifact distribution + GitHub mirror**

In practice, this means:

- the server keeps the only writable Git repository used for normal operation
- the database tracks submissions, reviews, jobs, users, and audit logs
- workers mutate the repository and invoke existing scripts
- release artifacts are published to a stable HTTPS distribution surface
- GitHub becomes a downstream mirror and disaster-recovery asset

Rejected alternatives:

- **Keep GitHub as the true source of truth and bolt on a UI:** lowers operational control and preserves the current dependency on GitHub semantics.
- **Store skills only in a database and export Git later:** throws away too much of the existing repository’s proven governance and release chain.
- **Let both the server and GitHub stay writable:** creates conflict, ambiguity, and supply-chain drift.

## Design principles

### 1. Server ownership must be unambiguous

There must be exactly one writable source of truth for daily operations. In this design, that is the hosted registry on the server.

### 2. Git remains authoritative for content; the database remains authoritative for interaction state

Skill content, release artifacts, and generated catalogs remain Git-traceable. Submissions, task logs, user roles, review comments, and job orchestration live in the database.

### 3. Workers, not users, mutate the repository

The API must not directly rewrite files in-place. The API creates jobs. Workers perform:

- repository checkout / locking
- validation
- promotion
- release
- artifact publication
- mirror sync

### 4. Runtime installation must use immutable artifacts

Install clients should resolve from:

- hosted `ai-index.json`
- hosted `distributions.json`
- hosted manifest + bundle + provenance

They must not require a working clone of the registry repository.

### 5. Release signing must remain isolated

Maintainers may authorize publish jobs, but only a controlled release executor may use the configured signer identity.

### 6. Hosted convenience must not weaken review or provenance guarantees

The Web UI and CLI should make submission and release easier, not looser.

## Architecture overview

The system should be treated as six cooperating components.

### 1. `registry-api`

Responsibilities:

- authenticate users
- authorize operations by role
- expose skills, submissions, reviews, releases, and install metadata
- accept submission uploads or structured edits
- enqueue validate / review / publish jobs
- expose download URLs and installation metadata

Recommended implementation: a Python monolith API with HTML endpoints for the Web UI plus JSON endpoints for CLI/automation.

### 2. `registry-worker`

Responsibilities:

- pull queued jobs from the database
- acquire repository locks
- write incoming submissions into the server-owned Git repo
- invoke existing validation, review, promotion, publish, and catalog scripts
- sync release artifacts to the distribution surface
- push mirror updates to GitHub

This worker is the only process allowed to mutate the source-of-truth repository.

### 3. `registry-repo`

Responsibilities:

- store `skills/`, `catalog/`, `policy/`, `config/`, `scripts/`, and documentation
- persist generated release bundles and provenance
- preserve diffability, rollback, and auditability

This repository remains structurally close to the current repo so existing scripts continue to work with minimal change.

### 4. `registry-db`

Responsibilities:

- users and roles
- sessions or API tokens
- submissions and review records
- background jobs and logs
- audit events
- installation and download telemetry

This database is not a replacement for Git; it is the interaction and orchestration layer.

### 5. `artifact-store`

Responsibilities:

- publish immutable artifacts and catalog views over HTTPS
- expose:
  - `ai-index.json`
  - `distributions.json`
  - `compatibility.json`
  - per-version manifests
  - bundles
  - provenance and signatures

The first deployment may use filesystem-backed storage plus Nginx-style static serving. A later deployment may move to object storage without changing the artifact contract.

### 6. `github-mirror`

Responsibilities:

- receive one-way pushes from the server-owned repository
- serve as a human-readable backup and recovery input
- never become the operational write authority

## Operational state model

The recommended business-level lifecycle is:

`draft -> incubating -> in_review -> approved -> active -> released`

Interpretation:

- `draft`: submission exists in the hosted platform but is not yet reviewable
- `incubating`: content is materialized in the registry repo under `skills/incubating/`
- `in_review`: the submission has an active review request
- `approved`: review state is sufficient for promotion or release
- `active`: the governed skill is promoted into active use
- `released`: immutable artifacts, provenance, and catalogs have been published

Important nuance:

- `active` is a repository governance state
- `released` is a distribution state

The hosted platform must not collapse those into one button without preserving the distinction internally.

## Roles and permission model

The recommended minimum roles are:

### `viewer`

- read skills, versions, compatibility, and release history
- download published artifacts if authorized

### `contributor`

- create or edit drafts
- upload skill payloads, references, and assets
- run validation
- request review

### `maintainer`

- approve or reject submissions
- promote approved skills
- trigger publish jobs
- manage stable release cadence

### `release-admin`

- manage signer policy and release infrastructure
- manage registry configuration
- rotate tokens, keys, and mirror settings
- operate disaster recovery procedures

## Submission model

Both Web and CLI should terminate in the same internal object: a **submission**.

A submission represents a mutable work item that may contain:

- a target skill identity
- structured metadata edits
- Markdown instructions
- assets / references
- validation results
- review state
- job history

This allows the server to support:

- Web-authored skills
- uploaded local skill directories
- repeated edits before review
- review feedback loops without losing history

The API should not treat a raw Git push as the primary authoring primitive.

## Review and publish workflow

The half-strict governance model should work like this:

### Contributor flow

1. create or update a submission
2. run validation
3. request review
4. wait for maintainer action

### Maintainer flow

1. inspect diff, metadata, smoke content, and validation logs
2. approve or reject the submission
3. optionally promote
4. optionally publish

### Worker flow

When a publish job is approved, the worker should:

1. verify role authorization and policy prerequisites
2. ensure repository cleanliness and repository lock ownership
3. update the server-owned repo
4. run review / promotion checks
5. invoke existing publish / release helpers
6. refresh catalogs
7. sync release artifacts to the artifact store
8. mirror the repository to GitHub
9. record job logs and audit events

This keeps existing repo governance intact while making the trigger surface safe and convenient.

## Hosted distribution model

The hosted platform should expose immutable release artifacts over stable HTTPS paths.

Recommended path model:

```text
/registry/ai-index.json
/registry/distributions.json
/registry/compatibility.json
/registry/skills/<publisher>/<skill>/<version>/manifest.json
/registry/skills/<publisher>/<skill>/<version>/skill.tar.gz
/registry/provenance/<skill>-<version>.json
/registry/provenance/<skill>-<version>.json.ssig
```

That path model maps directly onto the current catalog and distribution structure while removing the need for a client-side Git clone.

Install clients should:

1. fetch `ai-index.json`
2. resolve the requested skill and version
3. fetch manifest + bundle + provenance
4. verify sha256 and attestation
5. install into the target runtime directory

This is already conceptually compatible with the current `immutable-only` install policy; the hosted platform simply turns local file references into remote registry URLs.

## Registry source model change

The current registry source system supports `git` and `local` sources. Hosted distribution requires a new source class in the next phase:

- `http`

An `http` registry entry should describe:

- base URL
- trust tier
- token or auth mode
- expected host allowlist
- catalog endpoints
- artifact verification policy

This allows install clients to consume a hosted registry without maintaining a local repository cache.

## Web and CLI interaction model

The platform should support two human/agent entry modes:

### Web UI

Primary for:

- browsing skills and releases
- creating or editing submissions
- requesting review
- approving or rejecting changes
- triggering publish jobs
- viewing logs and audit records

### CLI / API

Primary for:

- local author workflows
- agent automation
- CI-style scripted operations
- remote installation from the hosted registry

The recommended CLI model is an API-backed control tool rather than raw Git access. It may coexist with existing repo-local scripts during migration.

## Security and signing model

Release signing is the most sensitive part of the hosted platform.

The recommended model is:

- maintainers can request publication
- only the server-side release executor can use the signer identity
- signer material should live in a restricted secret store or locked-down filesystem path
- release jobs should execute under a dedicated system user
- the worker should enforce publisher / releaser policy before invoking release commands

This preserves the current attestation and provenance guarantees while making release centrally manageable.

## Audit model

The platform should maintain two complementary audit surfaces.

### Control-plane audit

Stored in the database:

- who created a submission
- who edited it
- who requested review
- who approved or rejected
- who triggered publish
- what job ran and what it changed

### Supply-chain audit

Stored in Git and release artifacts:

- version
- tag
- provenance
- signature
- bundle sha256
- compatibility evidence

This separation is important because operational troubleshooting and consumer-facing verification are not the same concern.

## Data model overview

The minimum durable entities are:

- `users`
- `skills`
- `submissions`
- `reviews`
- `releases`
- `artifacts`
- `jobs`
- `audit_logs`

Design rule:

- Git stores content truth
- the database stores orchestration truth

Neither should try to fully replace the other.

## GitHub mirror and backup strategy

GitHub should become a downstream system with three functions:

1. read-only human visibility
2. off-server repository backup
3. disaster recovery input

The mirror must be one-way:

- server -> GitHub
- never GitHub -> server by default

Recovery must rely on three preserved surfaces:

1. server-owned Git repository backup
2. database backup
3. artifact-store backup

GitHub alone is not enough to restore the full hosted system because review state, jobs, and audit trails live outside Git.

## Recommended deployment topology

For a small-team self-hosted deployment, the recommended first production shape is:

- reverse proxy: Nginx / Caddy
- app process: `registry-api`
- worker process: `registry-worker`
- database: SQLite for the earliest MVP, but designed for an easy move to PostgreSQL
- artifact storage: local filesystem behind the reverse proxy
- source-of-truth repo: local server path
- mirror target: GitHub
- backups: scheduled snapshots of repo + db + artifacts

This topology keeps the first production deployment simple without blocking future upgrades.

## Rollout phases

### Phase 1: Hosted distribution without clone dependency

Deliver:

- remote `http` registry source support
- hosted catalog and artifact endpoints
- install clients that pull from hosted artifacts

This removes the biggest current friction for consumers on other machines.

### Phase 2: Hosted control plane

Deliver:

- users / roles
- submissions
- review queue
- job queue
- Web UI
- API-backed CLI

This makes the platform operationally useful for the team.

### Phase 3: Hardened release operations

Deliver:

- isolated signer execution
- GitHub mirroring
- backup and restore automation
- richer audit and observability

This makes the platform trustworthy as a long-term operational home.

## Success criteria

The design is successful when the following become true:

1. another machine can install `lvxiaoer/operate-infinitas-skill` without cloning the full repository
2. a contributor can submit a new skill through Web or CLI without raw Git access to the source-of-truth repo
3. a maintainer can approve and publish through the hosted platform without bypassing review or provenance policy
4. the resulting release still produces signed tags, provenance, distribution manifests, and compatibility evidence
5. GitHub can disappear temporarily without blocking normal team operation
6. GitHub can still restore repository history if the server must be rebuilt

## Recommended next step

The next implementation should begin with the **hosted distribution layer** rather than the full Web stack.

Reason:

- it solves the current installation pain first
- it preserves the existing release chain
- it creates the remote artifact contract that both Web and CLI will rely on later
- it keeps phase 1 surgical instead of turning the whole project into a platform rewrite
