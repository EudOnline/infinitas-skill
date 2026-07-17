---
audience: contributors, frontend maintainers, integrators
owner: repository maintainers
source_of_truth: frontend implementation checklist
last_reviewed: 2026-06-01
status: maintained
---

# Frontend Control-Plane Implementation Checklist

Use this checklist after reading [Frontend control-plane alignment](frontend-control-plane-alignment.md).

The old lifecycle model is not maintained for frontend delivery. Legacy routes are removed, and all new work must follow the canonical `object/release/exposure/distribution` model.

This page keeps frontend execution focused on the maintained browser surface.

## Maintained pages

New browser work should land on:

- `/manage` — consolidated admin console
- `/library/{object_id}` — object detail
- `/library/{object_id}/releases/{release_id}` — release detail
- `/settings`

Only `/manage` and the maintained `/library/{object_id}` detail routes are supported; removed console aliases return 404.

## Maintained API checklist

Use these endpoints for new frontend work:

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

## Page-level checks

For maintained browser work, keep these checks true:

- `/manage` stays focused on object/release distribution, token management, share-link management, and audit history
- `/settings` stays focused on environment and operator settings

## Never reintroduce

Do not reintroduce any legacy primary-flow copy, navigation, or controls into maintained pages.

If older authoring paths still appear in code, treat them as migration context only and translate the work back into the canonical `object/release/exposure/distribution` model before shipping.
