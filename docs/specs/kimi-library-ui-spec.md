---
audience: frontend maintainers, kimi cli sessions
owner: repository maintainers
source_of_truth: library admin UI generation spec
last_reviewed: 2026-04-24
status: maintained
---

# Kimi Library UI Spec

Generate the new admin-facing web UI using `kimi cli`.

## Product goal

Replace the old maintainer-console primary information architecture with a human-admin distribution console.

The web app is for people who manage distribution, visibility, access, and audit trails.

The web app is not the primary place to create objects or walk through draft and seal mechanics.

## Visual direction

Preserve the current hosted control plane visual language:

- kawaii layout shell
- current top bar, page framing, spacing rhythm, and card styling
- existing color variables and typography
- existing motion style

Do not invent a new design system.

## IA to generate

Primary navigation:

- Library
- Access
- Shares
- Activity
- Settings

Core pages to generate:

- `server/templates/library.html`
- `server/templates/object-detail.html`
- `server/templates/release-detail-v2.html`
- `server/templates/access-center.html`
- `server/templates/shares.html`
- `server/templates/activity.html`
- `server/templates/settings.html`

Supporting modules to generate:

- `server/static/js/modules/library.js`
- `server/static/js/modules/access-center.js`
- `server/static/js/modules/shares.js`
- `server/static/js/modules/activity.js`

## Copy rules

Use these product nouns in UI copy:

- Object
- Release
- Visibility
- Token
- Share Link
- Activity

Hide these internal nouns from the primary UI:

- Draft
- Seal
- Exposure
- Grant
- Credential
- Review Case

It is acceptable for legacy compatibility screens to keep old copy, but the new pages above must not center those terms.

## Library page requirements

The Library page is the main landing page for authenticated admins.

It must include:

- a strong page title
- a short description explaining that admins can inspect releases, visibility, tokens, and shares
- filter chips or segmented controls for:
  - All
  - Skills
  - Agent Presets
  - Agent Code
- a search input for local filtering
- a responsive card grid of Objects
- each Object card should show:
  - display name
  - object kind
  - short summary
  - current release version when available
  - current visibility
  - token count
  - share link count
  - a clear action to open details

Must not show:

- create skill
- create draft
- seal draft
- create release

## Object detail page requirements

The object detail page should feel like an admin control surface for one object.

It must include:

- object header and summary
- kind badge
- visibility summary
- token/share counters
- section tabs or segmented panels for:
  - Overview
  - Releases
  - Access
  - Shares
- a release list table or cards

## Release detail page requirements

The release page must help an admin inspect one release and govern access.

It must include:

- release header with version and readiness
- visibility summary
- artifact/readiness summary
- links or actions for:
  - back to object
  - open shares
  - inspect access

## Access page requirements

This page is for human admins issuing and reviewing Tokens.

It must include:

- a page title and short explanation
- token type explanations for at least:
  - reader
  - publisher
- a token activity area
- a token inventory list or table

## Shares page requirements

This page is for Share Link operations.

It must include:

- a page title and short explanation
- list of existing share links
- columns or cards showing:
  - target object or release
  - expiry
  - password status
  - usage or access status

## Activity page requirements

This page is for audit visibility.

It must include:

- a page title
- timeline or event list
- filters for object kind or event type if practical

## Settings page requirements

This page is a support page, not the primary workflow.

It should include:

- admin token explanation
- environment and safety notes
- links back to Library and Access

## Data contract assumptions

The generated frontend should assume these route families:

- `/library`
- `/library/{object_id}`
- `/library/{object_id}/releases/{release_id}`
- `/access`
- `/shares`
- `/activity`
- `/settings`

And JSON data from:

- `/api/library`
- `/api/library/{object_id}`
- `/api/library/{object_id}/releases`

## Delivery constraints

- output Jinja templates compatible with the existing FastAPI layout
- output vanilla JS modules compatible with the current app bootstrap
- do not rename existing backend routes
- do not remove old templates in this step
- prioritize responsive layout and readable empty states
