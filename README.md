# infinitas-skill

Private skill registry for Claude Code, Codex, and OpenClaw.

This repository is meant to hold private skills, templates, helper scripts, and review guidance for skills that should not live in a public repository. The MVP goal is simple: make skills easy to create, validate, promote, install, and sync across multiple personal agents without turning the repo into an uncontrolled prompt dump.

The current release/install model supports both:

- local or Git-backed registry sources for operators working inside the repository
- hosted HTTP registry sources for consumers that should install immutable artifacts without cloning the full repository

Policy composition now also supports ordered repository policy packs via `policy/policy-packs.json`, with repository-local policy files remaining the final override layer for compatibility. Shared team scopes can now be declared in `policy/team-policy.json` and referenced from namespace or review policy without duplicating membership lists.
Policy-aware validation, promotion, and release checks now also expose additive `policy_trace` diagnostics in JSON mode, with registry validation returning structured `validation_errors`, and optional `--debug-policy` text rendering for operator troubleshooting.

Project status: `infinitas-skill` is complete on `main` and currently operates in steady-state. See `docs/project-closeout.md` for the maintained verification matrix and accepted maintenance notes.

## Recommended workflow

1. Scaffold a new skill from a template
2. Build it under `skills/incubating/`
3. Fill in `SKILL.md`, `_meta.json`, and `tests/smoke.md`
4. Validate it with `scripts/check-skill.sh`
5. Rebuild the catalog with `scripts/build-catalog.sh`
6. Verify computed review quorum with `scripts/review-status.py`
7. Promote approved skills into `skills/active/`
7. Install or sync stable skills into agent-local skill directories

## Repository layout

