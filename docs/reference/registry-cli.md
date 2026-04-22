---
audience: operators, automation authors
owner: repository maintainers
source_of_truth: hosted registry CLI reference
last_reviewed: 2026-04-22
status: maintained
---

# Registry CLI Reference

Complete reference for `infinitas registry` subcommands that interact with the hosted control plane. All commands accept `--base-url` and `--token` flags (or their environment variable equivalents `INFINITAS_REGISTRY_API_BASE_URL` and `INFINITAS_REGISTRY_API_TOKEN`). Every command outputs JSON to stdout on success and error text to stderr on failure (exit code 1).

## Global Flags

| Flag | Environment Variable | Default | Description |
|---|---|---|---|
| `--base-url` | `INFINITAS_REGISTRY_API_BASE_URL` | `http://127.0.0.1:8000` | Registry API base URL |
| `--token` | `INFINITAS_REGISTRY_API_TOKEN` | *(empty)* | Authentication token |

---

## `infinitas registry skills create`

Create a new skill in the registry.

| Argument | Required | Default | Description |
|---|---|---|---|
| `--slug` | yes | | Skill slug |
| `--display-name` | yes | | Human readable skill display name |
| `--summary` | no | `''` | Skill summary |
| `--default-visibility-profile` | no | `None` | Default visibility profile |

API: `POST /api/v1/skills`

Example response:

```json
{
  "id": 1,
  "namespace_id": 1,
  "slug": "my-skill",
  "display_name": "My Skill",
  "summary": "",
  "status": "active",
  "default_visibility_profile": null,
  "created_by_principal_id": 1,
  "created_at": "2026-04-22T00:00:00Z",
  "updated_at": "2026-04-22T00:00:00Z"
}
```

---

## `infinitas registry skills get`

Retrieve a skill by its identifier.

| Argument | Required | Default | Description |
|---|---|---|---|
| `skill_id` (positional) | yes | | Skill identifier (int) |

API: `GET /api/v1/skills/{skill_id}`

Example response:

```json
{
  "id": 1,
  "namespace_id": 1,
  "slug": "my-skill",
  "display_name": "My Skill",
  "summary": "",
  "status": "active",
  "default_visibility_profile": null,
  "created_by_principal_id": 1,
  "created_at": "2026-04-22T00:00:00Z",
  "updated_at": "2026-04-22T00:00:00Z"
}
```

---

## `infinitas registry drafts create`

Create a new draft for a skill.

| Argument | Required | Default | Description |
|---|---|---|---|
| `skill_id` (positional) | yes | | Skill identifier (int) |
| `--base-version-id` | no | `None` | Base skill_version id |
| `--content-ref` | no | `''` | Content locator/ref |
| `--metadata-json` | no | `'{}'` | Draft metadata JSON object |

API: `POST /api/v1/skills/{skill_id}/drafts`

Example response:

```json
{
  "id": 10,
  "skill_id": 1,
  "base_version_id": null,
  "state": "open",
  "content_mode": "ref",
  "content_ref": "",
  "content_artifact_id": null,
  "metadata": {},
  "updated_by_principal_id": 1,
  "updated_at": "2026-04-22T00:00:00Z"
}
```

---

## `infinitas registry drafts update`

Update an existing draft.

| Argument | Required | Default | Description |
|---|---|---|---|
| `draft_id` (positional) | yes | | Draft identifier (int) |
| `--content-ref` | no | `None` | Updated content ref |
| `--metadata-json` | no | `None` | Updated metadata JSON object |

At least one flag is required; the CLI exits with code 1 if neither is provided.

API: `PATCH /api/v1/drafts/{draft_id}`

Example response:

```json
{
  "id": 10,
  "skill_id": 1,
  "base_version_id": null,
  "state": "open",
  "content_mode": "ref",
  "content_ref": "sha256:abc123",
  "content_artifact_id": null,
  "metadata": {"key": "value"},
  "updated_by_principal_id": 1,
  "updated_at": "2026-04-22T00:01:00Z"
}
```

