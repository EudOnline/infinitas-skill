---
audience: contributors, frontend maintainers, integrators
owner: repository maintainers
source_of_truth: frontend implementation checklist
last_reviewed: 2026-06-01
status: maintained
---

# Frontend Control-Plane Implementation Checklist

Use this checklist after reading [Frontend control-plane alignment](frontend-control-plane-alignment.md).

The old lifecycle model is not maintained for frontend delivery. Legacy routes exist only as redirects or migration shims, and all new work must follow the canonical `object/release/exposure/distribution` model.

This page keeps frontend execution focused on the maintained browser surface.

## Maintained pages

New browser work should land on:

- `/manage` — consolidated admin console
- `/library/{object_id}` — object detail
- `/library/{object_id}/releases/{release_id}` — release detail
- `/settings`

Old `/library`, `/access`, `/shares`, and `/activity` routes redirect to `/manage`.

## Maintained API checklist

Use these endpoints for new frontend work:

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

## Page-level checks

For maintained browser work, keep these checks true:

- `/manage` stays focused on object/release distribution, token management, share-link management, and audit history
- `/settings` stays focused on environment and operator settings

## Never reintroduce

Do not reintroduce any legacy primary-flow copy, navigation, or controls into maintained pages.

If older authoring paths still appear in code, treat them as migration context only and translate the work back into the canonical `object/release/exposure/distribution` model before shipping.
