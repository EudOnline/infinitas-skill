---
audience: operators, integrators
owner: repository maintainers
source_of_truth: install manifest format
last_reviewed: 2026-04-22
status: maintained
---

# Install Manifest Format

Schema and semantics for the `.infinitas-skill-install-manifest.json` file that tracks installed skills in a target directory.

## File location

Created at the root of each install target directory:

```text
<target-dir>/.infinitas-skill-install-manifest.json
```

## Top-level structure

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | `integer` | yes | Always `1`. |
| `repo` | `string\|null` | no | Git remote URL of the source repository. |
| `updated_at` | `string\|null` | no | ISO 8601 UTC timestamp of the last manifest update. |
| `skills` | `object` | yes | Map of skill name → install entry. Keys are the bare directory name from `_meta.json.name`. |
| `history` | `object` | yes | Map of skill name → array of prior install entries (for rollback). Retained up to 25 entries per skill. |

## Install entry fields

Each value in `skills` and each element in `history[]` arrays is an install entry object.

### Identity

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Skill name from `_meta.json` |
| `publisher` | `string\|null` | no | Publisher slug (e.g. `"acme"`) |
| `qualified_name` | `string\|null` | no | Fully-qualified name (e.g. `"acme/my-skill"`) |
| `identity_mode` | `string` | no | `"qualified"` or `"legacy"` |
| `author` | `string\|null` | no | Author handle |
| `owners` | `array[string]` | no | Owner handles |
| `maintainers` | `array[string]` | no | Maintainer handles |
| `version` | `string` | yes | Version from `_meta.json` |
| `locked_version` | `string` | no | Resolved/locked version at install time |
| `status` | `string` | no | Skill status (e.g. `"active"`, `"incubating"`) |

### Source provenance

| Field | Type | Required | Description |
|---|---|---|---|
| `source_type` | `string` | yes | Origin type: `"working-tree"`, `"distribution-manifest"`, etc. |
| `source_repo` | `string\|null` | no | Git remote URL of the source |
| `source_registry` | `string` | no | Registry name. Default `"self"` for local installs. |
| `source_registry_kind` | `string\|null` | no | Registry kind (e.g. `"http"` for hosted) |
| `source_trust` | `string\|null` | no | Trust level of the source registry |
| `source_ref` | `string\|null` | no | Git ref (branch/tag/commit) |
| `source_commit` | `string\|null` | no | Specific git commit SHA |
| `source_tag` | `string\|null` | no | Specific git tag |
| `source_root` | `string\|null` | no | Root path of the source registry |
| `source_path` | `string` | yes | Absolute path to the source skill directory |
| `source_relative_path` | `string\|null` | no | Relative path within the source registry |
| `source_stage` | `string` | no | Stage in source registry (e.g. `"active"`) |

### Source identity

| Field | Type | Required | Description |
|---|---|---|---|
| `source_publisher` | `string\|null` | no | Publisher of the source skill |
| `source_qualified_name` | `string\|null` | no | Qualified name in the source registry |
| `source_identity_mode` | `string\|null` | no | Identity mode at source |
| `source_version` | `string\|null` | no | Version at source |

### Snapshot

| Field | Type | Required | Description |
|---|---|---|---|
| `source_snapshot_of` | `string\|null` | no | Original skill+version this is a snapshot of |
| `source_snapshot_created_at` | `string\|null` | no | Timestamp of snapshot creation |
| `source_snapshot_kind` | `string\|null` | no | Kind of snapshot |
| `source_snapshot_tag` | `string\|null` | no | Snapshot tag |
| `source_snapshot_ref` | `string\|null` | no | Snapshot ref |
| `source_snapshot_commit` | `string\|null` | no | Snapshot commit SHA |

### Registry snapshot mirror

| Field | Type | Required | Description |
|---|---|---|---|
| `source_registry_snapshot_id` | `string\|null` | no | ID of the registry snapshot |
| `source_registry_snapshot_path` | `string\|null` | no | Path to snapshot metadata |
| `source_registry_snapshot_created_at` | `string\|null` | no | Timestamp of the snapshot |
| `source_registry_snapshot_metadata_path` | `string\|null` | no | Path to snapshot metadata file |

### Distribution

| Field | Type | Required | Description |
|---|---|---|---|
| `source_distribution_manifest` | `string\|null` | no | Relative path to the distribution manifest |
| `source_distribution_root` | `string\|null` | no | Local cache path for persisted artifacts |
| `source_distribution_bundle` | `string\|null` | no | Relative path to the distribution bundle archive |
| `source_distribution_bundle_sha256` | `string\|null` | no | SHA-256 digest of the bundle |
| `source_distribution_bundle_size` | `integer\|null` | no | Size of the bundle in bytes |
| `source_distribution_bundle_root_dir` | `string\|null` | no | Root directory within the bundle |
| `source_distribution_bundle_file_count` | `integer\|null` | no | Number of files in the bundle |
| `source_attestation_path` | `string\|null` | no | Relative path to the attestation file |
| `source_attestation_signature_path` | `string\|null` | no | Relative path to the attestation signature |
| `source_attestation_sha256` | `string\|null` | no | SHA-256 digest of the attestation |
| `source_attestation_signature_sha256` | `string\|null` | no | SHA-256 digest of the signature |

### Pin and resolution

| Field | Type | Required | Description |
|---|---|---|---|
| `source_expected_tag` | `string\|null` | no | Expected tag during resolution |
| `source_resolution_reason` | `string\|null` | no | Reason for the resolution outcome |
| `source_update_mode` | `string\|null` | no | Update mode (e.g. `"latest"`, `"pin"`) |
| `source_pin_mode` | `string\|null` | no | Pin mode |
| `source_pin_value` | `string\|null` | no | Pin value |

### Target and install

| Field | Type | Required | Description |
|---|---|---|---|
| `target_path` | `string` | yes | Relative path of the installed skill within the target directory |
| `install_target` | `string` | yes | Absolute path to the target directory |
| `installed_version` | `string` | yes | Version of the installed skill |
| `installed_at` | `string` | yes | ISO 8601 UTC timestamp of the install |
| `last_checked_at` | `string\|null` | no | ISO 8601 UTC timestamp of last integrity check. `null` if never checked. |
| `resolved_release_digest` | `string\|null` | no | SHA-256 digest of the resolved release bundle |
| `target_agent` | `string\|null` | no | Target agent identifier for agent-scoped installs |
| `install_mode` | `string` | yes | Action verb: `"install"`, `"update"`, `"switch"` |
| `action` | `string` | yes | Same as `install_mode` (compatibility) |
| `updated_at` | `string` | yes | ISO 8601 UTC timestamp of this entry |

### Optional fields

| Field | Type | Description |
|---|---|---|
| `resolution_plan` | `object` | Present when a deterministic dependency resolution plan was applied |
| `integrity` | `object` | Integrity verification snapshot |
| `integrity_capability` | `string\|null` | Integrity capability level |
| `integrity_reason` | `string\|null` | Reason for current integrity state |
| `integrity_events` | `array` | Chronological log of integrity check events |

## History retention

- Each skill retains prior install entries in `history`
- When a skill is updated, the previous entry is appended to `history[<name>]`
- Rollback uses these historical entries to restore a prior state

## Schema file

Machine-readable JSON Schema: `schemas/install-manifest.schema.json`

## See also

- [Distribution manifests](distribution-manifests.md)
- [Installed skill integrity](installed-skill-integrity.md)
- [Compatibility contract](compatibility-contract.md)
- [Metadata schema](metadata-schema.md)
