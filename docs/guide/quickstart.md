---
audience: contributors, automation authors
owner: repository maintainers
source_of_truth: quickstart walkthrough
last_reviewed: 2026-04-24
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

## Step 1: Open the web admin console

Human admins start in the web app, not in the lifecycle internals.

Primary routes:

- `/library`
- `/access`
- `/shares`
- `/activity`
- `/settings`

Use `/library` to browse each Object, inspect its Releases, search by name, and change Visibility. The web app should focus on distribution and governance, not on object creation.

## Step 2: Inspect an Object and its Releases

The Library is shared across:

- `skill`
- `agent_preset`
- `agent_code`

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

Agents without a Token can be granted temporary Release access through a Share Link with an expiry and optional password.

## Step 4: Publish through the agent-facing API

Object creation and release production are agent-driven. The canonical publish contract is:

```text
PUT /api/publish/objects/{slug}
POST /api/publish/objects/{object_id}/releases
GET /api/publish/releases/{release_id}/status
```

Recommended flow:

1. Upsert the Object with `PUT /api/publish/objects/{slug}`.
2. Submit release content with `POST /api/publish/objects/{object_id}/releases`.
3. Poll `GET /api/publish/releases/{release_id}/status` until the Release is ready.

Internal draft and sealing mechanics may still exist behind the service boundary, but they are not the primary product story.

## Step 5: Read from the unified library surface

Agents and automation should consume the unified read surface:

```text
GET /api/library
GET /api/library/{object_id}
GET /api/library/{object_id}/releases
GET /api/releases/{release_id}
PATCH /api/releases/{release_id}/visibility
POST /api/objects/{object_id}/tokens
GET /api/objects/{object_id}/tokens
POST /api/releases/{release_id}/share-links
GET /api/releases/{release_id}/share-links
GET /api/activity
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
