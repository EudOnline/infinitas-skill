# Architecture

## Scope and current state

This repository is not an application service with a long-running runtime. It is an **artifact-oriented private skill registry** whose main job is to keep skill sources, governance rules, generated catalogs, and distribution tooling in one place.

As of the current snapshot:

- `skills/active/`, `skills/incubating/`, and `skills/archived/` contain only `.gitkeep`
- `catalog/catalog.json` and `catalog/active.json` are generated and currently empty
- the repo is therefore **tooling-heavy and data-light**: architecture is defined more by scripts and contracts than by live skill content

## System model

The repository is best understood as five cooperating layers:

1. **Authoring layer**
   - Templates and source directories where skills are created and evolved
   - Key paths: `templates/`, `skills/incubating/`, `skills/active/`, `skills/archived/`

2. **Governance contract layer**
   - Machine-readable constraints for metadata, promotion, registry sources, and signing
   - Key paths: `schemas/skill-meta.schema.json`, `policy/promotion-policy.json`, `config/registry-sources.json`, `config/signing.json`

3. **Execution/orchestration layer**
   - Shell entrypoints coordinate filesystem changes, while Python handles structured JSON parsing, validation, and resolution
   - Key paths: `scripts/*.sh`, `scripts/*.py`

4. **Derived artifact layer**
   - Generated indexes, provenance bundles, archived snapshots, registry caches, and install manifests
   - Key paths: `catalog/*.json`, `catalog/provenance/`, `.cache/registries/`, external target manifests such as `~/.openclaw/skills/.infinitas-skill-install-manifest.json`

5. **Automation and human guidance layer**
   - CI runs the checks; docs explain expected human workflow and policy intent
   - Key paths: `.github/workflows/validate.yml`, `docs/*.md`, `README.md`, `SECURITY.md`

## Architecture style

### 1. Repository-as-control-plane

The repo is the source of truth for:

- skill source trees under `skills/`
- template skill scaffolds under `templates/`
- machine-readable governance under `config/`, `policy/`, and `schemas/`

Runtime consumption happens elsewhere. `scripts/install-skill.sh` and `scripts/sync-skill.sh` copy approved skills into a local runtime directory such as `~/.openclaw/skills` rather than executing skills in-place from the repo.

### 2. File-and-script architecture instead of library architecture

There is no shared Python package or Bash library. Composition happens by:

- shell scripts calling other shell scripts
- shell scripts invoking inline Python snippets
- standalone Python utilities reading JSON files directly from disk

This keeps the MVP simple, but also means cross-cutting behavior is spread across many entrypoints rather than hidden behind a reusable module.

### 3. Generated views over hand-edited sources

The hand-edited source layer is `skills/`, `templates/`, `config/`, `policy/`, `schemas/`, and `docs/`.

The generated/output layer is primarily:

- `catalog/catalog.json`
- `catalog/active.json`
- `catalog/compatibility.json`
- `catalog/registries.json`
- `catalog/provenance/*.json`

`scripts/build-catalog.sh` is the main projection step from source directories and config into machine-consumable indexes.

## Core subsystem relationships

### `catalog/` ↔ `config/` ↔ `scripts/`

- `config/registry-sources.json` is the authoritative registry-source configuration
- `scripts/build-catalog.sh` reads it and emits `catalog/registries.json`
- `scripts/resolve-skill-source.py` also reads it to resolve install/sync candidates across enabled registries
- `scripts/sync-registry-source.sh` and `scripts/sync-all-registries.sh` materialize external registries into `.cache/registries/`

This means `config/` is control-plane input, `scripts/` is behavior, and `catalog/` is read-optimized output.

### `docs/` ↔ `policy/` / `schemas/` ↔ `scripts/`

- `docs/metadata-schema.md` explains the intent of `_meta.json`
- `schemas/skill-meta.schema.json` is the canonical contract definition
- `scripts/validate-registry.py` and `scripts/check-skill.sh` enforce overlapping subsets of that contract
- `docs/promotion-policy.md` describes rules whose executable form lives in `policy/promotion-policy.json`
- `scripts/check-promotion-policy.py` turns that policy into a gate

