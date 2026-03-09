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
- attestation bundle (`provenance_path`, `signature_path`, signer identity, signer namespace)
- registry context
- dependency resolution context

The attestation payload must agree with the manifest. Verification fails if:

- the bundle digest changed
- the attestation digest changed
- the signed attestation does not match the manifest metadata
- the source snapshot or dependency context diverges

## Generate and verify

`release-skill.sh --write-provenance` now emits and verifies distribution data when the SSH attestation signature exists.

Useful commands:

```bash
# release, write attestation, emit distribution bundle + manifest
scripts/release-skill.sh my-skill --push-tag --write-provenance

# verify one manifest directly
python3 scripts/verify-distribution-manifest.py \
  catalog/distributions/_legacy/my-skill/1.2.3/manifest.json
```

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

## Historical rollback

Rollback history now keeps enough source metadata to re-resolve a previously installed version from the matching distribution manifest.

So historical install / switch / rollback flows no longer depend on whatever happens to still be present in `skills/active/`.

## Catalog exports

`build-catalog.sh` now writes:

- `catalog/distributions.json`
- `verified_distribution` metadata in catalog entries when a manifest is available

That gives downstream consumers a stable place to discover:

- manifest path
- bundle path + digest
- attestation path + signature path
- released source snapshot
- generation timestamp

## Current limitation

The bundle/manifest path is only authoritative once the release attestation can be verified.

If `config/allowed_signers` still has no real trusted signer entries, stable verified distribution remains operationally blocked even though the code path and tests are present.
