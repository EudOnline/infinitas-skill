# Structure

## Top-level layout

```text
.
├─ .github/workflows/      CI workflow entrypoints
├─ .planning/              planning-tool state; not part of registry runtime
├─ catalog/                generated registry indexes and provenance
├─ config/                 machine-readable operational configuration
├─ docs/                   human guidance and workflow documentation
├─ policy/                 machine-readable promotion rules
├─ schemas/                machine-readable schema contracts
├─ scripts/                operational CLI entrypoints and validators
├─ skills/                 lifecycle-managed skill source trees
├─ templates/              scaffold sources for new skills
├─ reviews/                currently unused top-level review area
└─ .cache/registries/      synced external registry cache
```

## Directory-by-directory map

### `.github/workflows/`

Purpose:

- GitHub Actions automation

Key file:

- `.github/workflows/validate.yml`: runs `scripts/check-all.sh` on `push` to `main` and on `pull_request`

Planning note:

- This is the only repo-native workflow automation directory today; there is no root `workflows/` directory for product logic.

### `.planning/`

Purpose:

- Local planning metadata for the GSD workflow, not for registry distribution

Key files:

- `.planning/config.json`: planning-model/profile toggles
- `.planning/codebase/`: generated codebase mapping documents

Planning note:

- Keep this separate from registry behavior. Future runtime changes should not depend on `.planning/` state.

### `catalog/`

Purpose:

- Generated, machine-readable views of registry state

Key files:

- `catalog/catalog.json`: all indexed skills across lifecycle stages
- `catalog/active.json`: active + installable subset
- `catalog/compatibility.json`: stage counts plus `agent_compatible` matrix
- `catalog/registries.json`: exported view of configured registries with resolved roots
- `catalog/provenance/`: generated provenance records from release flow

Ownership pattern:

- Input comes from `skills/` and `config/registry-sources.json`
- Generation is owned by `scripts/build-catalog.sh`

Planning constraint:

- Treat everything here as generated output, not editable source.

### `config/`

Purpose:

- Operational configuration for registry resolution and provenance verification

Key files:

- `config/registry-sources.json`: authoritative registry source list, priority, trust, branch, default source
- `config/signing.json`: SSH signing namespace and allowed-signers path
- `config/allowed_signers`: SSH verification trust list referenced by `config/signing.json`

Who reads it:

- `scripts/check-registry-sources.py`
- `scripts/list-registry-sources.py`
- `scripts/resolve-skill-source.py`
- `scripts/sync-registry-source.sh`
- `scripts/build-catalog.sh`
- `scripts/generate-provenance.py`
- `scripts/sign-provenance-ssh.sh`
- `scripts/verify-provenance-ssh.sh`

Planning constraint:

- `config/registry-sources.json` is the single config surface for multi-registry behavior; avoid duplicating registry settings elsewhere.

### `docs/`

Purpose:

- Human-facing explanation of lifecycle, conventions, metadata, release flow, trust model, and multi-registry behavior

Key files by topic:

- `docs/conventions.md`: naming and expected skill folder layout
- `docs/lifecycle.md`: incubating/active/archived lifecycle
- `docs/metadata-schema.md`: `_meta.json` field meaning
- `docs/promotion-policy.md`: explains `policy/promotion-policy.json`
- `docs/review-workflow.md`: explains `reviews.json` flow and review scripts
- `docs/history-and-snapshots.md`: archived snapshot semantics
- `docs/multi-registry.md`: registry-source model and sync behavior
- `docs/release-strategy.md`: tagging, release helper, provenance flow
- `docs/release-checklist.md`: pre-promote/pre-release checklist
- `docs/trust-model.md`: security and distribution posture
- `docs/compatibility-matrix.md`: explains `catalog/compatibility.json`

Planning constraint:

- The docs layer is explanatory, not authoritative. Any new documented rule should also exist in `policy/`, `schemas/`, or `scripts/` as appropriate.

### `policy/`

Purpose:

- Declarative governance rules for active-skill promotion

Key file:

- `policy/promotion-policy.json`

Who reads it:

- `scripts/check-promotion-policy.py`
- `scripts/review-status.py`

Planning constraint:

- Promotion logic is intentionally policy-driven. Add new promotion gates here before hard-coding them elsewhere.

