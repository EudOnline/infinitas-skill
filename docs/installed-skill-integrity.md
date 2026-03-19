# Installed Skill Integrity

Installed skills are not trusted just because they were once installed from a verified distribution manifest. Local runtime files can still drift afterward through manual edits, partial copy failures, or accidental overwrite.

The installed-integrity workflow extends v15's signed `file_manifest` into the local runtime directory:

1. read the installed entry from `.infinitas-skill-install-manifest.json`
2. re-verify the recorded immutable distribution manifest and attestation
3. compare the installed local files against the signed released-file inventory
4. report whether the runtime copy is still trustworthy

## Commands

Verify one installed skill:

```bash
python3 scripts/verify-installed-skill.py my-skill ~/.openclaw/skills --json
```

Repair one drifted install back to its recorded immutable source:

```bash
scripts/repair-installed-skill.sh my-skill ~/.openclaw/skills
```

## Integrity States

- `verified`: the installed local files still match the signed released-file inventory recorded by the immutable distribution source
- `drifted`: one or more local files are missing, modified, or unexpected compared with the signed released-file inventory
- `repaired`: not a persisted steady-state value; it describes the action where `repair-installed-skill.sh` restores the install and the follow-up verification returns `verified`
- `unknown`: the install manifest does not yet carry enough immutable source metadata to compare local files against a signed released-file inventory

For legacy immutable releases, `unknown` is often a manifest-shape problem instead of an install problem. After backfilling the referenced distribution manifest in place, the same installed runtime copy can move to `verified` without reinstalling:

```bash
python3 scripts/backfill-distribution-manifests.py --manifest <distribution-manifest> --write --json
python3 scripts/verify-installed-skill.py <name> <target-dir> --json
```

## Drift Report

`verify-installed-skill.py --json` reports additive arrays for:

- `modified_files`
- `missing_files`
- `unexpected_files`

It also reports compact summary counters such as:

- `release_file_manifest_count`
- `checked_file_count`
- `modified_count`
- `missing_count`
- `unexpected_count`

This keeps both humans and wrappers on the same contract without scraping stdout text.

## Repair Workflow

When a skill is `drifted`, prefer repair over silent overwrite:

1. run `python3 scripts/verify-installed-skill.py <name> <target-dir> --json`
2. inspect the reported drift paths
3. run `scripts/repair-installed-skill.sh <name> <target-dir>`
4. verify again to confirm the state is back to `verified`

`repair-installed-skill.sh` is exact-source and manifest-driven:

- it reuses the recorded `source_qualified_name`
- it reuses the recorded `source_registry`
- it prefers the recorded `locked_version` or installed version
- it restores the same immutable release rather than guessing the latest available version

## Guardrails

Mutation commands such as:

- `scripts/sync-skill.sh`
- `scripts/upgrade-skill.sh`
- `scripts/rollback-installed-skill.sh`

now stop on detected drift and point operators to `verify-installed-skill.py` or `repair-installed-skill.sh`.

Use `--force` only when you intentionally want to overwrite the local runtime copy despite detected drift.

## Trust Boundary

The workflow remains offline-verifiable and manifest-driven:

- it does not require a hosted control plane
- it does not trust mutable working-tree folders as the verification source
- it relies on the immutable distribution manifest and signed attestation already recorded in the local install manifest

For hosted installs, the toolchain now persists the fetched immutable distribution artifacts under a target-local cache root and records that root in the install manifest. Later explicit verification reuses that cached immutable set rather than resolving back through a mutable repo checkout copy.

If the install lacks those immutable references, the integrity state remains `unknown` until the skill is reinstalled, repaired from a verified immutable source, or the referenced legacy distribution manifest is backfilled.
