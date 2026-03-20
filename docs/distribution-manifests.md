# Distribution Manifests

V10 Phase 3 adds a verified distribution layer on top of the Git-native registry.

Instead of treating the working tree as the only install surface, stable releases can now emit an immutable bundle plus a machine-readable manifest that points to:

1. the exact released skill bundle
2. the signed attestation payload
3. the attestation signature
4. the immutable source snapshot (tag/ref/commit)
5. the dependency and registry context used for the release

## What gets written

A stable release with provenance now writes files under:

```text
catalog/distributions/<publisher-or-_legacy>/<skill>/<version>/
├─ manifest.json
└─ skill.tar.gz
```

And also updates:

```text
catalog/distributions.json
```

That index is consumed by resolver/catalog tooling so installs can prefer immutable release artifacts over ad-hoc working-tree state.

## Manifest contents

Each `manifest.json` records:

- skill identity (`name`, `publisher`, `qualified_name`, `version`, `status`)
- immutable source snapshot (`tag`, `ref`, `commit`, `immutable`, `pushed`)
- bundle metadata (`path`, `sha256`, `size`, `root_dir`, `file_count`)
- reproducibility-oriented bundle metadata (`build`)
- a per-file released-file inventory (`file_manifest`)
- attestation bundle (`provenance_path`, `signature_path`, signer identity, signer namespace)
- registry context
- dependency resolution context

The signed provenance now carries the same release-bundle contract inside `distribution`, so release tooling can keep the signed attestation and the published manifest aligned on both top-level bundle identity and file-level inventory.

`file_manifest` records one entry per archived file with:

- relative path inside the released skill root
- SHA-256 digest
- file size
- normalized archive mode

`build` records the normalized archive settings and small builder summary used to create the bundle, such as:

- archive format
- gzip and tar mtimes
- tar uid/gid and owner/group markers
- Python version and implementation used by the release helper

The attestation payload must agree with the manifest. Verification fails if:

- the bundle digest changed
- the attestation digest changed
- the signed attestation does not match the manifest metadata
- the source snapshot or dependency context diverges
- the file-level release inventory or normalized build metadata diverges from the signed attestation
- the actual archived bundle contents no longer match the signed `file_manifest`
- the archive-normalized reproducibility fields (`archive_format`, mtimes, uid/gid, owner markers) no longer match the signed `build` metadata

## Generate and verify

`release-skill.sh --write-provenance` now emits and verifies distribution data when the SSH attestation signature exists.

When the signing policy enables transparency publication, the release flow also writes a provenance companion record:

```text
catalog/provenance/<skill>-<version>.transparency.json
```

That companion file is not a replacement for the signed attestation. It is an additive proof record that ties the signed attestation digest to an external transparency-log entry.

Useful commands:

```bash
# release, write attestation, emit distribution bundle + manifest
scripts/release-skill.sh my-skill --push-tag --write-provenance

# verify one manifest directly
python3 scripts/verify-distribution-manifest.py \
  catalog/distributions/_legacy/my-skill/1.2.3/manifest.json
```

Legacy manifests created before reproducibility metadata was added can be upgraded in place:

```bash
python3 scripts/backfill-distribution-manifests.py \
  --manifest catalog/distributions/lvxiaoer/operate-infinitas-skill/0.1.1/manifest.json \
  --write \
  --json
```

The backfill flow is additive and deterministic:

- it re-verifies signed provenance plus bundle artifacts first
- it regenerates canonical `file_manifest` and normalized `build` from immutable artifacts
- it preserves immutable identity fields (`bundle`, `attestation_bundle`, `source_snapshot`) unchanged
- it reports `state = "would-backfill"` for dry runs, `state = "backfilled"` when `--write` applies changes, and `state = "unchanged"` on repeat runs

If immutable evidence is incomplete, the command reports a compatibility state instead of guessing release metadata.

The helper now supports both focused and repo-scan workflows:

```bash
# scan one explicit manifest
python3 scripts/backfill-distribution-manifests.py --manifest <path> --json

# scan every catalog/distributions/**/manifest.json under a root
python3 scripts/backfill-distribution-manifests.py --root . --json
```

Machine-readable output includes one status object per inspected manifest, including additive release capability hints:

- `installed_integrity_capability` (`supported` or `unknown`)
- `installed_integrity_reason` (for example `missing-signed-file-manifest` when capability is `unknown`)
- immutable reproducibility hints such as `file_manifest_count` and `build_archive_format`

You can now extend that immutable verification path into one installed runtime copy:

```bash
python3 scripts/verify-installed-skill.py my-skill ~/.openclaw/skills --json
```

That verifier loads the install-manifest entry for `my-skill`, re-verifies the recorded distribution manifest and attestation, then compares the installed local files against the signed `file_manifest`.

If the local runtime copy has drifted, repair it back to the same recorded immutable release instead of guessing a newer version:

