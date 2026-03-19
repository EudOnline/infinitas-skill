# Discovery and Install Protocol

## Commands

```bash
scripts/search-skills.sh [query] [--publisher <publisher>] [--agent <agent>] [--tag <tag>] [--json]
scripts/recommend-skill.sh <task-description> [--target-agent <agent>] [--limit <n>] [--json]
scripts/inspect-skill.sh <qualified-name> [--version <semver>] [--json]
scripts/resolve-skill.sh <name> [--target-agent <agent>]
scripts/install-by-name.sh <name> <target-dir> [--version <semver>] [--target-agent <agent>] [--mode auto|confirm]
scripts/check-skill-update.sh <installed-name> <target-dir>
scripts/upgrade-skill.sh <installed-name> <target-dir> [--to-version <semver>] [--registry <name>] [--mode auto|confirm]
```

## Consumer workflow

- search with `scripts/search-skills.sh` first when the caller only knows a topic, publisher, agent, or tag
- recommend with `scripts/recommend-skill.sh` when the caller describes a job and wants the best-ranked candidate
- inspect with `scripts/inspect-skill.sh` before install when the caller needs trust state, compatibility, dependency, distribution, or provenance details
- resolve/install flows stay index-driven and immutable-only; they must not treat source folders as install candidates

## Resolution policy

- search the private registry first via `catalog/discovery-index.json`
- when a configured registry uses `kind: "http"`, discovery may synthesize the same view dynamically from the hosted `ai-index.json`
- if the private registry has one clear compatible match, it wins
- if the private registry has multiple plausible matches, return `ambiguous`
- only search configured external registries when the private registry has no suitable match
- discovery is index-driven; it must not inspect mutable source trees as an install shortcut

## Confirmation rules

- external-only matches require confirmation before auto-install
- `install-by-name.sh --mode confirm` may plan an external install, but must not mutate the target directory
- `check-skill-update.sh` is non-mutating
- `upgrade-skill.sh` must stay on the recorded source registry unless the caller explicitly decides to reinstall from a different source
- when an installed copy is `drifted`, prefer `scripts/repair-installed-skill.sh` before retrying upgrade or rollback

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

All resolver, install, update, and upgrade payloads may now include an additive `explanation` object with:

- `selection_reason`
- `policy_reasons`
- `version_reason`
- `next_actions`

Use this explanation section to understand why a private match won, why an external source requires confirmation, and which version or source registry was chosen.

Release-indexed install trust is also surfaced additively for immutable artifacts:

- `catalog/distributions.json` carries per-version `installed_integrity_capability` plus optional `installed_integrity_reason`
- `catalog/catalog.json` mirrors the same release summary under `verified_distribution.installed_integrity_capability`
- `catalog/inventory-export.json` mirrors that release capability as `release_installed_integrity_capability`

These fields describe immutable release-artifact capability only. They are not local runtime integrity state for one installed target directory.

When the question is "can this release support installed-integrity verification at all?", use those repository-scoped immutable exports and catalog fields.

When the question is "what is the trust state of this specific target directory right now?", use the target-local report surface instead:

```bash
python3 scripts/report-installed-integrity.py <target-dir> --json
python3 scripts/report-installed-integrity.py <target-dir> --refresh --json
```

Do not collapse these concerns:

- `catalog/audit-export.json` is repo-scoped immutable release evidence
- `report-installed-integrity.py` is target-local runtime trust state
- `verify-installed-skill.py` is the explicit read-only verifier for one installed skill

When `install-by-name.sh` fails before materialization, it normalizes resolver states into wrapper-level failure payloads with:

- `ok: false`
- `state: failed`
- stable `error_code`
- actionable `suggested_action`
- additive `explanation`

`check-skill-update.sh` returns:

```json
{
  "ok": true,
  "qualified_name": "lvxiaoer/spreadsheet",
  "source_registry": "self",
  "installed_version": "1.2.3",
  "latest_available_version": "1.2.4",
  "update_available": true,
  "integrity": {
    "state": "verified",
    "last_verified_at": "2026-03-18T08:00:00Z"
  },
  "state": "update-available",
  "next_step": "run upgrade-skill"
}
```

`integrity.state` is additive and may be:

- `verified`
- `drifted`
- `unknown`

When `integrity.state = drifted`, agents should inspect the drift and prefer `scripts/repair-installed-skill.sh` over silently overwriting local files.

## Failure states

- `ambiguous` — caller must choose a qualified name
- `not-found` — no matching discovery entry exists
- `incompatible` — matches exist, but not for the requested target agent
- `confirmation-required` — the chosen install source is external and the caller requested auto mode
- `cross-source-upgrade-not-allowed` — an upgrade request tried to change registry source implicitly
- `ambiguous-skill-name` — `install-by-name.sh` must stop, surface the candidate list, and ask the caller for a `qualified_name`
- `incompatible-target-agent` — `install-by-name.sh` must stop and report that no compatible candidate matched the requested target agent
- `skill-not-found` — install-by-name could not find a discovery match worth materializing
- `resolver-failed` — discovery indexes or resolver inputs were invalid enough that install could not choose any candidate

For `ambiguous-skill-name`, do not guess. Ask the human for a `qualified_name`, then rerun the wrapper with that exact name.

For `incompatible-target-agent`, do not silently drop the compatibility filter. Report the mismatch and let the human choose a different skill or agent target.

## Forbidden assumptions

- do not treat discovery as permission to install mutable source directories
- do not auto-install external matches without confirmation
- do not infer installable versions from working tree state; use generated indexes
- do not require a full repository clone when the configured source is a hosted immutable registry
- do not silently change source registry during upgrade