---

## `infinitas registry drafts seal`

Seal a draft, producing a versioned skill release candidate.

| Argument | Required | Default | Description |
|---|---|---|---|
| `draft_id` (positional) | yes | | Draft identifier (int) |
| `--version` | yes | | Semantic version to create |

API: `POST /api/v1/drafts/{draft_id}/seal`

Example response:

```json
{
  "version": "1.0.0",
  "draft": {
    "state": "sealed"
  },
  "skill_version": {
    "id": 5,
    "version": "1.0.0",
    "content_digest": "sha256:abc123",
    "metadata_digest": "sha256:def456",
    "sealed_manifest_json": "{}",
    "sealed_manifest": {},
    "created_from_draft_id": 10,
    "created_by_principal_id": 1,
    "created_at": "2026-04-22T00:02:00Z"
  }
}
```

---

## `infinitas registry agent-presets create`

Create a new agent preset.

| Argument | Required | Default | Description |
|---|---|---|---|
| `--slug` | yes | | Preset slug |
| `--display-name` | yes | | Display name |
| `--summary` | no | `''` | Summary |
| `--runtime-family` | no | `'openclaw'` | Runtime family |
| `--supported-memory-modes` | no | `['none']` | Space-separated list |
| `--default-memory-mode` | no | `'none'` | Default memory mode |
| `--pinned-skill-dependencies` | no | `[]` | Space-separated list |

API: `POST /api/v1/agent-presets`

---

## `infinitas registry agent-presets create-draft`

Create a draft for an agent preset.

| Argument | Required | Default | Description |
|---|---|---|---|
| `preset_id` (positional) | yes | | Preset identifier (int) |
| `--prompt` | no | `''` | Prompt text |
| `--model` | no | `''` | Model identifier |
| `--tools` | no | `[]` | Space-separated list |

API: `POST /api/v1/agent-presets/{preset_id}/drafts`

---

## `infinitas registry agent-presets seal-draft`

Seal an agent preset draft.

| Argument | Required | Default | Description |
|---|---|---|---|
| `draft_id` (positional) | yes | | Draft identifier (int) |
| `--version` | yes | | Semantic version |

API: `POST /api/v1/agent-preset-drafts/{draft_id}/seal`

---

## `infinitas registry agent-codes create`

Create a new agent code.

| Argument | Required | Default | Description |
|---|---|---|---|
| `--slug` | yes | | Agent code slug |
| `--display-name` | yes | | Display name |
| `--summary` | no | `''` | Summary |
| `--runtime-family` | no | `'openclaw'` | Runtime family |
| `--language` | no | `'python'` | Language |
| `--entrypoint` | yes | | Entrypoint |

API: `POST /api/v1/agent-codes`

---

## `infinitas registry agent-codes create-draft`

Create a draft for an agent code.

| Argument | Required | Default | Description |
|---|---|---|---|
| `code_id` (positional) | yes | | Code identifier (int) |
| `--content-ref` | yes | | Content reference |

API: `POST /api/v1/agent-codes/{code_id}/drafts`

---

## `infinitas registry agent-codes seal-draft`

Seal an agent code draft.

| Argument | Required | Default | Description |
|---|---|---|---|
| `draft_id` (positional) | yes | | Draft identifier (int) |
| `--version` | yes | | Semantic version |

API: `POST /api/v1/agent-code-drafts/{draft_id}/seal`

---

## `infinitas registry releases create`

Create a release from a sealed skill version. Materialization runs in the background; poll with `releases get` until `state` becomes `ready`.

| Argument | Required | Default | Description |
|---|---|---|---|
| `version_id` (positional) | yes | | Skill version identifier (int) |

API: `POST /api/v1/versions/{version_id}/releases`

Example response:

```json
{
  "id": 20,
  "skill_version_id": 5,
  "state": "pending",
  "format_version": "1",
  "manifest_artifact_id": null,
  "bundle_artifact_id": null,
  "signature_artifact_id": null,
  "provenance_artifact_id": null,
  "created_by_principal_id": 1,
  "created_at": "2026-04-22T00:03:00Z",
  "ready_at": null,
  "platform_compatibility": {}
}
```

