# infinitas-skill

Private skill registry for Claude Code, Codex, and OpenClaw.

This repository is meant to hold private skills, templates, helper scripts, and review guidance for skills that should not live in a public repository. The MVP goal is simple: make skills easy to create, validate, promote, install, and sync across multiple personal agents without turning the repo into an uncontrolled prompt dump.

## Recommended workflow

1. Scaffold a new skill from a template
2. Build it under `skills/incubating/`
3. Fill in `SKILL.md`, `_meta.json`, and `tests/smoke.md`
4. Validate it with `scripts/check-skill.sh`
5. Rebuild the catalog with `scripts/build-catalog.sh`
6. Promote approved skills into `skills/active/`
7. Install or sync stable skills into agent-local skill directories

## Repository layout

```text
catalog/
├─ catalog.json          machine-readable index for all skills
└─ active.json           install-focused index for active skills only

docs/
├─ conventions.md        naming, layout, lifecycle rules
├─ lifecycle.md          incubating → active → archived flow
├─ metadata-schema.md    required `_meta.json` fields
├─ release-checklist.md  pre-publish / pre-promote review list
├─ release-strategy.md   version bump, changelog, and git tag guidance
├─ history-and-snapshots.md active overwrite snapshots and exact ancestry
└─ trust-model.md        safety model for shared skill evolution

scripts/
├─ new-skill.sh          scaffold a new skill folder from a template
├─ check-skill.sh        validate skill metadata + secret scan
├─ build-catalog.sh      regenerate catalog JSON files
├─ install-skill.sh      copy an active skill into a local skills dir
├─ sync-skill.sh         refresh an installed skill from the registry
├─ list-installed.sh     inspect install manifest data for a target dir
├─ promote-skill.sh      move an approved incubating skill into active/
├─ snapshot-active-skill.sh archive a timestamped copy of an active skill
├─ bump-skill-version.sh bump semver and seed changelog entries
├─ release-skill-tag.sh  print or create a skill/<name>/v<version> git tag
├─ lineage-diff.sh       diff a skill against its declared ancestor
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

# Promote a reviewed skill
scripts/promote-skill.sh my-skill

# Install a stable skill into an OpenClaw-managed local skills dir and lock it to the active version
scripts/install-skill.sh my-skill ~/.openclaw/skills --version 0.2.0

# Snapshot the current active copy before a risky overwrite
scripts/snapshot-active-skill.sh my-skill --label pre-refactor

# Print the release tag you would use (or create it with --create)
scripts/release-skill-tag.sh my-skill

# View the install manifest for that target directory
scripts/list-installed.sh ~/.openclaw/skills
```

## CI

GitHub Actions runs `scripts/check-all.sh` on pushes and pull requests. That validation currently covers:

- `_meta.json` shape and required fields
- stage/status consistency
- smoke test presence
- secret scan
- deterministic catalog generation

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

## Safety rules

- Keep the repository private.
- Do not commit API keys, tokens, cookies, SSH keys, auth exports, or raw credential files.
- Review generated content before every push.
- Treat private repos as private collaboration space, not as a secret manager.
- Do not allow agents to auto-promote or auto-distribute unreviewed skills.