The pattern is: **docs explain, schema/policy declare, scripts enforce**.

### `workflows` ↔ `scripts/`

There is no top-level `workflows/` product directory. The operational workflow automation currently lives in:

- `.github/workflows/validate.yml` for CI validation
- `docs/*.md` for human workflow playbooks
- `.planning/config.json` for GSD planning-tool behavior, not registry behavior

The CI workflow is intentionally thin: it delegates almost everything to `scripts/check-all.sh`.

### `policy/` ↔ review state storage

Promotion policy assumes review state is stored per skill, inside `reviews.json` next to the skill directory. The active scripts are:

- `scripts/request-review.sh`
- `scripts/approve-skill.sh`
- `scripts/review-status.py`
- `scripts/check-promotion-policy.py`

Notably, the root `reviews/` directory exists but is currently unused by the active flow.

## Main entry points

### Human entry points

- `README.md`: overall workflow and quick-start commands
- `docs/conventions.md`: expected skill shape and naming
- `docs/lifecycle.md`: incubating → active → archived lifecycle
- `docs/release-strategy.md`: release/tag/provenance guidance

### Script entry points

- `scripts/new-skill.sh`: scaffold a skill from `templates/`
- `scripts/check-skill.sh`: local validation and secret scan for one skill directory
- `scripts/check-all.sh`: top-level validation aggregator used locally and in CI
- `scripts/promote-skill.sh`: move an approved skill from `skills/incubating/` to `skills/active/`
- `scripts/install-skill.sh`: install a resolved skill into an external runtime directory
- `scripts/sync-skill.sh`: refresh an installed skill while honoring lock/version rules
- `scripts/release-skill.sh`: release summary, tagging, provenance generation, optional signing
- `scripts/build-catalog.sh`: regenerate `catalog/*.json`

### Automation entry point

- `.github/workflows/validate.yml`: runs `scripts/check-all.sh` on push and PR

## Data and artifact flows

### Flow 1: authoring and validation

1. `scripts/new-skill.sh` copies a template from `templates/` into `skills/incubating/<name>`
2. Human edits `SKILL.md`, `_meta.json`, `CHANGELOG.md`, and `tests/smoke.md`
3. `scripts/check-skill.sh` validates local consistency and scans for secrets
4. `scripts/check-all.sh` runs broader repo-level validation

Key artifacts:

- source skill tree in `skills/incubating/<name>/`
- metadata contract in `_meta.json`
- smoke test note in `tests/smoke.md`

### Flow 2: review and promotion

1. `scripts/request-review.sh` updates `_meta.json.review_state` to `under-review` and appends to `reviews.json`
2. `scripts/approve-skill.sh` appends review decisions and updates `_meta.json.review_state`
3. `scripts/check-promotion-policy.py` evaluates `policy/promotion-policy.json`
4. `scripts/promote-skill.sh` validates the skill, optionally snapshots the active version, moves the folder to `skills/active/`, then runs `scripts/build-catalog.sh`

Key artifacts:

- per-skill `reviews.json`
- archived snapshots under `skills/archived/`
- updated `catalog/*.json`

### Flow 3: install and sync

1. `scripts/resolve-skill-source.py` scans enabled registries from `config/registry-sources.json`
2. It prefers `active` by default, or exact archived snapshots when `--version` is requested
3. `scripts/install-skill.sh` copies the source directory into a target runtime directory
4. `scripts/update-install-manifest.py` writes `.infinitas-skill-install-manifest.json`
5. `scripts/sync-skill.sh`, `scripts/switch-installed-skill.sh`, and `scripts/rollback-installed-skill.sh` use that manifest for controlled updates and rollback

Key artifacts:

- external install copy under the target directory
- target manifest `.infinitas-skill-install-manifest.json`
- optional registry cache under `.cache/registries/<name>`

### Flow 4: release and provenance

1. `scripts/release-skill.sh` validates the chosen skill and the whole repo
2. It extracts release notes from `CHANGELOG.md`
3. It can create a git tag `skill/<name>/v<version>`
4. It can generate provenance into `catalog/provenance/<name>-<version>.json`
5. It can sign provenance with HMAC or SSH and optionally verify the signature