---

## `infinitas registry releases get`

Retrieve a release by its identifier.

| Argument | Required | Default | Description |
|---|---|---|---|
| `release_id` (positional) | yes | | Release identifier (int) |

API: `GET /api/v1/releases/{release_id}`

Example response:

```json
{
  "id": 20,
  "skill_version_id": 5,
  "state": "ready",
  "format_version": "1",
  "manifest_artifact_id": 100,
  "bundle_artifact_id": 101,
  "signature_artifact_id": 102,
  "provenance_artifact_id": 103,
  "created_by_principal_id": 1,
  "created_at": "2026-04-22T00:03:00Z",
  "ready_at": "2026-04-22T00:03:30Z",
  "platform_compatibility": {}
}
```

---

## `infinitas registry releases artifacts`

List artifacts belonging to a release.

| Argument | Required | Default | Description |
|---|---|---|---|
| `release_id` (positional) | yes | | Release identifier (int) |

API: `GET /api/v1/releases/{release_id}/artifacts`

Example response:

```json
{
  "items": [
    {
      "id": 100,
      "release_id": 20,
      "kind": "manifest",
      "storage_uri": "s3://bucket/manifest.json",
      "sha256": "sha256:abc123",
      "size_bytes": 2048,
      "created_at": "2026-04-22T00:03:15Z"
    }
  ],
  "total": 1
}
```

---

## `infinitas registry exposures create`

Create an exposure for a release.

| Argument | Required | Default | Description |
|---|---|---|---|
| `release_id` (positional) | yes | | Release identifier (int) |
| `--audience-type` | yes | | One of: `private`, `grant`, `public` |
| `--listing-mode` | no | `'listed'` | Listing mode |
| `--install-mode` | no | `'enabled'` | Install mode |
| `--requested-review-mode` | no | `'none'` | Requested review mode |

API: `POST /api/v1/releases/{release_id}/exposures`

Example response:

```json
{
  "id": 30,
  "release_id": 20,
  "audience_type": "private",
  "listing_mode": "listed",
  "install_mode": "enabled",
  "review_requirement": "none",
  "requested_review_mode": "none",
  "state": "active",
  "requested_by_principal_id": 1,
  "policy_snapshot": {},
  "activated_at": null,
  "ended_at": null
}
```

---

## `infinitas registry exposures update`

Update an existing exposure.

| Argument | Required | Default | Description |
|---|---|---|---|
| `exposure_id` (positional) | yes | | Exposure identifier (int) |
| `--listing-mode` | no | `None` | Updated listing mode |
| `--install-mode` | no | `None` | Updated install mode |
| `--requested-review-mode` | no | `None` | Updated requested review mode |

At least one flag is required.

API: `PATCH /api/v1/exposures/{exposure_id}`

---

## `infinitas registry exposures activate`

Activate an exposure.

| Argument | Required | Default | Description |
|---|---|---|---|
| `exposure_id` (positional) | yes | | Exposure identifier (int) |

API: `POST /api/v1/exposures/{exposure_id}/activate`

---

## `infinitas registry exposures revoke`

Revoke an exposure.

| Argument | Required | Default | Description |
|---|---|---|---|
| `exposure_id` (positional) | yes | | Exposure identifier (int) |

API: `POST /api/v1/exposures/{exposure_id}/revoke`

---

## `infinitas registry grants`

**Status: NOT IMPLEMENTED** -- all subcommands are stubs that exit with code 1.

### `infinitas registry grants list`

> "grant listing API is not available yet"

### `infinitas registry grants create-token`

| Argument | Required | Default | Description |
|---|---|---|---|
| `grant_id` (positional) | yes | | Grant identifier (int) |

> "grant token issuing API is not available yet"

### `infinitas registry grants revoke`

| Argument | Required | Default | Description |
|---|---|---|---|
| `grant_id` (positional) | yes | | Grant identifier (int) |