```bash
scripts/repair-installed-skill.sh my-skill ~/.openclaw/skills
```

Machine-readable verification now exposes the same reproducibility contract on every layer:

- `python3 scripts/verify-attestation.py <attestation.json> --json` includes `distribution.file_manifest_count` plus the signed `distribution.build` summary
- `python3 scripts/check-release-state.py <name> --mode local-tag --json` includes `release.reproducibility`, so local provenance flows can inspect the generated release metadata even though repo-managed artifacts make the worktree dirty
- `catalog/catalog.json` mirrors a compact downstream summary under `verified_distribution.file_manifest_count` and `verified_distribution.build_archive_format`

When transparency publication is enabled:

- `python3 scripts/verify-attestation.py <attestation.json> --json` also includes `transparency_log`
- `python3 scripts/check-release-state.py <name> --json` mirrors the same summary under `release.transparency_log`
- `catalog/catalog.json` preserves a downstream-facing copy under `verified_distribution.transparency_log`

## Install / sync behavior

Resolver output now prefers `distribution-manifest` sources when available.

That means these workflows can materialize from immutable release artifacts instead of copying directly from the live skill folder:

```bash
scripts/install-skill.sh my-skill ~/.openclaw/skills --version 1.2.3
scripts/sync-skill.sh my-skill ~/.openclaw/skills
scripts/switch-installed-skill.sh my-skill ~/.openclaw/skills --to-version 1.2.3 --force
scripts/rollback-installed-skill.sh my-skill ~/.openclaw/skills --force
```

When a distribution manifest is selected, the toolchain:

1. verifies the manifest
2. verifies the SSH attestation bundle it references
3. verifies the archived bundle digest
4. extracts a temporary materialized skill tree
5. installs/syncs from that verified materialized tree

This preserves backward compatibility while making verified immutable artifacts the preferred stable path.

Installed runtime trust now follows the same model:

1. verify the recorded immutable source
2. compare installed local files against the signed released-file inventory
3. stop mutation commands on drift unless the caller explicitly forces replacement
4. prefer `repair-installed-skill.sh` over silent overwrite when the goal is to restore trust

When the installed copy is still clean but the recorded local verification is stale, overwrite-style commands now consult the repo-managed installed-integrity freshness policy:

- `warn` prints `python3 scripts/report-installed-integrity.py <target-dir> --refresh` guidance before continuing
- `fail` stops until that explicit refresh is run
- `--force` remains the deliberate bypass for local overwrite guardrails

`never-verified` installs use the same target-local policy layer through `freshness.never_verified_policy`:

- refreshable installs recommend `python3 scripts/report-installed-integrity.py <target-dir> --refresh`
- legacy compatibility-only installs without enough immutable source metadata recommend reinstall or distribution-manifest backfill first
- `warn` surfaces that recovery path before continuing
- `fail` blocks overwrite-style mutation until the recovery path re-establishes trust

Drift still blocks first, before stale or never-verified freshness rules are consulted.

This freshness policy is target-local behavior. It does not change the immutable distribution-manifest contract or require new persisted install-manifest fields.

## Historical rollback

Rollback history now keeps enough source metadata to re-resolve a previously installed version from the matching distribution manifest.

So historical install / switch / rollback flows no longer depend on whatever happens to still be present in `skills/active/`.

## Catalog exports

`build-catalog.sh` now writes:

- `catalog/distributions.json`
- `verified_distribution` metadata in catalog entries when a manifest is available
- additive installed-integrity capability summary (`installed_integrity_capability`, optional `installed_integrity_reason`) in both of those surfaces

That gives downstream consumers a stable place to discover:

- manifest path
- bundle path + digest
- file-manifest count
- bundle archive format summary
- installed-integrity verification capability for the released artifact
- attestation path + signature path
- released source snapshot
- generation timestamp

## Current limitation

The bundle/manifest path is only authoritative once the release attestation can be verified.

Fresh repositories without real trusted signer entries in `config/allowed_signers` remain operationally blocked even though the code path and tests are present.

This repository already has a committed `lvxiaoer` signer plus verified provenance for `operate-infinitas-skill`; use `python3 scripts/report-signing-readiness.py --skill operate-infinitas-skill --json` when you need to confirm the current release-trust state before relying on immutable distribution artifacts.

## Discovery and by-name install

The discovery layer does not replace distribution manifests; it resolves to them.

Commands such as:

```bash
scripts/install-by-name.sh my-skill ~/.openclaw/skills
scripts/check-skill-update.sh my-skill ~/.openclaw/skills
scripts/upgrade-skill.sh my-skill ~/.openclaw/skills
```

still rely on immutable release metadata underneath:

1. discovery resolves a candidate skill and source registry
2. install or upgrade resolves an exact installable version
3. the final materialization step still uses the released distribution manifest, bundle digest, and attestation path

So “install by name” is a convenience layer, not a mutable-source shortcut.