### `schemas/`

Purpose:

- Machine-readable metadata contract

Key file:

- `schemas/skill-meta.schema.json`

Who depends on it conceptually:

- `docs/metadata-schema.md`
- `scripts/validate-registry.py`
- `scripts/check-skill.sh`
- every skill `_meta.json`

Planning constraint:

- Even though enforcement scripts currently encode checks directly, this schema is still the contract anchor for future tooling/editor support.

### `scripts/`

Purpose:

- Operational command surface for the registry

Internal organization by concern:

- Creation/scaffolding
  - `scripts/new-skill.sh`

- Validation/governance
  - `scripts/check-skill.sh`
  - `scripts/check-all.sh`
  - `scripts/validate-registry.py`
  - `scripts/check-registry-integrity.py`
  - `scripts/check-promotion-policy.py`
  - `scripts/check-registry-sources.py`
  - `scripts/check-install-target.py`

- Catalog/index generation
  - `scripts/build-catalog.sh`
  - `scripts/list-registry-sources.py`

- Review/promotion lifecycle
  - `scripts/request-review.sh`
  - `scripts/approve-skill.sh`
  - `scripts/review-status.py`
  - `scripts/promote-skill.sh`
  - `scripts/snapshot-active-skill.sh`
  - `scripts/bump-skill-version.sh`
  - `scripts/release-skill-tag.sh`
  - `scripts/release-skill.sh`

- Source resolution and registry sync
  - `scripts/resolve-skill-source.py`
  - `scripts/sync-registry-source.sh`
  - `scripts/sync-all-registries.sh`

- Installation/runtime distribution
  - `scripts/install-skill.sh`
  - `scripts/sync-skill.sh`
  - `scripts/switch-installed-skill.sh`
  - `scripts/rollback-installed-skill.sh`
  - `scripts/list-installed.sh`
  - `scripts/update-install-manifest.py`

- Lineage and comparison
  - `scripts/lineage-diff.sh`
  - `scripts/diff-skill.sh`

- Provenance signing
  - `scripts/generate-provenance.py`
  - `scripts/sign-provenance.py`
  - `scripts/verify-provenance.py`
  - `scripts/sign-provenance-ssh.sh`
  - `scripts/verify-provenance-ssh.sh`

Structure note:

- The directory mixes shell entrypoints and standalone Python helpers.
- There is no shared `lib/` or package layer; reuse happens via script-to-script calls and inline Python blocks.

Planning constraint:

- New cross-cutting behavior should either extend an existing hub script or introduce a deliberate helper layer; avoid scattering duplicated JSON logic further.

### `skills/`

Purpose:

- Lifecycle-managed registry source of truth for actual skills

Subdirectories:

- `skills/incubating/`: work-in-progress skills
- `skills/active/`: reviewed, installable stable skills
- `skills/archived/`: deprecated skills and timestamped snapshots

Current state:

- All three directories are empty except for `.gitkeep`

Expected per-skill shape:

- `SKILL.md`
- `_meta.json`
- `CHANGELOG.md`
- optional `scripts/`, `references/`, `assets/`
- `tests/smoke.md`

Planning constraint:

- Parent directory is semantically significant; `_meta.json.status` must match the lifecycle directory.

### `templates/`

Purpose:

- Starter skill definitions for new work

Subdirectories:

- `templates/basic-skill/`
- `templates/scripted-skill/`
- `templates/reference-heavy-skill/`

Role in structure:

- These are valid skeletons used by `scripts/new-skill.sh`
- They mirror the expected skill shape and embed starter `_meta.json` + `SKILL.md`

Planning constraint:

- Any change to expected skill layout should update templates, docs, and validation together.

### `.cache/registries/`

Purpose:

- Local cache/mirror area for synced external git registries

Who writes it:

- `scripts/sync-registry-source.sh`

Who reads it:

- `scripts/resolve-skill-source.py`

Planning constraint:

- This is materialized state, not source-of-truth. Safe behavior depends on being able to rebuild it from `config/registry-sources.json`.

### `reviews/`

Purpose:

- Currently no active runtime role in the reviewed flow

Important note:

- Review state is stored beside each skill in `reviews.json`, not under this directory

Planning constraint:

