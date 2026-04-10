---
audience: contributors, frontend maintainers, integrators
owner: repository maintainers
source_of_truth: frontend implementation checklist
last_reviewed: 2026-04-08
status: maintained
---

# Frontend Control-Plane Implementation Checklist

Use this checklist after reading [Frontend control-plane alignment](frontend-control-plane-alignment.md).

This page turns the lifecycle model into concrete frontend work items. The goal is to let a frontend engineer move page by page, endpoint by endpoint, without having to rediscover the backend contract first.

## Target outcome

When this checklist is complete, a maintainer should be able to finish the full hosted lifecycle from the browser:

1. create a skill
2. create and edit a draft
3. seal the draft into a version
4. create a release and wait for materialization
5. create private, grant, or public exposures
6. approve or reject public review cases
7. validate discovery and install behavior from the correct audience path

## Current frontend baseline

The current frontend already has:

- login and logout
- session probing
- background preferences
- global search
- read-only lifecycle pages for skills, drafts, releases, sharing, access, and review

The current frontend still lacks:

- lifecycle mutation forms
- lifecycle action buttons
- asynchronous action feedback for release materialization
- review decision submission
- exposure management controls
- browser-based end-to-end completion of the private-first flow

## Backend contract map

### Authoring

- `POST /api/v1/skills`
- `GET /api/v1/skills/{skill_id}`
- `POST /api/v1/skills/{skill_id}/drafts`
- `PATCH /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/seal`

### Release

- `POST /api/v1/versions/{version_id}/releases`
- `GET /api/v1/releases/{release_id}`
- `GET /api/v1/releases/{release_id}/artifacts`

### Exposure

- `POST /api/v1/releases/{release_id}/exposures`
- `PATCH /api/v1/exposures/{exposure_id}`
- `POST /api/v1/exposures/{exposure_id}/activate`
- `POST /api/v1/exposures/{exposure_id}/revoke`

### Review

- `POST /api/v1/exposures/{exposure_id}/review-cases`
- `GET /api/v1/review-cases/{review_case_id}`
- `POST /api/v1/review-cases/{review_case_id}/decisions`

### Access

- `GET /api/v1/access/me`
- `GET /api/v1/access/releases/{release_id}/check`

### Discovery and install

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

## Shared frontend work

Before shipping page-specific features, complete these shared tasks.

### Shared task 1: unify lifecycle action plumbing

Files to touch first:

- [server/static/js/app.js](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/static/js/app.js)
- [server/templates/layout-kawaii.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/layout-kawaii.html)

Checklist:

- add one maintained action helper for authenticated `POST` and `PATCH` requests
- centralize JSON error parsing and toast messaging
- centralize optimistic loading states and button disabling
- add a consistent refresh strategy after successful mutations
- remove or replace the dead `useSkill()` path that calls `/api/skills/{id}/use`

Acceptance check:

- there is no remaining frontend code that calls an unsupported lifecycle endpoint
- mutation buttons all show loading, success, and failure feedback consistently

### Shared task 2: expose lifecycle states as UI rules

Files likely involved:

- [server/ui/formatting.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/formatting.py)
- [server/ui/navigation.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/navigation.py)
- [server/templates/skills.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/skills.html)
- [server/templates/skill-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/skill-detail.html)
- [server/templates/draft-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/draft-detail.html)
- [server/templates/release-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/release-detail.html)
- [server/templates/share-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/share-detail.html)
- [server/templates/review-cases.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/review-cases.html)

Checklist:

- make actions depend on backend state, not on page location alone
- surface `open` vs `sealed` draft states as editable vs read-only
- surface `preparing` vs `ready` release states as pending vs installable
- surface `review_open`, `active`, `rejected`, and `revoked` exposure states with clear next actions
- surface `open`, `approved`, and `rejected` review states with clear reviewer messaging

Acceptance check:

- every primary button in the lifecycle is gated by backend state
- the UI never offers an action that the backend would reject as structurally invalid