```text
catalog/
├─ catalog.json          machine-readable index for all skills
├─ active.json           install-focused index for active skills only
├─ compatibility.json    declared + verified compatibility view
├─ compatibility-evidence/ per-platform verification evidence records
├─ registries.json       configured registry sources view
├─ distributions.json    immutable distribution manifest index
├─ provenance/           generated release provenance records
└─ distributions/        released bundles + verified manifest payloads

docs/
├─ conventions.md        naming, layout, lifecycle rules
├─ lifecycle.md          incubating → active → archived flow
├─ metadata-schema.md    required `_meta.json` fields
├─ policy-packs.md       ordered policy-pack loading and override rules
├─ release-checklist.md  pre-publish / pre-promote review list
├─ release-strategy.md   version bump, changelog, and git tag guidance
├─ signing-bootstrap.md  first trusted signer setup and doctor flow
├─ distribution-manifests.md verified bundles, manifests, and immutable install flow
├─ history-and-snapshots.md active overwrite snapshots and exact ancestry
├─ compatibility-matrix.md generated compatibility catalog guide
├─ ai/search-and-inspect.md search, inspect, trust, and explanation-first consumer flow
├─ platform-contracts/   per-platform contract-watch documents
├─ multi-registry.md     source registry configuration and trust model
├─ promotion-policy.md   promotion rules for active skills
├─ review-workflow.md    request/approval flow for skill promotion
└─ trust-model.md        safety model for shared skill evolution

scripts/
├─ new-skill.sh          scaffold a new skill folder from a template
├─ check-skill.sh        validate skill metadata + secret scan
├─ build-catalog.sh      regenerate catalog JSON files
├─ install-skill.sh      copy an active skill into a local skills dir
├─ sync-skill.sh         refresh an installed skill from the registry
├─ list-installed.sh     inspect install manifest data for a target dir
├─ promote-skill.sh      move a quorum-approved incubating skill into active/
├─ snapshot-active-skill.sh archive a timestamped copy of an active skill
├─ bump-skill-version.sh bump semver and seed changelog entries
├─ release-skill-tag.sh  print, create, sign, and optionally push a skill/<name>/v<version> git tag
├─ check-release-state.py verify clean-tree, upstream-sync, and signed-tag release invariants
├─ bootstrap-signing.py  create or wire SSH signing identities into repo policy
├─ doctor-signing.py     explain signer, tag, and attestation readiness blockers
├─ release-skill.sh      verify stable release state, tag, prepare release notes, write provenance, and emit immutable bundles
├─ generate-distribution-manifest.py create a verified manifest from a signed attestation payload
├─ verify-distribution-manifest.py verify bundle + manifest + attestation consistency
├─ lineage-diff.sh       diff a skill against its declared ancestor
├─ switch-installed-skill.sh switch an installed copy to active or a historical version
├─ rollback-installed-skill.sh rollback using manifest history
├─ resolve-skill-source.py resolve active vs archived skill sources
├─ resolve-install-plan.py preflight deterministic dependency resolution plans
├─ list-registry-sources.py list configured registry sources
├─ check-registry-sources.py validate multi-registry source config
├─ check-policy-packs.py validate policy pack selection and referenced packs
├─ check-signing-config.py validate signing policy and allowed signer wiring
├─ sync-registry-source.sh sync one configured git registry into cache
├─ sync-all-registries.sh sync all enabled git registries
├─ check-registry-integrity.py validate dependency refs and graph integrity
├─ check-promotion-policy.py enforce active-skill promotion policy
├─ request-review.sh     mark a skill under review and log the request
├─ review-status.py      summarize current computed approval quorum status
├─ approve-skill.sh      record reviewer approvals or rejections
├─ sign-provenance.py    sign provenance bundles with a legacy HMAC sidecar
├─ verify-provenance.py  verify legacy HMAC provenance sidecars
├─ sign-provenance-ssh.sh sign provenance bundles with SSH keys
├─ verify-provenance-ssh.sh verify SSH-signed provenance bundles
├─ verify-attestation.py verify release attestations against repo-managed SSH/CI policy
├─ verify-ci-attestation.py verify CI-native release attestation payloads
└─ diff-skill.sh         compare two skill folders or names

server/
├─ app.py                FastAPI entrypoint for the hosted control plane
├─ auth.py               bearer-token auth helpers for hosted APIs
├─ artifact_ops.py       hosted catalog / bundle sync helpers
├─ db.py                 SQLAlchemy engine + session wiring
├─ jobs.py               queue helpers and job serialization
├─ models.py             users, submissions, reviews, and jobs tables
├─ repo_ops.py           locked repo mutation helpers for worker jobs
├─ settings.py           env-driven hosted server configuration
├─ worker.py             sequential hosted validate / promote / publish worker
└─ templates/            lightweight hosted control plane HTML pages

skills/
├─ incubating/           work in progress
├─ active/               ready-to-use skills
└─ archived/             deprecated or historical skills

templates/
├─ basic-skill/          minimal starting point
├─ scripted-skill/       for skills that rely on helper scripts
└─ reference-heavy-skill/ for skills with larger reference docs
```

## Quick start

