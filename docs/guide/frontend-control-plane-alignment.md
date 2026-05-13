---
audience: contributors, frontend maintainers, integrators
owner: repository maintainers
source_of_truth: frontend alignment guide
last_reviewed: 2026-04-28
status: maintained
---

# Frontend Control-Plane Alignment Guide

This guide explains how the frontend should align with the current hosted control plane.

The old lifecycle model is not maintained for frontend work. Legacy routes exist only as redirects or migration shims, and new work must follow the canonical `object/release/exposure/distribution` model.

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

- `/library`
- `/library/{object_id}`
- `/library/{object_id}/releases/{release_id}`
- `/access`
- `/shares`
- `/activity`
- `/settings`

## Maintained API contract

Frontend delivery should stay inside these maintained surfaces:

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

## Frontend guardrails

New browser work should preserve these rules:

- treat the frontend as a projection over backend truth, not as the owner of release lifecycle state
- keep release distribution centered on the canonical `object/release/exposure/distribution` story
- keep agent publishing on the publish facade or CLI instead of inventing browser-only authoring flows
- treat old browser routes only as redirects or migration shims into the maintained pages
- avoid reintroducing legacy primary-flow copy or controls into maintained pages
