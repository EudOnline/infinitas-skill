# Discovery and Install Protocol

## Commands

```bash
scripts/resolve-skill.sh <name> [--target-agent <agent>]
scripts/install-by-name.sh <name> <target-dir> [--version <semver>] [--target-agent <agent>] [--mode auto|confirm]
scripts/check-skill-update.sh <installed-name> <target-dir>
scripts/upgrade-skill.sh <installed-name> <target-dir> [--to-version <semver>] [--registry <name>] [--mode auto|confirm]
```

## Resolution policy

- search the private registry first via `catalog/discovery-index.json`
- if the private registry has one clear compatible match, it wins
- if the private registry has multiple plausible matches, return `ambiguous`
- only search configured external registries when the private registry has no suitable match
- discovery is index-driven; it must not inspect mutable source trees as an install shortcut

## Confirmation rules

- external-only matches require confirmation before auto-install
- `install-by-name.sh --mode confirm` may plan an external install, but must not mutate the target directory
- `check-skill-update.sh` is non-mutating
- `upgrade-skill.sh` must stay on the recorded source registry unless the caller explicitly decides to reinstall from a different source

## Output JSON

`resolve-skill.sh` returns states such as:

- `resolved-private`
- `resolved-external`
- `ambiguous`
- `not-found`
- `incompatible`

`install-by-name.sh` returns:

```json
{
  "ok": true,
  "query": "spreadsheet",
  "qualified_name": "lvxiaoer/spreadsheet",
  "source_registry": "self",
  "requested_version": null,
  "resolved_version": "1.2.3",
  "target_dir": "/path/to/skills",
  "manifest_path": "/path/to/skills/.infinitas-skill-install-manifest.json",
  "state": "installed",
  "requires_confirmation": false,
  "next_step": "check-update-or-use"
}
```

`check-skill-update.sh` returns:

```json
{
  "ok": true,
  "qualified_name": "lvxiaoer/spreadsheet",
  "source_registry": "self",
  "installed_version": "1.2.3",
  "latest_available_version": "1.2.4",
  "update_available": true,
  "state": "update-available",
  "next_step": "run upgrade-skill"
}
```

## Failure states

- `ambiguous` — caller must choose a qualified name
- `not-found` — no matching discovery entry exists
- `incompatible` — matches exist, but not for the requested target agent
- `confirmation-required` — the chosen install source is external and the caller requested auto mode
- `cross-source-upgrade-not-allowed` — an upgrade request tried to change registry source implicitly

## Forbidden assumptions

- do not treat discovery as permission to install mutable source directories
- do not auto-install external matches without confirmation
- do not infer installable versions from working tree state; use generated indexes
- do not silently change source registry during upgrade
