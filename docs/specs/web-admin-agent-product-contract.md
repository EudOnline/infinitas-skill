---
audience: contributors, operators, frontend implementers
owner: repository maintainers
source_of_truth: web admin and agent product contract
last_reviewed: 2026-04-24
status: maintained
---

# Web Admin And Agent Product Contract

This document freezes the target product split for the hosted registry:

- Web is a human-admin distribution console.
- Agent is an API and CLI client for publish and read workflows.
- `skill`, `agent_preset`, and `agent_code` are first-class object types that share the same release core.

## Product vocabulary

Use these terms in product-facing docs and UI copy:

- Object
- Release
- Visibility
- Token
- Share Link
- Activity

Do not expose internal lifecycle wording as the primary web vocabulary:

- Draft
- Seal
- Exposure
- Grant
- Credential
- Review Case

## Personas

### Human admin

Human admins use the web app to:

- browse the Library
- open an Object and inspect its Releases
- search and filter by type, name, and Visibility
- change Release Visibility
- issue and revoke agent Tokens
- inspect Activity
- create Share Links with expiry, password, and limited-use constraints

### Agent user

Agent users do not use the web app as the primary authoring surface. Agents use the API and CLI to:

- upsert an Object identity
- publish new Releases
- poll publish status
- read Library metadata and Release metadata
- install or fetch a Release when access is available through a Token or Share Link

## Object model

Every published item is an Object with a stable identity and a current set of Releases.

Supported kinds:

- `skill`
- `agent_preset`
- `agent_code`

Shared Object fields:

- `id`
- `kind`
- `slug`
- `display_name`
- `summary`
- `default_release`
- `current_visibility`
- `token_count`
- `share_link_count`
- `updated_at`

Type-specific fields stay in a nested payload block so the Library remains uniform.

## Visibility model

Visibility is managed at the Release level.

Minimum supported modes:

- private
- share-link
- public

Rules:

- a Release can be fully public
- a Share Link may target a specific Release version
- Visibility changes are admin actions, not agent authoring actions

## Token model

Tokens are distinct from admin environment credentials.

- `INFINITAS_REGISTRY_API_TOKEN` is the admin token used to operate the hosted control plane
- agent tokens are issued per Object or per admin workflow
- minimum agent token types are `reader` and `publisher`

Token expectations:

- `reader` tokens can read Library metadata and fetch authorized Releases
- `publisher` tokens can publish Object changes and create Releases
- web admins can inspect token activity, revoke tokens, and rotate tokens

## Share Link model

Share Links let an agent without a Token access a specific Release.

Share Link requirements:

- target a single Release
- optional temporary password
- expiry timestamp
- optional usage limit
- auditable access events

## Route map

### Web admin routes

- `/library`
- `/library/{object_id}`
- `/library/{object_id}/releases/{release_id}`
- `/access`
- `/shares`
- `/activity`
- `/settings`

### Agent-facing routes

- `GET /api/library`
- `GET /api/library/{object_id}`
- `GET /api/library/{object_id}/releases`
- `GET /api/releases/{release_id}`
- `PATCH /api/releases/{release_id}/visibility`
- `POST /api/objects/{object_id}/tokens`
- `GET /api/objects/{object_id}/tokens`
- `POST /api/releases/{release_id}/share-links`
- `GET /api/releases/{release_id}/share-links`
- `GET /api/activity`
- `PUT /api/publish/objects/{slug}`
- `POST /api/publish/objects/{object_id}/releases`
- `GET /api/publish/releases/{release_id}/status`

## UX rules

- Web navigation prioritizes Library, Access, Shares, Activity, and Settings.
- The web app is not the primary place to create Objects.
- Skill authoring and release production remain agent-driven workflows.
- `skill` is the default featured Object in the web UI, but the information architecture must support all Object kinds.

## Frontend implementation requirement

All net-new frontend layout and interaction work for this product cutover must be generated and iterated with `kimi cli`.

Hand edits are limited to:

- route wiring
- template integration glue
- bug fixes
- accessibility or performance follow-up fixes after generation
