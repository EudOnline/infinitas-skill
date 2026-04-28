---
audience: contributors, frontend maintainers, integrators
owner: repository maintainers
source_of_truth: frontend alignment guide
last_reviewed: 2026-04-08
status: maintained
---

# Frontend Control-Plane Alignment Guide

This guide explains how the frontend should align with the current hosted control plane.

For page-by-page execution work, continue with [Frontend control-plane checklist](frontend-control-plane-checklist.md).

The backend already supports the full private-first lifecycle:

`skill -> draft -> sealed version -> release -> exposure -> review case -> grant/credential -> discovery/install`

The current frontend is only partially aligned with that lifecycle. It has strong read-only coverage for browsing and console visibility, but it does not yet expose most of the lifecycle write actions that the backend already supports.

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

- skills
- drafts
- versions
- releases
- exposures
- review cases
- access credentials and grants

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

### Where the frontend is drifting

The main drift is not conceptual. It is behavioral.

The backend already supports lifecycle mutations, but the frontend mostly stops at read-only views.

Missing or underrepresented frontend capabilities include:

- create skill
- create draft
- edit draft
- seal draft into a version
- create release
- create exposure for a release
- patch exposure settings
- activate exposure
- revoke exposure
- review approve/reject/comment actions
- access grant and credential management workflows

There is also at least one concrete API mismatch in the frontend code:

- `POST /api/skills/{skillId}/use` is referenced in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/static/js/app.js`
- that endpoint does not exist in the backend
- frontend code should not invent shortcut APIs that bypass the lifecycle model

## Product rule the frontend must preserve

The frontend should model the backend as a private-first lifecycle system, not as a generic CRUD dashboard.

That means:

- a release is immutable
- sharing does not modify release contents; it creates or updates exposures around a release
- public exposure is review-gated
- private and authenticated paths can activate directly according to policy
- install and discovery must resolve from materialized release artifacts, not from mutable draft state

If the frontend hides these distinctions, users will misunderstand the system and create invalid expectations.

## What the frontend should do

The frontend should be organized around the actual lifecycle, in this order.

### 1. Authoring flow

The frontend should support:

- create skill
- open skill detail
- create draft under a skill
- edit draft content reference and metadata
- seal draft into a version

Use these backend endpoints:

- `POST /api/v1/skills`
- `GET /api/v1/skills/{skill_id}`
- `POST /api/v1/skills/{skill_id}/drafts`
- `PATCH /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/seal`

Frontend UX guidance:

- skill detail should have a clear primary action to create a draft
- draft detail should show editable fields only while state is `open`
- sealed drafts must become read-only in the UI
- seal should be presented as a deliberate freeze step, not a casual save action

### 2. Release flow

The frontend should support:

- create release from a sealed version
- surface release materialization state
- surface release artifacts once ready

Use these backend endpoints:

- `POST /api/v1/versions/{version_id}/releases`
- `GET /api/v1/releases/{release_id}`
- `GET /api/v1/releases/{release_id}/artifacts`

Frontend UX guidance:

- release creation belongs on version rows and version detail areas
- after release creation, the UI should communicate that materialization is asynchronous
- `preparing` and `ready` must be visible states
- artifact links should appear only when the release is actually ready

### 3. Exposure and sharing flow

The frontend should support:

- create exposure from a ready release
- configure audience, listing mode, install mode, and requested review mode
- patch exposure settings when allowed
- activate exposure when policy permits
- revoke exposure when needed

Use these backend endpoints:

- `POST /api/v1/releases/{release_id}/exposures`
- `PATCH /api/v1/exposures/{exposure_id}`
- `POST /api/v1/exposures/{exposure_id}/activate`
- `POST /api/v1/exposures/{exposure_id}/revoke`

Frontend UX guidance:

- sharing UI should be action-oriented, not table-only
- audience choice must explain policy consequences
- public exposure must explicitly warn that blocking review is required
- private, authenticated, grant, and public exposures should be shown as distinct channels, not one shared visibility toggle

### 4. Review flow

The frontend should support:

- open review case visibility from exposure state
- view review case history and evidence
- submit approve, reject, and comment decisions

Use these backend endpoints:

- `POST /api/v1/exposures/{exposure_id}/review-cases`
- `GET /api/v1/review-cases/{review_case_id}`
- `POST /api/v1/review-cases/{review_case_id}/decisions`

Frontend UX guidance:

- review inbox should allow action, not only inspection
- blocking review outcomes should clearly explain downstream exposure state changes
- approving a blocking review should be presented as activating the public path
- rejecting a blocking review should be presented as closing that public path

### 5. Access flow

The frontend should support:

- viewing current credential identity and scopes
- checking whether a principal can access a release
- eventually managing grants and credentials if this becomes a supported UI workflow

Supported backend endpoints today:

- `GET /api/v1/access/me`
- `GET /api/v1/access/releases/{release_id}/check`

Frontend UX guidance:

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
