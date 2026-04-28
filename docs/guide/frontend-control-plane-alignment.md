---
audience: contributors, frontend maintainers, integrators
owner: repository maintainers
source_of_truth: frontend alignment guide
last_reviewed: 2026-04-28
status: maintained
---

# Frontend Control-Plane Alignment Guide

This guide explains how the frontend should align with the current hosted control plane.

For page-by-page execution work, continue with [Frontend control-plane checklist](frontend-control-plane-checklist.md).

The backend still supports the full private-first lifecycle internally:

`skill -> draft -> sealed version -> release -> exposure -> review case -> grant/credential -> discovery/install`

The browser product is no longer a lifecycle authoring console. It is a human-admin distribution
console that exposes Objects, Releases, Visibility, Tokens, Share Links, and Activity. Agent
creation and publishing are API/CLI workflows that use the publish facade.

## Current assessment

## Latest frontend contract

As of 2026-04-08, frontend work should treat OpenClaw runtime fields as first-class UI data rather than optional compatibility extras.

### Primary runtime fields the frontend should read

For discovery, search, inspect, install, and release-readiness views, prefer these fields:

- `runtime.platform`
- `runtime.readiness.status`
- `runtime_readiness`
- `workspace_targets`
- `runtime.install_targets.workspace`
- `runtime.install_targets.shared`
- `runtime.plugin_capabilities`
- `background_tasks`
- `subagents`

Operational rule:

- treat `runtime.readiness.status` and top-level `runtime_readiness` as the current UI-facing readiness signal
- treat `workspace_targets` as the short display list for install location hints
- treat `runtime.install_targets.*` as the structured source of truth for install destination breakdown

### Release-readiness fields the frontend should read

Release UI should now treat OpenClaw as the only maintained runtime gate.

Prefer these fields from `release.platform_compatibility`:

- `canonical_runtime_platform`
- `canonical_runtime`
- `blocking_platforms`
- `historical_platforms`
- `verified_support`

Operational rule:

- show blocking state from `canonical_runtime` and `blocking_platforms`
- do not block the UI on stale Codex or Claude historical evidence alone
- historical platform rows can still be rendered from `verified_support`, but they are audit context, not the primary readiness decision

### Skill contract fields the frontend should read

For OpenClaw skill validation or authoring helpers, prefer:

- `verification.required_runtimes`
- `verification.smoke_prompts`
- `verification.legacy.required_platforms`

Operational rule:

- use `required_runtimes` as the primary field in new UI
- only show `legacy.required_platforms` when you explicitly need migration or historical context
- do not introduce new frontend code that treats `required_platforms` as the preferred field name

### Search result shape the frontend can now rely on

`GET /api/search` now returns runtime metadata for:

- public snapshot search
- authenticated `me` search
- grant search

Each skill row can now include:

- `install_scope`
- `install_ref`
- `install_api_path`
- `runtime`
- `runtime_readiness`
- `workspace_targets`

Frontend guidance:

- global search results should show runtime-readiness badges consistently across public, me, and grant scopes
- install affordances can safely derive quick hints from `workspace_targets`
- keep the existing UI style, but stop treating runtime information as private-only or detail-page-only data

### What is already aligned

The frontend and backend agree on the main domain objects:

- Objects: `skill`, `agent_preset`, and `agent_code`
- Releases
- Visibility
- Tokens
- Share Links
- Activity

The current maintained web admin flow is:

- `/library`
- `/library/{object_id}`
- `/library/{object_id}/releases/{release_id}`
- `/access`
- `/shares`
- `/activity`
- `/settings`

The frontend also correctly uses the supported browser-facing APIs for:

- token login/logout
- session probing
- background preferences
- search

### Current product API surface

The web and agent product contract is:

- `GET /api/library`
- `GET /api/library/{object_id}`
- `GET /api/library/{object_id}/releases`
- `PUT /api/publish/objects/{slug}`
- `POST /api/publish/objects/{object_id}/releases`
- `GET /api/publish/releases/{release_id}/status`
- `POST /api/objects/{object_id}/tokens`
- `GET /api/objects/{object_id}/tokens`
- `POST /api/tokens/{token_id}/revoke`
- `POST /api/releases/{release_id}/share-links`
- `GET /api/releases/{release_id}/share-links`
- `POST /api/share-links/{share_id}/resolve`
- `POST /api/share-links/{share_id}/revoke`
- `GET /api/activity`
- `GET /api/tokens/{token_id}/activity`
- `GET /api/share-links/{share_id}/activity`

There is also at least one concrete API mismatch in the frontend code:

