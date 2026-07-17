---
audience: CLI maintainers, install tooling developers, operators
owner: repository maintainers
source_of_truth: schemas/install-manifest.schema.json
last_reviewed: 2026-07-14
status: maintained
---

# Install Manifest Format

Every install target has one state file at its root:

```text
.infinitas-skill-install-manifest.json
```

Only schema version `1` is accepted. The manifest records current installed state and bounded prior state for rollback and integrity reporting.

## Top-level object

```json
{
  "schema_version": 1,
  "repo": "https://example.invalid/registry.git",
  "updated_at": "2026-07-14T08:00:00Z",
  "skills": {},
  "history": {}
}
```

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `schema_version` | integer | yes | Exactly `1` |
| `repo` | string or null | no | Source repository identifier |
| `updated_at` | string or null | no | Last manifest update time |
| `skills` | object | yes | Current entry keyed by installed folder name |
| `history` | object | yes | Prior entries keyed by installed folder name |

## Current entry

Required fields:

- `name`
- `version`
- `source_type`
- `source_path`
- `target_path`
- `install_target`
- `installed_version`
- `installed_at`
- `install_mode`
- `updated_at`

### Identity

```json
{
  "name": "operate-infinitas-skill",
  "publisher": "lvxiaoer",
  "qualified_name": "lvxiaoer/operate-infinitas-skill",
  "identity_mode": "qualified",
  "author": "lvxiaoer",
  "owners": ["lvxiaoer"],
  "maintainers": ["lvxiaoer"]
}
```

`identity_mode` has one value: `qualified`. The manifest key is the installed target folder; canonical identity is carried by `qualified_name`.

### Source provenance

The `source_*` fields record the exact source selected by discovery and resolution:

- registry name, kind, and trust state;
- repository/ref/commit/tag;
- source root and relative path;
- publisher, qualified identity, version, and stage;
- snapshot identifier and source metadata when a snapshot is used.

### Distribution evidence

Immutable installs record:

- `source_distribution_manifest`
- `source_distribution_root`
- `source_distribution_bundle`
- `source_distribution_bundle_sha256`
- `source_distribution_bundle_size`
- `source_distribution_bundle_root_dir`
- `source_distribution_bundle_file_count`
- `source_attestation_path`
- `source_attestation_signature_path`
- attestation and signature SHA-256 values
- `source_expected_tag`

These fields identify current release evidence. Install code verifies paths, archive members, hashes, and attestations before materialization.

### Resolution and pinning

- `source_resolution_reason`
- `source_update_mode`
- `source_pin_mode`
- `source_pin_value`
- `locked_version`
- `resolution_plan`
- `resolved_release_digest`
- `target_agent`

`install_mode` records the operation that produced the current state, such as `install`, `update`, `switch`, or `rollback`. There is no duplicate action field.

### Integrity

- `integrity`
- `integrity_capability`
- `integrity_reason`
- `integrity_events`
- `last_checked_at`

Integrity state describes the installed copy, not the source release. Source evidence remains immutable; local verification timestamps and events can advance.

## History

Before an entry is replaced, the prior current entry is appended to `history[folder_name]`. History supports rollback and audit without inventing a second manifest format. Retention is governed by the current install-integrity policy.

## Validation and commands

The Python implementation is `src/infinitas_skill/install/install_manifest.py`; the JSON schema is `schemas/install-manifest.schema.json`.

Use the maintained CLI for install state operations:

```bash
uv run infinitas install exact --help
uv run infinitas install check-update --help
uv run infinitas install upgrade --help
uv run infinitas install rollback --help
uv run infinitas install report --help
uv run infinitas install verify --help
```

Invalid schema versions or unsupported source/distribution paths fail immediately with `InstallManifestError`; they are not rewritten in place.
