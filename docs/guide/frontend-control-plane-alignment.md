---
audience: contributors, frontend maintainers, integrators
owner: repository maintainers
source_of_truth: frontend alignment guide
last_reviewed: 2026-06-01
status: maintained
---

# Frontend Control-Plane Alignment Guide

This guide explains how the frontend should align with the current hosted control plane.

The old lifecycle model is not maintained for frontend work. Legacy routes are removed, and new work must follow the canonical `object/release/exposure/distribution` model.

For page-by-page execution work, continue with [Frontend control-plane checklist](frontend-control-plane-checklist.md).

The backend may still run legacy internals behind the publish facade, but those internals are not a maintained browser contract.

## Maintained browser model

The browser product is a human-admin distribution console. It is not a maintained authoring surface.

Frontend work should present these first-class concepts:

- Objects
- Releases
- Visibility
- Tokens
- Share Links
- Activity

The maintained routes are:

- `/manage` — consolidated admin console
- `/library/{object_id}` — object detail
- `/library/{object_id}/releases/{release_id}` — release detail
- `/settings`

## Maintained API contract

Frontend delivery should stay inside these maintained surfaces:

- `GET /api/v1/library`
- `GET /api/v1/library/{object_id}`
- `GET /api/v1/library/{object_id}/releases`
- `POST /api/v1/skills`
- `POST /api/v1/versions/{version_id}/releases`
- `GET /api/v1/releases/{release_id}`
- `POST /api/v1/object-tokens/objects/{object_id}/tokens`
- `GET /api/v1/object-tokens/objects/{object_id}/tokens`
- `POST /api/v1/object-tokens/tokens/{token_id}/revoke`
- `POST /api/v1/share-links/releases/{release_id}/share-links`
- `GET /api/v1/share-links/releases/{release_id}/share-links`
- `POST /api/v1/share-links/{share_id}/resolve`
- `POST /api/v1/share-links/{share_id}/revoke`
- `GET /api/v1/activity`
- `GET /api/v1/activity/tokens/{token_id}/activity`
- `GET /api/v1/activity/share-links/{share_id}/activity`

## Frontend guardrails

New browser work should preserve these rules:

- treat the frontend as a projection over backend truth, not as the owner of release lifecycle state
- keep release distribution centered on the canonical `object/release/exposure/distribution` story
- keep agent publishing on the publish facade or CLI instead of inventing browser-only authoring flows
- do not add compatibility routes for removed browser pages
- avoid reintroducing legacy primary-flow copy or controls into maintained pages
