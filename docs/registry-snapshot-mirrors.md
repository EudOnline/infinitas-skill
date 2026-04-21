---
audience: contributors, integrators, operators
owner: repository maintainers
source_of_truth: legacy top-level mirror strategy doc
last_reviewed: 2026-04-21
status: legacy
---

# Registry Snapshot Mirrors

Version 13 Phase 2 adds immutable registry snapshots for operators who need offline or recovery-friendly access to a previously synced remote registry.

Snapshots are additive artifacts. They do not become a new authoritative registry kind and they do not change normal resolver behavior unless you explicitly ask for one.

## Snapshot layout

Each snapshot lives under:

```text
.cache/registry-snapshots/<registry>/<snapshot_id>/
```

The directory contains:

- `registry/` - a copied checkout of the cached registry tree at snapshot time
- `snapshot.json` - machine-readable metadata describing the copied source identity and refresh state

The metadata records:

- `registry`
- `snapshot_id`
- `created_at`
- `authoritative: false`
- `snapshot_root`
- `source_registry` identity, including `kind`, `trust`, `update_mode`, `ref`, `tag`, `commit`, and `origin_url`
- copied `refresh_state` from the mutable cache state file

## Create a snapshot

First sync the remote registry cache:

```bash
scripts/sync-registry-source.sh upstream
```

Then create the snapshot:

```bash
python3 scripts/create-registry-snapshot.py upstream --json
```

The JSON response includes the concrete `snapshot_id`, the relative `snapshot_root`, and the source commit/ref/tag copied into the snapshot.

Snapshot creation is currently limited to remote cached Git registries. `local-only` registries such as `self` are intentionally rejected.

## Use a snapshot explicitly

Explicit snapshot usage is opt-in. Pass both `--registry` and `--snapshot`:

```bash
python3 scripts/resolve-skill-source.py demo --registry upstream --snapshot latest --json
```

```bash
uv run python3 -m infinitas_skill.cli.main install exact demo ~/.openclaw/skills --registry upstream --snapshot latest
```

```bash
scripts/sync-registry-source.sh upstream --snapshot latest
```

Behavior:

- `resolve-skill-source.py` resolves from the immutable snapshot tree instead of `.cache/registries/<registry>`
- missing snapshots fail explicitly; they do not fall back to the mutable cache
- `infinitas install exact` preserves snapshot identity in the install manifest
- `sync-registry-source.sh --snapshot ...` validates the snapshot and prints its root without fetching remote state

When a concrete snapshot is selected, resolved payloads expose snapshot metadata such as:

- `registry_snapshot_id`
- `registry_snapshot_path`
- `registry_snapshot_created_at`
- `registry_snapshot_metadata_path`

## Catalog visibility

Catalog and registry listing surfaces expose additive snapshot summary fields:

- `snapshot_count`
- `latest_snapshot`
- `available_snapshots`

Those fields help operators discover what immutable recovery points exist. They do not change resolver authority by themselves.