- Do not route new review features here unless you also redesign and migrate the existing per-skill review model.

## Key structural relationships

### `catalog` / `config` / `scripts`

- `config/` declares registry-source inputs
- `scripts/` resolves, validates, syncs, and exports those inputs
- `catalog/` stores generated views for consumers and audits

Practical relationship:

- edit `config/registry-sources.json`
- validate via `scripts/check-registry-sources.py`
- sync via `scripts/sync-registry-source.sh` or `scripts/sync-all-registries.sh`
- export via `scripts/build-catalog.sh`
- consume via `catalog/registries.json` or `scripts/resolve-skill-source.py`

### `docs` / `policy` / `schemas` / `scripts`

- `docs/` defines human expectations
- `policy/` defines promotion rules
- `schemas/` defines metadata shape
- `scripts/` turns those contracts into executable checks and mutations

Practical relationship:

- metadata contract lives in `schemas/skill-meta.schema.json`
- human explanation lives in `docs/metadata-schema.md`
- validation is performed in `scripts/validate-registry.py` and `scripts/check-skill.sh`
- promotion rules live in `policy/promotion-policy.json`
- enforcement runs in `scripts/check-promotion-policy.py`

### `workflows` / `scripts`

- CI workflow file `.github/workflows/validate.yml` delegates to `scripts/check-all.sh`
- local and remote validation therefore share the same aggregation point

Planning constraint:

- If a new invariant must fail PRs, wire it into `scripts/check-all.sh` rather than only into documentation or an ad-hoc CI step.

## Primary entrypoint map

### Authoring

- `scripts/new-skill.sh`
- `templates/*`
- `skills/incubating/`

### Validation

- `scripts/check-skill.sh`
- `scripts/check-all.sh`
- `.github/workflows/validate.yml`

### Review and promotion

- `scripts/request-review.sh`
- `scripts/approve-skill.sh`
- `scripts/review-status.py`
- `scripts/promote-skill.sh`

### Distribution

- `scripts/resolve-skill-source.py`
- `scripts/install-skill.sh`
- `scripts/sync-skill.sh`
- `scripts/switch-installed-skill.sh`
- `scripts/rollback-installed-skill.sh`

### Release and trust

- `scripts/release-skill.sh`
- `catalog/provenance/`
- `config/signing.json`
- `config/allowed_signers`

## Naming and layout conventions that matter structurally

- Skill names are lowercase hyphenated slugs
- For non-archived skills, folder name should match `_meta.json.name` and `SKILL.md` `name:`
- `tests/smoke.md` is treated as the default minimum validation artifact
- Active overwrite history is stored as timestamped directories under `skills/archived/`
- Release tags use the form `skill/<name>/v<version>`
- Installed copies are tracked by `.infinitas-skill-install-manifest.json` in the target directory

## Structural hotspots for future work

1. **Registry resolution hotspot**
   - `config/registry-sources.json`
   - `scripts/resolve-skill-source.py`
   - `scripts/sync-registry-source.sh`
   - `catalog/registries.json`

2. **Governance hotspot**
   - `schemas/skill-meta.schema.json`
   - `policy/promotion-policy.json`
   - `scripts/validate-registry.py`
   - `scripts/check-promotion-policy.py`
   - `scripts/check-all.sh`

3. **Distribution hotspot**
   - `scripts/install-skill.sh`
   - `scripts/sync-skill.sh`
   - `scripts/update-install-manifest.py`
   - `scripts/check-install-target.py`

4. **Release/provenance hotspot**
   - `scripts/release-skill.sh`
   - `scripts/generate-provenance.py`
   - `scripts/sign-provenance.py`
   - `scripts/sign-provenance-ssh.sh`
   - `catalog/provenance/`

## Important findings

- The repository has a clear top-level separation between source (`skills/`, `templates/`), contracts (`config/`, `policy/`, `schemas/`), behavior (`scripts/`), generated outputs (`catalog/`), and explanation (`docs/`).
- The current repo has no live skill data, so many structural guarantees are encoded by templates and validators rather than by populated examples.
- The term “workflows” currently maps to `.github/workflows/` and prose workflow docs, not to a first-class application directory.
- The root `reviews/` directory is structurally present but operationally idle.