Key artifacts:

- git tag
- `catalog/provenance/*.json`
- `*.sig.json` or `*.ssig` signature sidecars

### Flow 5: multi-registry synchronization

1. `config/registry-sources.json` declares registries, trust, priority, and path/url
2. `scripts/sync-registry-source.sh` clones or fetches git registries into `.cache/registries/<name>`
3. `scripts/resolve-skill-source.py` merges candidates across enabled registries
4. `scripts/build-catalog.sh` exports a resolved view to `catalog/registries.json`

This is the repo's main extension point for future federation.

## Major abstraction boundaries

### Boundary 1: runtime-facing skill content vs registry-facing metadata

- `SKILL.md` is the runtime-facing instruction surface for the consumer agent
- `_meta.json` is the registry-facing contract used for validation, promotion, installation, and catalogs

Any future change that mixes these concerns should be treated carefully; current tooling expects a clean split.

### Boundary 2: policy declaration vs policy enforcement

- Declarative inputs live in `policy/promotion-policy.json` and `schemas/skill-meta.schema.json`
- Enforcement lives in `scripts/check-promotion-policy.py`, `scripts/validate-registry.py`, and `scripts/check-skill.sh`

If future planning adds a new rule, the durable architecture is to update both the declarative file and the enforcing script, then document the behavior in `docs/`.

### Boundary 3: source-of-truth vs generated outputs

- Source-of-truth: `skills/`, `templates/`, `config/`, `policy/`, `schemas/`
- Generated: `catalog/*.json`, `catalog/provenance/*`, `.cache/registries/*`, target install manifests

Generated files should not become alternative sources of truth.

### Boundary 4: repository-local state vs external runtime state

- Repo-local state: skill sources, configs, docs, generated catalogs
- External runtime state: installed skill copies and target manifests in user-local directories

This boundary is important because install/sync/rollback behavior must stay deterministic even when the repo evolves.

## Architectural constraints for future planning

1. **Do not hand-edit generated catalog views**
   - `catalog/catalog.json`, `catalog/active.json`, `catalog/compatibility.json`, and `catalog/registries.json` are projections owned by `scripts/build-catalog.sh`

2. **Keep governance split across docs + declaration + enforcement**
   - New rules should update `docs/`, the corresponding file in `policy/` or `schemas/`, and the enforcing script in `scripts/`

3. **Preserve the current source-resolution contract**
   - `scripts/resolve-skill-source.py` is the narrow waist between `config/registry-sources.json`, `.cache/registries/`, and install/sync flows
   - Changes to registry behavior should land there first, not in ad-hoc install logic

4. **Preserve per-skill review locality unless intentionally redesigned**
   - Active tooling expects `reviews.json` inside each skill directory; the root `reviews/` folder is not currently authoritative

5. **Treat shell/Python duality as a real constraint**
   - Shell scripts own orchestration and CLI ergonomics
   - Python owns structured JSON reasoning
   - Future refactors should either standardize this split or intentionally consolidate it; adding more duplicated parsing logic will raise maintenance cost

6. **Support empty registries as a first-class state**
   - Current generated catalogs legitimately contain zero skills
   - Future features must continue to behave correctly when `skills/` is empty except for templates

7. **CI coverage is centralized through `scripts/check-all.sh`**
   - Any new repo-wide invariant should be wired into `scripts/check-all.sh` so local validation and CI stay aligned

8. **Signing is configured but not fully provisioned**
   - `config/signing.json` points to `config/allowed_signers`, but that file is currently empty
   - SSH verification workflows therefore require operational setup beyond code changes

## Important findings

- The repo currently has **no live skill inventory**, only templates and tooling.
- The architecture is already prepared for multi-registry resolution, provenance, snapshots, dependency management, and review gating even though current data volume is zero.
- There is some intentional duplication in shell-level `resolve_skill` helpers across scripts such as `scripts/release-skill.sh`, `scripts/request-review.sh`, `scripts/approve-skill.sh`, and `scripts/diff-skill.sh`.
- The top-level `reviews/` directory appears reserved or legacy; the active review system is per-skill `reviews.json`.
