# Hosted Server API

The hosted app is now private-first only. There is no supported `submissions / reviews / jobs` control plane anymore.

## Auth

- Bearer token: `Authorization: Bearer <token>`
- Browser session: `POST /api/auth/login` sets `infinitas_auth_token`
- `GET /api/auth/me` restores cookie-backed browser auth
- Hosted user tokens are bridged into private-first principals automatically
- Grant tokens resolve through `credentials.grant_id`

## Control plane endpoints

- `GET /healthz`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/v1/me`
- `GET /api/v1/access/me`
- `GET /api/v1/access/releases/{release_id}/check`
- `POST /api/v1/skills`
- `GET /api/v1/skills/{skill_id}`
- `POST /api/v1/skills/{skill_id}/drafts`
- `PATCH /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/seal`
- `POST /api/v1/versions/{version_id}/releases`
- `GET /api/v1/releases/{release_id}`
- `GET /api/v1/releases/{release_id}/artifacts`
- `POST /api/v1/releases/{release_id}/exposures`
- `PATCH /api/v1/exposures/{exposure_id}`
- `POST /api/v1/exposures/{exposure_id}/activate`
- `POST /api/v1/exposures/{exposure_id}/revoke`
- `POST /api/v1/exposures/{exposure_id}/review-cases`
- `GET /api/v1/review-cases/{review_case_id}`
- `POST /api/v1/review-cases/{review_case_id}/decisions`

## Discovery and install endpoints

- `GET /api/v1/catalog/public`
- `GET /api/v1/catalog/me`
- `GET /api/v1/catalog/grant`
- `GET /api/v1/search/public`
- `GET /api/v1/search/me`
- `GET /api/v1/search/grant`
- `GET /api/v1/install/public/{skill_ref}`
- `GET /api/v1/install/me/{skill_ref}`
- `GET /api/v1/install/grant/{skill_ref}`

When `artifact=manifest|bundle|provenance|signature` is supplied to an install endpoint, the server returns the requested immutable artifact directly.

## Registry surface

The `/registry/*` surface stays as the stable hosted registry contract, but it is now generated entirely from private-first release projections:

- `GET /registry/ai-index.json`
- `GET /registry/discovery-index.json`
- `GET /registry/distributions.json`
- `GET /registry/compatibility.json`
- `GET /registry/skills/{publisher}/{skill}/{version}/manifest.json`
- `GET /registry/skills/{publisher}/{skill}/{version}/skill.tar.gz`
- `GET /registry/provenance/{publisher}--{skill}-{version}.json`
- `GET /registry/provenance/{publisher}--{skill}-{version}.json.ssig`
- `GET /registry/catalog/distributions/...`
- `GET /registry/catalog/provenance/...`

Audience rules:

- no token: public active exposures only
- hosted user token: releases accessible to that principal
- grant token: only the granted release scope

Invalid tokens return `401` on registry metadata and artifact requests.