```bash
# Create a new incubating skill from the basic template
scripts/new-skill.sh my-skill basic

# Or scaffold a publisher-qualified skill while preserving legacy unqualified compatibility
scripts/new-skill.sh lvxiaoer/my-skill basic

# Validate a skill folder
scripts/check-skill.sh skills/incubating/my-skill

# Rebuild the install/search catalog
scripts/build-catalog.sh

# Validate ordered policy packs and effective local policy overlays
python3 scripts/check-policy-packs.py

# Inspect machine-readable policy traces when promotion, validation, or release checks are blocked
python3 scripts/check-promotion-policy.py --json --as-active skills/active/operate-infinitas-skill
python3 scripts/check-release-state.py operate-infinitas-skill --json
python3 scripts/validate-registry.py --json

# Run the full local validation suite
scripts/check-all.sh

# Bump a skill version and seed a changelog entry
scripts/bump-skill-version.sh my-skill patch --note "Refined the workflow"

# Request review, record reviewer decisions, verify quorum, then promote
scripts/request-review.sh my-skill --note "Ready for active"
scripts/approve-skill.sh my-skill --reviewer lvxiaoer --decision approved --note "Looks good"
scripts/review-status.py my-skill --as-active --require-pass
scripts/promote-skill.sh my-skill

# Preview or apply the deterministic dependency plan for an install
scripts/resolve-install-plan.py --skill-dir skills/active/my-skill --target-dir ~/.openclaw/skills

# Resolve an installable skill by short name
scripts/resolve-skill.sh my-skill

# Search the discovery catalog before resolving or installing
scripts/search-skills.sh operate
scripts/search-skills.sh --publisher lvxiaoer --agent codex

# Ask for the best fit when the task is clearer than the exact skill name
scripts/recommend-skill.sh "Need a codex skill for repository operations"

# Inspect trust state, compatibility, dependencies, and provenance first
scripts/inspect-skill.sh lvxiaoer/my-skill

# Install by name from the private-first discovery layer
scripts/install-by-name.sh my-skill ~/.openclaw/skills

# Check whether an installed skill has a newer stable version
scripts/check-skill-update.sh my-skill ~/.openclaw/skills

# Upgrade an installed skill from its recorded source
scripts/upgrade-skill.sh my-skill ~/.openclaw/skills

# Install a stable skill into an OpenClaw-managed local skills dir and lock it to the current version
scripts/install-skill.sh my-skill ~/.openclaw/skills --version 0.2.0

# Qualified names also resolve cleanly when a publisher namespace is declared
scripts/install-skill.sh lvxiaoer/my-skill ~/.openclaw/skills --version 0.2.0

# Later, install an exact historical version from archived snapshots
scripts/install-skill.sh my-skill ~/.openclaw/skills --version 0.1.0 --force

# Snapshot the current active copy before a risky overwrite
scripts/snapshot-active-skill.sh my-skill --label pre-refactor

# Preview release notes before tagging
scripts/release-skill.sh my-skill --preview

# Bootstrap the first trusted release signer
python3 scripts/bootstrap-signing.py init-key --identity lvxiaoer --output ~/.ssh/infinitas-skill-release-signing
python3 scripts/bootstrap-signing.py add-allowed-signer --identity lvxiaoer --key ~/.ssh/infinitas-skill-release-signing
python3 scripts/bootstrap-signing.py configure-git --key ~/.ssh/infinitas-skill-release-signing
python3 scripts/bootstrap-signing.py authorize-publisher --publisher lvxiaoer --signer lvxiaoer --releaser lvxiaoer
python3 scripts/doctor-signing.py my-skill

# Create, push, and verify the default signed release tag
scripts/release-skill.sh my-skill --push-tag

# Confirm the repository is release-ready
scripts/check-release-state.py my-skill

# Write immutable release notes and provenance from the pushed signed tag
scripts/release-skill.sh my-skill --notes-out /tmp/my-skill-release.md --write-provenance --releaser lvxiaoer
# verify the resulting attestation bundle against repo-managed signers
scripts/verify-attestation.py catalog/provenance/my-skill-1.2.3.json
python3 scripts/verify-ci-attestation.py catalog/provenance/my-skill-1.2.3.ci.json
python3 scripts/doctor-signing.py my-skill --provenance catalog/provenance/my-skill-1.2.3.json
python3 scripts/verify-distribution-manifest.py catalog/distributions/_legacy/my-skill/1.2.3/manifest.json
# optional legacy HMAC sidecars still work after the SSH attestation is verified
scripts/release-skill.sh my-skill --write-provenance --sign-provenance
scripts/release-skill.sh my-skill --write-provenance --ssh-sign-provenance --ssh-key ~/.ssh/id_ed25519

# Switch an installed copy to a different historical version
scripts/switch-installed-skill.sh my-skill ~/.openclaw/skills --to-version 0.1.0 --force

# Roll back using manifest history
scripts/rollback-installed-skill.sh my-skill ~/.openclaw/skills --force

# View the install manifest for that target directory
scripts/list-installed.sh ~/.openclaw/skills

# List configured registry sources and their resolved commit/tag
scripts/list-registry-sources.py

# Safe local-only sync for the self registry
scripts/sync-registry-source.sh self
```

# AI-first publish and pull wrappers
scripts/search-skills.sh operate
scripts/recommend-skill.sh "Need a codex skill for repository operations"
scripts/inspect-skill.sh lvxiaoer/my-skill
scripts/publish-skill.sh my-skill
scripts/pull-skill.sh my-skill ~/.openclaw/skills
scripts/import-openclaw-skill.sh ~/.openclaw/workspace/skills/my-skill --owner lvxiaoer
scripts/export-openclaw-skill.sh my-skill --version 1.2.3 --out /tmp/openclaw-export