### Shared task 3: normalize OpenClaw runtime field consumption

Files most likely to change:

- [server/static/js/app.js](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/static/js/app.js)
- [server/templates/skills.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/skills.html)
- [server/templates/skill-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/skill-detail.html)
- [server/templates/release-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/release-detail.html)
- [server/templates/share-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/share-detail.html)

Checklist:

- read `runtime.platform` and `runtime_readiness` from search and discovery payloads
- read `workspace_targets` as the default concise install-target hint
- read `runtime.install_targets.workspace` and `runtime.install_targets.shared` when a structured destination breakdown is needed
- read `release.platform_compatibility.canonical_runtime_platform` and `release.platform_compatibility.canonical_runtime` as the maintained release gate
- treat `release.platform_compatibility.verified_support` as historical context, not the primary blocking decision
- prefer `verification.required_runtimes` in any new skill-contract UI
- if legacy metadata must be shown, render `verification.legacy.required_platforms` with explicit migration wording

Acceptance check:

- public, me, and grant search results render the same runtime badge logic
- release UI highlights OpenClaw canonical readiness rather than triple-platform parity
- no new UI copy presents `required_platforms` as the preferred field name

## Phase 1: authoring flow

### Page: skills overview

Files most likely to change:

- [server/templates/skills.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/skills.html)
- [server/ui/lifecycle.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/lifecycle.py)
- [server/ui/lifecycle_actions.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/lifecycle_actions.py)
- [server/ui/navigation.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/navigation.py)

Checklist:

- add a visible “create skill” entry point on `/skills`
- add a create-skill form with `slug`, `display_name`, `summary`, and optional `default_visibility_profile`
- on success, route the user to the new skill detail page

Acceptance check:

- a maintainer can create a skill from `/skills` without using the API manually

### Page: skill detail

Files most likely to change:

- [server/templates/skill-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/skill-detail.html)
- [server/ui/navigation.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/navigation.py)

Checklist:

- add a “create draft” action on the skill detail page
- add a draft creation form with `base_version_id`, `content_ref`, and `metadata`
- make base version selection optional and clearly scoped to the current skill
- after success, route the user to the draft detail page

Acceptance check:

- a maintainer can create a draft from a skill detail page

### Page: draft detail

Files most likely to change:

- [server/templates/draft-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/draft-detail.html)
- [server/ui/navigation.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/navigation.py)

Checklist:

- render `content_ref` and `metadata` as editable controls while draft state is `open`
- add a save action that calls `PATCH /api/v1/drafts/{draft_id}`
- add a seal form for the target version string
- lock the editing form when the draft becomes `sealed`

Acceptance check:

- an `open` draft can be edited and sealed from the page
- a `sealed` draft is read-only in the browser

## Phase 2: release flow

### Page: skill detail version rows

Files most likely to change:

- [server/templates/skill-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/skill-detail.html)
- [server/ui/navigation.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/navigation.py)

Checklist:

- add a “create release” action for sealed versions that do not yet have a release
- call `POST /api/v1/versions/{version_id}/releases`
- update the version row after creation so the user can navigate to the release detail page

Acceptance check:

- a maintainer can create a release from the version list without leaving the skill page

### Page: release detail

Files most likely to change:

- [server/templates/release-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/release-detail.html)
- [server/ui/navigation.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/navigation.py)

Checklist:

- show release state as soon as a release exists
- when state is `preparing`, show that materialization is asynchronous
- add refresh or polling behavior until the release reaches `ready`
- once ready, show manifest, bundle, provenance, and signature rows as first-class artifacts

Acceptance check:

- a user can create a release, wait for readiness, and inspect artifacts from the browser

## Phase 3: exposure and sharing flow

### Page: release share

Files most likely to change:

- [server/templates/share-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/share-detail.html)
- [server/ui/navigation.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/navigation.py)

Checklist:

