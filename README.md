# infinitas-skill

Private skill registry for Claude Code, Codex, and OpenClaw.

This repository is meant to hold private skills, templates, helper scripts, and review guidance for skills that should not live in a public repository. The MVP goal is simple: make skills easy to create, validate, promote, install, and sync across multiple personal agents without turning the repo into an uncontrolled prompt dump.

The current release/install model supports both:

- local or Git-backed registry sources for operators working inside the repository
- hosted HTTP registry sources for consumers that should install immutable artifacts without cloning the full repository

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
├─ release-checklist.md  pre-publish / pre-promote review list
├─ release-strategy.md   version bump, changelog, and git tag guidance
├─ signing-bootstrap.md  first trusted signer setup and doctor flow
├─ distribution-manifests.md verified bundles, manifests, and immutable install flow
├─ history-and-snapshots.md active overwrite snapshots and exact ancestry
├─ compatibility-matrix.md generated compatibility catalog guide
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
├─ verify-attestation.py verify release attestations against repo-managed SSH signers
└─ diff-skill.sh         compare two skill folders or names

server/
├─ app.py                FastAPI entrypoint for the hosted control plane
├─ auth.py               bearer-token auth helpers for hosted APIs
├─ db.py                 SQLAlchemy engine + session wiring
├─ models.py             users, submissions, reviews, and jobs tables
├─ settings.py           env-driven hosted server configuration
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
scripts/publish-skill.sh my-skill
scripts/pull-skill.sh my-skill ~/.openclaw/skills
scripts/import-openclaw-skill.sh ~/.openclaw/workspace/skills/my-skill --owner lvxiaoer
scripts/export-openclaw-skill.sh my-skill --version 1.2.3 --out /tmp/openclaw-export

# Hosted control plane preview
uv run python scripts/test-hosted-api.py
uv run uvicorn server.app:app --reload
```

## Hosted registry control plane preview

The repository now includes a minimal hosted control plane under `server/` for the server-owned registry model. The first scaffold includes:

- `GET /healthz` for readiness
- `GET /` for a lightweight HTML dashboard
- `GET /login` for auth bootstrap guidance
- `GET /api/v1/me` for bearer-token identity checks

The hosted server uses SQLite by default and can be configured with:

- `INFINITAS_SERVER_DATABASE_URL`
- `INFINITAS_SERVER_SECRET_KEY`
- `INFINITAS_SERVER_BOOTSTRAP_USERS` (JSON array of `{username, display_name, role, token}`)

## AI Protocol

For AI-driven publishing, import, export, and installation, treat the following files as the machine-facing contract:

- `docs/ai/agent-operations.md` — agent-facing common operations manual
- `docs/ai/discovery.md` — private-first discovery, install-by-name, and upgrade contract
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
- compatibility regression coverage for legacy metadata, install-manifest, lock, snapshot, and bare-name resolution behavior
- discovery-index, name-resolution, install-by-name, and source-aware upgrade regression coverage
- signing config and allowed-signer validation
- computed review-group quorum enforcement
- publisher namespace / transfer regression checks
- stable release invariant regression checks
- asymmetric attestation regression checks
- signing bootstrap / doctor rehearsal regression checks

If CI fails because catalog files changed, run:

```bash
scripts/build-catalog.sh
```

and commit the updated `catalog/*.json`.

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
- **Release actor decisions are auditable**. Machine-readable release outputs now record author, reviewers, releaser, signer, and namespace-policy context.
- **Attestations capture dependency and registry context**. Release provenance now records the consulted registries, their resolved identity, and the dependency resolution plan used for the released skill.
- **Legacy HMAC sidecars remain optional only**. `sign-provenance.py` / `verify-provenance.py` still work for compatibility, but repo-managed SSH attestation is the trusted verification path.

## Safety rules

- Keep the repository private.
- Do not commit API keys, tokens, cookies, SSH keys, auth exports, or raw credential files.
- Review generated content before every push.
- Treat private repos as private collaboration space, not as a secret manager.
- Do not allow agents to auto-promote or auto-distribute unreviewed skills.
