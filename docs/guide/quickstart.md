---
audience: contributors, operators, automation authors
owner: repository maintainers
source_of_truth: quickstart walkthrough
last_reviewed: 2026-07-20
status: maintained
---

# Quickstart: Web Admin And Agent Workflows

This quickstart reflects the current product split:

- the web app is for human admins
- the API and CLI are for agent publish and read workflows
- the core nouns are Object, Release, Visibility, Token, Share Link, and Activity

## Prerequisites

| Variable | Default | Description |
|---|---|---|
| `INFINITAS_REGISTRY_API_BASE_URL` | `http://127.0.0.1:8000` | Hosted registry base URL |
| `INFINITAS_REGISTRY_API_TOKEN` | — | Admin token for the hosted control plane |

`INFINITAS_REGISTRY_API_TOKEN` is the admin token. Agent tokens are issued from the web admin flow and should be scoped separately.

For a hosted server, complete the [Coolify deployment runbook](../ops/coolify-deployment.md)
or the [generic hosted deployment runbook](../ops/server-deployment.md) first.

## Step 1: Open the web admin console

Human admins start in the web app, not in the lifecycle internals.

Primary routes:

- `/manage` — consolidated admin console with Library, Access, Shares, and Activity sections
- `/library/{object_id}` — object detail
- `/library/{object_id}/releases/{release_id}` — release detail
- `/settings`

The consolidated `/manage` page is the entry point; removed `/access`, `/shares`, and `/activity` aliases return 404.
Use the manage console to browse Objects, inspect Releases, search by name, and change Visibility.
The web app should focus on distribution and governance, not on object creation.

## Step 2: Inspect an Object and its Releases

The v0.1 Library publishes `skill` Objects. The shared Object vocabulary is
extensible, but additional kinds are not part of the current product contract.

For each Object, the web flow should make it easy to:

- read the object summary
- inspect release history
- review the current Visibility
- see how many Tokens and Share Links exist
- open activity related to that Object

## Step 3: Issue agent access

Admins issue agent-facing Tokens from the access flow.

Minimum token types:

- `reader`
- `publisher`

Recommended usage:

- use `reader` for search, metadata reads, and install/fetch access
- use `publisher` for publishing and release creation

Agents without a Token can be granted temporary Release access through a Share Link with
an expiry and optional password. Share credentials use an explicit exchange flow:

1. Create the link and retain its `resolve_url`. For a passwordless link, also retain the
   one-time `resolve_secret` returned by creation.
2. POST the password or resolve secret to `resolve_url`.
3. Read `access_token` from the successful response.
4. Send that token as a Bearer credential to the returned grant `install_url`.

The share password/secret is not accepted directly as a Bearer token.

## Step 4: Publish through the agent-facing API

Object creation and release production are agent-driven. The canonical publish contract is:

```text
POST /api/v1/skills
POST /api/v1/skills/{skill_id}/content
POST /api/v1/versions/{version_id}/releases
GET /api/v1/releases/{release_id}
```

Recommended flow:

1. Create the Object with `POST /api/v1/skills`.
2. Upload a `.tar.gz` content bundle with `POST /api/v1/skills/{skill_id}/content` and retain
   the returned content identifier.
3. Create an immutable version with `POST /api/v1/skills/{skill_id}/versions`, referencing that
   content identifier.
4. Create a Release with `POST /api/v1/versions/{version_id}/releases`.
5. Poll `GET /api/v1/releases/{release_id}` until the Release is ready.

The equivalent CLI sequence is:

```bash
export INFINITAS_REGISTRY_API_BASE_URL=https://skills.example.com
export INFINITAS_REGISTRY_API_TOKEN=<publisher-token>

uv run infinitas registry skills create \
  --slug example-skill \
  --display-name "Example Skill" \
  --summary "Example hosted skill"
uv run infinitas registry skills upload-content <skill_id> ./example-skill.tar.gz
uv run infinitas registry versions create <skill_id> \
  --version 1.0.0 \
  --content-id <content_id>
uv run infinitas registry releases create <version_id>
uv run infinitas registry releases get <release_id>
```

IDs in angle brackets come from the preceding JSON response. A version cannot be created from a
local path alone; the validated hosted content upload is required.

## Step 5: Read from the unified library surface

Agents and automation should consume the unified read surface:

```text
GET /api/v1/library
GET /api/v1/library/{object_id}
GET /api/v1/library/{object_id}/releases
GET /api/v1/releases/{release_id}
POST /api/v1/exposures/{exposure_id}/revoke
POST /api/v1/object-tokens/objects/{object_id}/tokens
GET /api/v1/object-tokens/objects/{object_id}/tokens
POST /api/v1/object-tokens/tokens/{token_id}/revoke
POST /api/v1/share-links/releases/{release_id}/share-links
GET /api/v1/share-links/releases/{release_id}/share-links
POST /api/v1/share-links/{share_id}/resolve
POST /api/v1/share-links/{share_id}/revoke
GET /api/v1/activity
```

This keeps read and governance actions centered on Objects and Releases instead of lifecycle internals.

## Step 6: Build the new frontend with `kimi cli`

All net-new frontend layout and interaction work for the admin cutover must be generated and iterated with `kimi cli`.

Hand edits should be limited to:

- FastAPI route wiring
- template integration glue
- bug fixes
- focused accessibility and performance follow-up work

## See also

- [Web admin and agent product contract](../specs/web-admin-agent-product-contract.md)
- [Registry CLI reference](../reference/registry-cli.md)
- [Error catalog](../reference/error-catalog.md)
- [CLI reference](../reference/cli-reference.md)
- [Coolify deployment](../ops/coolify-deployment.md)