# Hosted control plane preview
uv run python scripts/test-hosted-api.py
uv run uvicorn server.app:app --reload
python scripts/server-healthcheck.py --api-url http://127.0.0.1:8000 --repo-path /srv/infinitas/repo --artifact-path /srv/infinitas/artifacts --database-url sqlite:////srv/infinitas/data/server.db --json
python scripts/backup-hosted-registry.py --repo-path /srv/infinitas/repo --artifact-path /srv/infinitas/artifacts --database-url sqlite:////srv/infinitas/data/server.db --output-dir /srv/infinitas/backups --label nightly
python scripts/prune-hosted-backups.py --backup-root /srv/infinitas/backups --keep-last 7 --json
python scripts/rehearse-hosted-restore.py --backup-dir /srv/infinitas/backups/20260314T010000Z-nightly --output-dir /tmp/infinitas-restore-drill --json
python scripts/inspect-hosted-state.py --database-url sqlite:////srv/infinitas/data/server.db --limit 10 --max-queued-jobs 10 --max-running-jobs 2 --max-failed-jobs 0 --max-warning-jobs 0 --alert-webhook-url https://ops.example/hooks/infinitas --alert-fallback-file /var/lib/infinitas/alerts/latest-inspect-alert.json --json
python scripts/render-hosted-systemd.py --output-dir /tmp/infinitas-systemd --repo-root /srv/infinitas/repo --python-bin /srv/infinitas/.venv/bin/python --env-file /etc/infinitas/hosted-registry.env --service-prefix infinitas-hosted --backup-output-dir /srv/infinitas/backups --backup-on-calendar daily --backup-label nightly --prune-on-calendar daily --prune-keep-last 7 --inspect-on-calendar hourly --inspect-limit 10 --inspect-max-queued-jobs 10 --inspect-max-running-jobs 2 --inspect-max-failed-jobs 0 --inspect-max-warning-jobs 0 --inspect-alert-webhook-url https://ops.example/hooks/infinitas --inspect-alert-fallback-file /var/lib/infinitas/alerts/latest-inspect-alert.json
python scripts/render-hosted-systemd.py --output-dir /tmp/infinitas-systemd --repo-root /srv/infinitas/repo --python-bin /srv/infinitas/.venv/bin/python --env-file /etc/infinitas/hosted-registry.env --service-prefix infinitas-hosted --backup-output-dir /srv/infinitas/backups --backup-on-calendar daily --backup-label nightly --mirror-remote github-mirror --mirror-branch main --mirror-on-calendar daily --prune-on-calendar daily --prune-keep-last 7 --inspect-on-calendar hourly --inspect-limit 10 --inspect-max-queued-jobs 10 --inspect-max-running-jobs 2 --inspect-max-failed-jobs 0 --inspect-max-warning-jobs 0 --inspect-alert-webhook-url https://ops.example/hooks/infinitas --inspect-alert-fallback-file /var/lib/infinitas/alerts/latest-inspect-alert.json
# hosted installers should target the built-in distribution surface, not the app root
# example registry base_url: https://skills.example.com/registry

# Mirror the hosted source-of-truth repo outward only
scripts/mirror-registry.sh --remote github-mirror --dry-run