> "grant revoke API is not available yet"

---

## `infinitas registry tokens me`

Return information about the currently authenticated principal.

| Argument | Required | Default | Description |
|---|---|---|---|
| *(none)* | | | |

API: `GET /api/v1/access/me`

Example response:

```json
{
  "credential_id": "cred_abc123",
  "credential_type": "api_token",
  "principal_id": 1,
  "principal_kind": "user",
  "principal_slug": "alice",
  "user_id": 1,
  "username": "alice",
  "scopes": ["read", "write"]
}
```

---

## `infinitas registry tokens check-release`

Check whether the current token has access to a release.

| Argument | Required | Default | Description |
|---|---|---|---|
| `release_id` (positional) | yes | | Release identifier (int) |

API: `GET /api/v1/access/releases/{release_id}/check`

Example response:

```json
{
  "ok": true,
  "release_id": 20,
  "credential_type": "api_token",
  "principal_id": 1,
  "scope_granted": "read"
}
```

---

## `infinitas registry reviews open-case`

Open a review case for an exposure.

| Argument | Required | Default | Description |
|---|---|---|---|
| `exposure_id` (positional) | yes | | Exposure identifier (int) |
| `--mode` | no | `None` | Review mode override: `advisory` or `blocking` |

API: `POST /api/v1/exposures/{exposure_id}/review-cases`

Example response:

```json
{
  "id": 40,
  "exposure_id": 30,
  "policy_id": 1,
  "mode": "advisory",
  "state": "open",
  "opened_by_principal_id": 1,
  "opened_at": "2026-04-22T00:04:00Z",
  "closed_at": null,
  "decisions": []
}
```

---

## `infinitas registry reviews get-case`

Retrieve a review case by its identifier.

| Argument | Required | Default | Description |
|---|---|---|---|
| `review_case_id` (positional) | yes | | Review case identifier (int) |

API: `GET /api/v1/review-cases/{review_case_id}`

Example response:

```json
{
  "id": 40,
  "exposure_id": 30,
  "policy_id": 1,
  "mode": "advisory",
  "state": "open",
  "opened_by_principal_id": 1,
  "opened_at": "2026-04-22T00:04:00Z",
  "closed_at": null,
  "decisions": []
}
```

---

## `infinitas registry reviews decide`

Record a decision on a review case.

| Argument | Required | Default | Description |
|---|---|---|---|
| `review_case_id` (positional) | yes | | Review case identifier (int) |
| `--decision` | yes | | One of: `approve`, `reject`, `comment` |
| `--note` | no | `''` | Decision note |
| `--evidence-json` | no | `'{}'` | Evidence JSON object |

API: `POST /api/v1/review-cases/{review_case_id}/decisions`

Example response:

```json
{
  "id": 40,
  "exposure_id": 30,
  "policy_id": 1,
  "mode": "advisory",
  "state": "closed",
  "opened_by_principal_id": 1,
  "opened_at": "2026-04-22T00:04:00Z",
  "closed_at": "2026-04-22T00:05:00Z",
  "decisions": [
    {
      "id": 1,
      "review_case_id": 40,
      "reviewer_principal_id": 1,
      "decision": "approve",
      "note": "LGTM",
      "evidence": {},
      "created_at": "2026-04-22T00:05:00Z"
    }
  ]
}
```

---

## ID Chaining Reference

IDs produced by one command feed into the next. The full lifecycle chain:

```
skills create         -> id (skill_id)               -> drafts create
drafts create         -> id (draft_id)               -> drafts seal
drafts seal           -> skill_version.id (version_id) -> releases create
releases create       -> id (release_id)             -> exposures create, tokens check-release, releases get/artifacts
exposures create      -> id (exposure_id)            -> reviews open-case
reviews open-case     -> id (review_case_id)         -> reviews decide
```

---

## See Also

- [Quickstart](../guide/quickstart.md)
- [CLI reference](cli-reference.md)
- [Error catalog](error-catalog.md)
