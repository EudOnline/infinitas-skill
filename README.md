# infinitas-skill

Private skill registry for Claude Code, Codex, and OpenClaw.

This repository is meant to hold private skills, templates, helper scripts, and review guidance for skills that should not live in a public repository. The MVP goal is simple: make skills easy to create, validate, promote, install, and sync across multiple personal agents without turning the repo into an uncontrolled prompt dump.

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
├─ compatibility.json    agent/tool compatibility view
├─ registries.json       configured registry sources view
└─ provenance/           generated release provenance records

docs/
├─ conventions.md        naming, layout, lifecycle rules
├─ lifecycle.md          incubating → active → archived flow
├─ metadata-schema.md    required `_meta.json` fields
├─ release-checklist.md  pre-publish / pre-promote review list
├─ release-strategy.md   version bump, changelog, and git tag guidance
├─ history-and-snapshots.md active overwrite snapshots and exact ancestry
├─ compatibility-matrix.md generated compatibility catalog guide
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
├─ release-skill-tag.sh  print or create a skill/<name>/v<version> git tag
├─ release-skill.sh      check, tag, prepare release notes, and write provenance
├─ lineage-diff.sh       diff a skill against its declared ancestor
├─ switch-installed-skill.sh switch an installed copy to active or a historical version
├─ rollback-installed-skill.sh rollback using manifest history
├─ resolve-skill-source.py resolve active vs archived skill sources
├─ resolve-install-plan.py preflight deterministic dependency resolution plans
├─ list-registry-sources.py list configured registry sources
├─ check-registry-sources.py validate multi-registry source config
├─ sync-registry-source.sh sync one configured git registry into cache
├─ sync-all-registries.sh sync all enabled git registries
├─ check-registry-integrity.py validate dependency refs and graph integrity
├─ check-promotion-policy.py enforce active-skill promotion policy
├─ request-review.sh     mark a skill under review and log the request
├─ review-status.py      summarize current computed approval quorum status
├─ approve-skill.sh      record reviewer approvals or rejections
├─ sign-provenance.py    sign provenance bundles with an HMAC key
├─ verify-provenance.py  verify signed provenance bundles
├─ sign-provenance-ssh.sh sign provenance bundles with SSH keys
├─ verify-provenance-ssh.sh verify SSH-signed provenance bundles
└─ diff-skill.sh         compare two skill folders or names

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

# Install a stable skill into an OpenClaw-managed local skills dir and lock it to the current version
scripts/install-skill.sh my-skill ~/.openclaw/skills --version 0.2.0

# Later, install an exact historical version from archived snapshots
scripts/install-skill.sh my-skill ~/.openclaw/skills --version 0.1.0 --force

# Snapshot the current active copy before a risky overwrite
scripts/snapshot-active-skill.sh my-skill --label pre-refactor

# Prepare a release summary and signed provenance (and optionally tag it)
scripts/release-skill.sh my-skill --write-provenance --sign-provenance
# or with SSH signing
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

## CI

GitHub Actions runs `scripts/check-all.sh` on pushes and pull requests. That validation currently covers:

- `_meta.json` shape and required fields
- stage/status consistency
- smoke test presence
- secret scan
- deterministic catalog generation
- compatibility catalog generation
- computed review-group quorum enforcement

If CI fails because catalog files changed, run:

```bash
scripts/build-catalog.sh
```

and commit the updated `catalog/*.json`.

## Registry model

- **Repo is source-of-truth**. Runtime still happens from a local skills directory.
- **Incubating is where experiments land**. Agents can contribute here.
- **Active is curated**. Only reviewed skills should be promoted here.
- **Archived keeps history**. Don't delete lineage unless you mean it.
- **`SKILL.md` is runtime-facing**. `_meta.json` is registry/governance-facing.
- **`CHANGELOG.md` tracks skill evolution**. Use it with semantic version bumps and optional git tags.
- **Install targets keep a manifest**. Local skill directories can now record what was installed, from where, and at which version.
- **Installs can be version-locked**. Sync now refuses to silently advance a locked install beyond the pinned active version.
- **Active overwrites can snapshot history**. You can archive an active skill before replacing it and later diff lineage against the exact archived ancestor.
- **Historical installs are supported**. Versioned installs can resolve archived snapshots instead of only whatever happens to be active now.
- **Installed copies can switch or roll back**. Manifest history now supports controlled source switching and version rollback.
- **Compatibility is exported**. Consumers can read a generated compatibility matrix instead of scraping every `_meta.json`.
- **Registry sources are policy-driven**. Source registries now declare trust, allowed hosts/refs, pinning, and update behavior in config.
- **Local-only self catalogs stay stable**. Committed catalog snapshots intentionally omit live `self` commit/tag identity so `check-all.sh` does not fail after every local commit; use `scripts/list-registry-sources.py` for the current checkout identity.
- **Dependencies and conflicts are first-class**. Skills can declare exact or ranged constraints plus optional registry hints in `depends_on` / `conflicts_with`.
- **Install and sync are plan-driven**. Both commands now print a deterministic dependency plan before mutating the target directory.
- **Unsafe upgrades fail early**. Dependency locks, reverse conflicts, and unresolved cross-registry requests are rejected before files are copied.
- **Promotion is policy-driven**. Active skills now pass a dedicated promotion policy check instead of relying only on ad-hoc conventions.
- **Computed review state is authoritative**. `_meta.json.review_state` is kept for compatibility, but promotion and catalog data now derive from `reviews.json` plus repository policy.
- **Reviewer groups and quorum are enforced**. Promotion policy can require configured reviewer groups, stage/risk-specific quorum, and rejection-free latest decisions.
- **Releases can emit signed provenance**. Release tooling can write machine-readable provenance records and sign/verify them.

## Safety rules

- Keep the repository private.
- Do not commit API keys, tokens, cookies, SSH keys, auth exports, or raw credential files.
- Review generated content before every push.
- Treat private repos as private collaboration space, not as a secret manager.
- Do not allow agents to auto-promote or auto-distribute unreviewed skills.