# Run the hosted end-to-end publish -> serve -> install rehearsal
uv run python scripts/test-hosted-registry-e2e.py
```

## Hosted registry control plane preview

The repository now includes a minimal hosted control plane under `server/` for the server-owned registry model. The first scaffold includes:

- `GET /healthz` for readiness
- `GET /` for a lightweight HTML dashboard
- `GET /login` plus `POST /api/auth/login` / `POST /api/auth/logout` for browser auth bootstrap
- `GET /api/auth/me` for cookie-backed browser session probing
- `GET /api/v1/me` for bearer-token identity checks
- `GET /submissions`, `GET /reviews`, and `GET /jobs` for maintainer-only operator views
- `GET /api/v1/submissions`, `GET /api/v1/reviews`, and `GET /api/v1/jobs` for JSON list inspection

The hosted server uses SQLite by default and can be configured with:

- `INFINITAS_SERVER_DATABASE_URL`
- `INFINITAS_SERVER_SECRET_KEY`
- `INFINITAS_SERVER_BOOTSTRAP_USERS` (JSON array of `{username, display_name, role, token}`)
- `INFINITAS_SERVER_REPO_PATH`
- `INFINITAS_SERVER_ARTIFACT_PATH`
- optional `INFINITAS_REGISTRY_READ_TOKENS` (JSON array; when set, `/registry/*` requires one of these bearer tokens)
- optional `INFINITAS_SERVER_MIRROR_REMOTE`
- optional `INFINITAS_SERVER_MIRROR_BRANCH`

Hosted submission and review APIs are documented in `docs/ai/server-api.md`. The matching CLI wrapper is `scripts/registryctl.py`, which talks to the hosted API instead of editing repository state directly. The hosted HTML pages now also support cookie-backed browser sessions backed by the same token primitive.
Operational runbooks live in `docs/ops/server-deployment.md` and `docs/ops/server-backup-and-restore.md`.
Phase 1 hosted ops automation now includes:

- `scripts/server-healthcheck.py` to verify `/healthz`, repo checkout presence, artifact directory shape, and SQLite connectivity
- `scripts/backup-hosted-registry.py` to create a point-in-time repo bundle + SQLite copy + artifact tarball backup set
- `scripts/prune-hosted-backups.py` to keep only the newest recognized hosted backup snapshots under the backup root
- `scripts/rehearse-hosted-restore.py` to validate a backup set by cloning and extracting it into a staging directory
- `scripts/inspect-hosted-state.py` to summarize queue depth, failed jobs, and submission status counts from the hosted DB, with optional threshold-based non-zero exits
- `scripts/inspect-hosted-state.py` also surfaces warning-bearing jobs so best-effort publish-hook issues are visible to scheduled inspection
- `scripts/inspect-hosted-state.py` can optionally POST alert summaries to a webhook when alert thresholds are breached
- `scripts/inspect-hosted-state.py` can also write the latest alert summary to a stable fallback file when webhook delivery is unavailable
- `scripts/render-hosted-systemd.py` to generate a `systemd` deployment bundle for the API, worker, scheduled backup/prune/inspect timers, plus an optional one-way mirror timer when `--mirror-remote` is provided
- `scripts/run-hosted-worker.py` to provide a stable long-running worker entrypoint for the generated worker service
- `Dockerfile`, `docker-compose.yml`, and `.env.compose.example` to run the hosted control plane in containers from a published image, while auto-seeding the runtime repo into a persistent host directory
- `.github/workflows/container-image.yml` to build multi-arch container images and publish them to GHCR on `main` and version tags

The hosted app now also serves immutable install artifacts directly from `/registry/*`, including:

- `/registry/ai-index.json`
- `/registry/distributions.json`
- `/registry/compatibility.json`
- `/registry/discovery-index.json`
- `/registry/skills/<publisher>/<skill>/<version>/manifest.json`
- `/registry/skills/<publisher>/<skill>/<version>/skill.tar.gz`
- `/registry/provenance/<skill>-<version>.json`
- `/registry/provenance/<skill>-<version>.json.ssig`

The built-in hosted surface also preserves legacy `catalog/` artifact paths under `/registry/catalog/...` so older generated manifest refs continue to install cleanly.

For hosted operators, `scripts/registryctl.py` now supports read-only inspection commands in addition to workflow mutations:

```bash
python scripts/registryctl.py --base-url http://127.0.0.1:8000 --token dev-maintainer-token submissions list
python scripts/registryctl.py --base-url http://127.0.0.1:8000 --token dev-maintainer-token reviews list
python scripts/registryctl.py --base-url http://127.0.0.1:8000 --token dev-maintainer-token jobs list
```

These ops helpers are intentionally SQLite-first for the current single-node deployment model. PostgreSQL and object-storage automation remain future extensions.
If `INFINITAS_SERVER_MIRROR_REMOTE` is configured, hosted publish jobs also attempt an immediate best-effort one-way mirror push after syncing artifacts and pushing the primary repo.

## Container deployment

The repository now ships a production-oriented container image path for the hosted registry:

- `Dockerfile` packages the FastAPI app, worker entrypoints, ops scripts, and hosted templates
- `docker-compose.yml` runs the API and worker from the image itself, then bootstraps a writable runtime repo into `.deploy/repo` on first start
- `.env.compose.example` seeds the required compose/runtime environment
- `.github/workflows/container-image.yml` builds `linux/amd64` and `linux/arm64` images, publishes them to `ghcr.io/<owner>/infinitas-skill`, and keeps PR builds pushless

The key deployment boundary is unchanged: the container image runs the control plane, but `INFINITAS_SERVER_REPO_PATH` still becomes the writable source-of-truth git checkout that publish jobs validate, mutate, and push. The difference is that compose now seeds that checkout from the image snapshot on first boot instead of requiring a manual `git clone`.

Typical compose flow:

```bash
cp .env.compose.example .env.compose
mkdir -p .deploy/{repo,data,artifacts,backups,home}

# Optional: set INFINITAS_SERVER_GIT_ORIGIN_URL in .env.compose
# Optional: place .gitconfig / .ssh under .deploy/home for git push + mirror auth

docker compose --env-file .env.compose run --rm init-repo
docker compose --env-file .env.compose pull
docker compose --env-file .env.compose up -d app worker
docker compose --env-file .env.compose --profile ops run --rm inspect
```

The shared entrypoint now seeds `.deploy/repo` into a local git worktree from the bundled image snapshot when that directory is empty, configures `origin` when `INFINITAS_SERVER_GIT_ORIGIN_URL` is set, and syncs `catalog/` into `INFINITAS_SERVER_ARTIFACT_PATH` before the API or worker starts.
For the full compose runbook, backup/prune/mirror commands, and credential layout guidance, see `docs/ops/server-deployment.md`.

## AI Protocol

For AI-driven publishing, import, export, and installation, treat the following files as the machine-facing contract:

- `docs/ai/agent-self-serve.md` — agent 自助部署、hosted 运维、registry 使用手册
- `docs/ai/agent-operations.md` — agent-facing common operations manual
- `docs/ai/usage-guide.md` — stable high-level guide for when to search, recommend, inspect, publish, pull, and verify
- `docs/ai/workflow-drills.md` — search, recommend, inspect, publish, and pull drills that stay on public docs plus generated JSON surfaces
- `docs/ai/discovery.md` — private-first discovery, install-by-name, and upgrade contract
- `docs/ai/recommend.md` — recommendation workflow, ranking factors, and recommendation explanations
- `docs/ai/search-and-inspect.md` — search, inspect, trust state, compatibility, provenance, and explanation-first consumer workflow
- `docs/ai/hosted-registry.md` — hosted registry endpoints, auth, and immutable download contract
- `docs/ai/openclaw.md` — OpenClaw / ClawHub bridge contract
- `docs/ai/publish.md` — protocol for `scripts/publish-skill.sh`
- `docs/ai/pull.md` — protocol for `scripts/pull-skill.sh`

The default AI execution model is autonomous, but the contract also supports `--mode confirm` for non-mutating plan output. AI installation is immutable-only: agents must resolve installable versions from published release artifacts, not from `skills/active/` or `skills/incubating/`.

## OpenClaw workflows

- **Private default**: OpenClaw local prototype → `scripts/import-openclaw-skill.sh` → review / release → `scripts/pull-skill.sh ~/.openclaw/skills`
- **Public optional**: release first → `scripts/export-openclaw-skill.sh --out <dir>` → manual `clawhub publish <dir>/<skill>`
- **Do not skip release**: AI must not install directly from editable source folders when serving OpenClaw runtime installs

## CI

GitHub Actions runs `scripts/check-all.sh` on pushes and pull requests. That validation currently covers:

- `_meta.json` shape and required fields
- stage/status consistency
- smoke test presence
- secret scan
- deterministic catalog generation
- compatibility catalog generation
- hosted registry container image builds on pull requests, `main`, and `v*` tags through `.github/workflows/container-image.yml`
- compatibility regression coverage for legacy metadata, install-manifest, lock, snapshot, and bare-name resolution behavior
- discovery-index, name-resolution, install-by-name, and source-aware upgrade regression coverage
- signing config and allowed-signer validation
- computed review-group quorum enforcement
- publisher namespace / transfer regression checks
- stable release invariant regression checks
- asymmetric attestation regression checks
- signing bootstrap / doctor rehearsal regression checks
- hosted end-to-end publish / serve / install coverage when the Python environment includes the hosted control plane dependencies

If CI fails because catalog files changed, run:

```bash
scripts/build-catalog.sh
```

and commit the updated `catalog/*.json`.

CI now installs the `pyproject.toml` dependencies and requires hosted end-to-end coverage to pass.

For the same local bootstrap path, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install .
python3 scripts/test-hosted-registry-e2e.py
```

If you want hosted control plane coverage in a minimal environment, install the `pyproject.toml` dependencies first or run with a prepared tool like `uv`. To force failure instead of skipping when those dependencies are missing, set `INFINITAS_REQUIRE_HOSTED_E2E_TESTS=1`.

## Compatibility Contract

Compatibility-sensitive repository behavior is documented in `docs/compatibility-contract.md`.

Use that document as the source of truth for:

- stable vs soft compatibility surfaces
- schema-version expectations for `_meta.json` and install manifests
- deprecation windows for persisted state
- migration and regression-test expectations
- migration commands: `scripts/migrate-skill-meta.py` and `scripts/migrate-install-manifest.py`
- declared support vs verified support compatibility reporting
- compatibility evidence recorded separately from author declarations

## Compatibility pipeline

- Author intent is still declared in `_meta.json.agent_compatible` or canonical `skills-src/*/skill.json` metadata.
- Platform adapters render generated outputs under `build/` or export targets via `scripts/export-codex-skill.sh`, `scripts/export-claude-skill.sh`, and `scripts/export-openclaw-skill.sh`.
- Platform-specific verification evidence lives under `catalog/compatibility-evidence/<platform>/<skill>/<version>.json`.
- Use `python3 scripts/record-verified-support.py <skill> --platform codex --platform claude --platform openclaw --build-catalog` to record fresh evidence from the real export/check pipeline after a stable release exists.
- `catalog/compatibility.json` now separates `declared_support` from `verified_support` while preserving the legacy top-level `agents` view.
- Contract-watch docs in `docs/platform-contracts/` record stable assumptions, volatile assumptions, official sources, and the last manual verification date for Claude, Codex, and OpenClaw.
- Run `python3 scripts/check-platform-contracts.py --max-age-days 30` to spot stale platform assumptions before claiming compatibility.

## Registry model

- **Repo is source-of-truth**. Runtime still happens from a local skills directory.
- **Hosted server can own writes**. The control plane can mutate a server-owned checkout and publish immutable artifacts without clients cloning the whole repository.
- **Incubating is where experiments land**. Agents can contribute here.
- **Active is curated**. Only reviewed skills should be promoted here.
- **Archived keeps history**. Don't delete lineage unless you mean it.
- **`SKILL.md` is runtime-facing**. `_meta.json` is registry/governance-facing.
- **Publishers are first-class**. `_meta.json` can now declare `publisher`, `qualified_name`, `owners`, and `author`.
- **Legacy names still work**. Existing unqualified `skill` references remain valid while `publisher/skill` disambiguates ownership-sensitive flows.
- **`CHANGELOG.md` tracks skill evolution**. Use it with semantic version bumps and optional git tags.
- **Install targets keep a manifest**. Local skill directories can now record what was installed, from where, and at which version.
- **Installs can be version-locked**. Sync now refuses to silently advance a locked install beyond the pinned active version.
- **Active overwrites can snapshot history**. You can archive an active skill before replacing it and later diff lineage against the exact archived ancestor.
- **Historical installs are supported**. Versioned installs can resolve archived snapshots instead of only whatever happens to be active now.
- **Installed copies can switch or roll back**. Manifest history now supports controlled source switching and version rollback.
- **Stable releases emit verified bundles and manifests**. Catalog exports now index immutable release bundles under `catalog/distributions/` plus `catalog/distributions.json`.
- **Install and sync prefer immutable release artifacts**. When a verified distribution manifest exists, resolver/install/sync materialize from that manifest instead of relying only on the live working-tree folder.
- **Consumer discovery is search-first**. `scripts/search-skills.sh` filters the generated discovery surface by query, publisher, agent, and tag without scraping source paths.
- **Recommendation is task-first**. `scripts/recommend-skill.sh` ranks candidate skills using trust state, compatibility, maturity, quality, and verification freshness when the user describes a job instead of an exact skill name.
- **AI workflow drills are confirm-first**. Start with [docs/ai/workflow-drills.md](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules/docs/ai/workflow-drills.md) when an agent needs a realistic search, recommend, inspect, publish, or pull playbook without opening implementation internals.
- **Inspect before install**. `scripts/inspect-skill.sh` exposes trust state, compatibility summaries, dependency summaries, provenance references, and the verified distribution manifest path as a stable JSON view.
- **Resolver and upgrade payloads explain policy**. `scripts/resolve-skill.sh`, `scripts/install-by-name.sh`, `scripts/check-skill-update.sh`, and `scripts/upgrade-skill.sh` now emit additive `explanation` fields with `selection_reason`, `policy_reasons`, and `version_reason`.
- **Compatibility is exported**. Consumers can read a generated compatibility matrix instead of scraping every `_meta.json`.
- **Namespace ownership is policy-driven**. `policy/namespace-policy.json` declares valid publishers plus approved namespace transfers.
- **Registry sources are policy-driven**. Source registries now declare trust, allowed hosts/refs, pinning, and update behavior in config.
- **Local-only self catalogs stay stable**. Committed catalog snapshots intentionally omit live `self` commit/tag identity so `check-all.sh` does not fail after every local commit; use `scripts/list-registry-sources.py` for the current checkout identity.
- **Dependencies and conflicts are first-class**. Skills can declare exact or ranged constraints plus optional registry hints in `depends_on` / `conflicts_with`.
- **Install and sync are plan-driven**. Both commands now print a deterministic dependency plan before mutating the target directory.
- **Unsafe upgrades fail early**. Dependency locks, reverse conflicts, and unresolved cross-registry requests are rejected before files are copied.
- **Promotion is policy-driven**. Active skills now pass a dedicated promotion policy check instead of relying only on ad-hoc conventions.
- **Computed review state is authoritative**. `_meta.json.review_state` is kept for compatibility, but promotion and catalog data now derive from `reviews.json` plus repository policy.
- **Reviewer groups and quorum are enforced**. Promotion policy can require configured reviewer groups, stage/risk-specific quorum, and rejection-free latest decisions.
- **Stable releases require signed pushed tags**. Release notes and provenance now resolve against a verified `refs/tags/skill/<name>/v<version>` snapshot instead of best-effort `HEAD` state.
- **Release attestations are authoritative under v9 policy**. Any written release artifact must be accompanied by a verified SSH attestation generated from the immutable release snapshot.
- **CI-native attestation is now available for Phase 4**. `.github/workflows/release-attestation.yml` can generate a CI-side attestation payload, and repo policy can require `ssh`, `ci`, or `both`.
- **Release actor decisions are auditable**. Machine-readable release outputs now record author, reviewers, releaser, signer, and namespace-policy context.
- **Attestations capture dependency and registry context**. Release provenance now records the consulted registries, their resolved identity, and the dependency resolution plan used for the released skill.
- **Legacy HMAC sidecars remain optional only**. `sign-provenance.py` / `verify-provenance.py` still work for compatibility, but repo-managed SSH attestation is the trusted verification path.
- **GitHub is a mirror, not an authority**. Hosted deployments may push outward with `scripts/mirror-registry.sh`, but must not reverse-sync GitHub back into the server-owned repo.

## Safety rules

- Keep the repository private.
- Do not commit API keys, tokens, cookies, SSH keys, auth exports, or raw credential files.
- Review generated content before every push.
- Treat private repos as private collaboration space, not as a secret manager.
- Do not allow agents to auto-promote or auto-distribute unreviewed skills.