- add a “create exposure” form for a ready release
- collect `audience_type`, `listing_mode`, `install_mode`, and `requested_review_mode`
- present audience options as separate channels:
  - private
  - authenticated
  - grant
  - public
- explain that public exposure always becomes review-gated
- show create, patch, activate, and revoke actions inline with each exposure row where allowed

Acceptance check:

- a maintainer can create private, grant, and public exposures from the share page
- the page explains why public exposure behaves differently from private exposure

### Exposure mutation controls

Files most likely to change:

- [server/templates/share-detail.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/share-detail.html)
- [server/static/js/app.js](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/static/js/app.js)

Checklist:

- patch exposure listing mode and install mode with `PATCH /api/v1/exposures/{exposure_id}`
- expose activate action for eligible non-active exposures
- expose revoke action for active or still-open exposures where that is the desired closeout path
- after every mutation, refresh the share page state

Acceptance check:

- exposure controls reflect the latest backend state without requiring a manual full-page reload

## Phase 4: review flow

### Page: review inbox

Files most likely to change:

- [server/templates/review-cases.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/review-cases.html)
- [server/ui/navigation.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/navigation.py)

Checklist:

- add a detail affordance for each review case
- show decisions, notes, and evidence when available
- add approve, reject, and comment actions for open review cases
- submit decisions through `POST /api/v1/review-cases/{review_case_id}/decisions`
- after approval or rejection, refresh the case state and linked exposure state

Acceptance check:

- a reviewer can approve or reject a public exposure from the browser
- after approval, the corresponding exposure becomes active
- after rejection, the corresponding exposure becomes rejected

## Phase 5: access and discovery flow

### Page: access tokens

Files most likely to change:

- [server/templates/access-tokens.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/access-tokens.html)
- [server/ui/navigation.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/ui/navigation.py)

Checklist:

- add current identity and scope visibility using `GET /api/v1/access/me`
- add a lightweight “can this principal access this release?” check using `GET /api/v1/access/releases/{release_id}/check`
- keep grants and credentials visibly separate in the UI

Acceptance check:

- the page can explain why a token does or does not have release access

### Discovery and install surfaces

Files most likely to change:

- [server/templates/index-kawaii.html](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates/index-kawaii.html)
- [server/static/js/app.js](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/static/js/app.js)

Checklist:

- keep `/api/search` for lightweight global search
- add deeper install views or links that resolve through the canonical install endpoints
- show install artifacts as immutable distribution outputs, not mutable source snapshots
- distinguish public, personal, and grant discovery scopes in language and controls

Acceptance check:

- search results can lead the user to an exact install resolution path

## Recommended execution order

Implement in this order:

1. remove the dead unsupported frontend API path
2. add shared mutation plumbing
3. ship create skill
4. ship create and edit draft
5. ship seal draft
6. ship create release and ready-state feedback
7. ship create and manage exposures
8. ship actionable review inbox
9. ship access checks and richer install UX

## Browser-level done checklist

Do not call the frontend complete until all of these are true:

- create skill works from `/skills`
- create draft works from skill detail
- editing draft works while state is `open`
- sealing draft works from draft detail
- creating release works from a sealed version
- release readiness is visible from the browser
- exposure creation works from the share page
- public exposure review can be approved or rejected from the browser
- discovery and install behavior can be validated without dropping to raw API calls

## Test checklist

Tests should expand from the current read-only UI round-trip into action flows.

Files to extend first:

- [tests/integration/test_private_registry_ui.py](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_private_registry_ui.py)

Add coverage for:

- creating a skill through the browser-facing flow
- creating and sealing a draft through the browser-facing flow
- creating a release and observing `preparing` to `ready`
- creating a public exposure and approving the review case
- verifying the share page and review page update correctly after mutations

## Notes for frontend engineers

- prefer adding actions into the existing console pages instead of replacing the current UI shell
- keep backend state names visible enough that debugging remains easy
- avoid flattening `release` and `exposure` into the same concept in the interface
- prefer server-backed truth over local heuristics when deciding which action to show next