- `POST /api/skills/{skillId}/use` is referenced in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/static/js/app.js`
- that endpoint does not exist in the backend
- frontend code should not invent shortcut APIs that bypass the lifecycle model

## Product rule the frontend must preserve

The frontend should model the product as a private-first distribution system, not as a generic
CRUD dashboard and not as an authoring-first lifecycle console.

That means:

- a Release is immutable
- sharing does not modify Release contents
- Tokens are scoped managed objects and raw secrets are shown only once
- Share Links can have passwords, expiry, usage limits, and revocation
- Activity should be human-readable and normalized across Tokens, Share Links, Visibility, and Releases
- install and discovery must resolve from materialized Release artifacts, not from mutable draft state

If the frontend hides these distinctions, users will misunderstand the system and create invalid expectations.

## What the frontend should do

The frontend should be organized around distribution workflows, in this order.

### 1. Library flow

The frontend should support:

- browse Objects
- open Object detail
- inspect Release history
- inspect a Release detail page

Use these backend endpoints:

- `GET /api/library`
- `GET /api/library/{object_id}`
- `GET /api/library/{object_id}/releases`

Frontend UX guidance:

- keep Object kinds first-class
- avoid Draft, Seal, Exposure, Grant, Credential, and Review Case vocabulary in primary UI
- route old `/skills` pages to `/library`

### 2. Agent publish flow

The frontend may show publish status, but publish initiation belongs to agents and automation:

- upsert an Object
- publish a Release
- poll status

Use these backend endpoints:

- `PUT /api/publish/objects/{slug}`
- `POST /api/publish/objects/{object_id}/releases`
- `GET /api/publish/releases/{release_id}/status`

Frontend UX guidance:

- do not expose Draft or Seal steps as the primary happy path
- show `preparing` and `ready` status when surfacing publish progress

### 3. Token and share flow

The frontend should support:

- issue reader and publisher Tokens
- list Token metadata without raw secrets
- revoke Tokens
- create passworded Share Links with expiry and usage limits
- resolve and revoke Share Links

Use these backend endpoints:

- `POST /api/objects/{object_id}/tokens`
- `GET /api/objects/{object_id}/tokens`
- `POST /api/tokens/{token_id}/revoke`
- `POST /api/releases/{release_id}/share-links`
- `GET /api/releases/{release_id}/share-links`
- `POST /api/share-links/{share_id}/resolve`
- `POST /api/share-links/{share_id}/revoke`

Frontend UX guidance:

- raw Token values are one-time display only
- revoked, expired, and exhausted Share Links must be visible states
- Share Link password values must never be returned after creation

### 4. Activity flow

The frontend should support:

- list normalized Activity records
- filter Activity by Token or Share Link
- show actor, action, object, release, outcome, and timestamp

Use these backend endpoints:

- `GET /api/activity`
- `GET /api/tokens/{token_id}/activity`
- `GET /api/share-links/{share_id}/activity`

Frontend UX guidance:

- activity copy should use product terms, not internal lifecycle terms

- keep identity and access checks explicit
- do not imply that every logged-in user can access every release
- expose release access as a policy outcome tied to exposure state and audience rules

### 6. Discovery and install flow

The frontend should support:

- browsing public catalog
- browsing accessible personal catalog
- searching both modes
- resolving install targets
- downloading materialized artifacts

Use these backend endpoints:

- `GET /api/v1/catalog/public`
- `GET /api/v1/catalog/me`
- `GET /api/v1/catalog/grant`
- `GET /api/v1/search/public`
- `GET /api/v1/search/me`
- `GET /api/v1/search/grant`
- `GET /api/v1/install/public/{skill_ref}`
- `GET /api/v1/install/me/{skill_ref}`
- `GET /api/v1/install/grant/{skill_ref}`
- `GET /api/search`

Frontend UX guidance:

- global search can keep using `/api/search` for lightweight search UX
- lifecycle console pages should still be able to deep-link into the exact install resolution endpoints
- install views must present immutable artifacts: manifest, bundle, provenance, and signature

## Recommended frontend implementation order

Build the missing UI in lifecycle order, not by page popularity.

### Phase 1: close the authoring gap

Ship these first:

- create skill
- create draft
- edit draft
- seal draft

This gives the console a real write path instead of a read-only shell.

### Phase 2: close the release gap

Ship next:

- create release
- release status polling or refresh
- artifact visibility when ready

Without this, the lifecycle still dead-ends before the registry surface.

### Phase 3: close the sharing gap

Ship next:

- create exposure
- patch exposure
- activate/revoke exposure
- audience and review policy messaging

This is the minimum needed to make the private-first model visible and operable.

### Phase 4: close the review gap

Ship next:

- actionable review inbox
- approve/reject/comment submission
- exposure state feedback after decisions

This is required before public release management can be considered complete.

### Phase 5: improve access and discovery UX

Ship after core lifecycle actions are in place:

- access check helpers
- grant-oriented discovery UX
- install detail UX
- registry metadata and artifact download affordances

## Frontend rules to avoid future drift

### Do not invent shortcut APIs

Do not add frontend-only endpoints like `/api/skills/{id}/use` unless the backend explicitly adopts them as maintained surfaces.

Prefer the canonical lifecycle endpoints already exposed under `/api/v1`.

### Do not collapse domain objects into one page-level abstraction

The UI should not pretend that:

- a draft is a release
- a release is an exposure
- a visibility toggle replaces review policy
- search results are installable before artifacts exist

Keep the backend domain boundaries visible in the frontend.

### Treat state as policy-bearing, not decorative

These states are operationally meaningful and should drive UI affordances:

- draft: `open`, `sealed`
- release: `preparing`, `ready`
- exposure: `pending_policy`, `review_open`, `active`, `rejected`, `revoked`
- review case: `open`, `approved`, `rejected`

Buttons, warnings, and next actions should follow those states.

### Prefer additive UI over replacing the current read-only console

The current console pages already provide useful overview and detail pages.

The best next step is to add action panels, forms, and mutation flows into those pages rather than replacing them with a new disconnected UI layer.

## Definition of frontend completion

The frontend can be considered aligned with the backend when a maintainer can complete this end-to-end flow from the browser:

1. create a skill
2. create and edit a draft
3. seal the draft into a version
4. create a release
5. wait for the release to become ready
6. create a private or grant exposure
7. create a public exposure
8. approve or reject the resulting review case
9. verify discovery/install behavior from the appropriate audience view

Until that browser flow exists, the frontend should be described as partially complete rather than complete.

## Suggested follow-up engineering work

- remove or replace the dead `/api/skills/{id}/use` frontend path
- add lifecycle mutation UI to the existing console pages
- add end-to-end UI tests that exercise authoring, release, exposure, and review actions through the browser-facing flows
- keep docs and UI language consistent with the private-first lifecycle model
