---
audience: integrators, API consumers, frontend developers
owner: repository maintainers
source_of_truth: API reference
last_reviewed: 2026-06-01
status: maintained
---

# API Reference

The infinitas hosted registry exposes a REST API built on FastAPI. This document provides a high-level overview of the available endpoints. For the full interactive schema, see the auto-generated documentation.

The old lifecycle model is not maintained as a primary API story. Legacy routes, if they still exist, should be treated only as redirects or migration shims; new integrations must follow the canonical `object/release/exposure/distribution` model.

## Interactive Documentation

When the server is running, the following endpoints are available:

| Endpoint | Description |
|---|---|
| `/api/docs` | Swagger UI — interactive API explorer with request/response examples |
| `/api/redoc` | ReDoc — clean, readable API reference |
| `/openapi.json` | Raw OpenAPI 3.1 schema (machine-readable) |

You can also generate a static `openapi.json` locally:

```bash
uv run python3 scripts/generate-openapi.py
```

## Authentication

The API supports two authentication schemes:

### Bearer Token (API / CLI)

Include an `Authorization: Bearer <token>` header. Tokens are scoped and can be revoked.

```bash
curl -H "Authorization: Bearer your-api-token" \
  https://skills.infinitas.fun/api/v1/access/me
```

### Session Cookie (Browser)

The web UI uses HMAC-signed session cookies (`infinitas_auth_token`). Cookie-authenticated POST requests must include a valid CSRF token via the `X-CSRF-Token` header (double-submit cookie pattern).

## Core Endpoints

### Health & Identity

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/system/healthz` | None | Service health check + user count |
| GET | `/api/v1/access/me` | Bearer or Cookie | Current user identity |
| GET | `/api/v1/profile/me` | Bearer or Cookie | Current user profile |

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/login` | None | Exchange username + password for session |
| POST | `/api/v1/auth/logout` | Cookie | Clear session cookies |
| GET | `/api/v1/auth/csrf` | None | Refresh CSRF token cookie |

### Library & Objects

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/library` | Bearer | List published library entries |
| GET | `/api/v1/library/{id}` | Bearer | Get library entry details |
| GET | `/api/v1/library/{id}/releases` | Bearer | List releases for an object |
| POST | `/api/v1/object-tokens/objects/{object_id}/tokens` | Bearer | Create access token |
| POST | `/api/v1/object-tokens/tokens/{token_id}/revoke` | Bearer | Revoke a token |

### Publishing

The maintained publish surface is object-first and release-first.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/skills` | Bearer | Create a skill object |
| POST | `/api/v1/skills/{skill_id}/versions` | Bearer | Create an immutable skill version directly |
| POST | `/api/v1/versions/{version_id}/releases` | Bearer | Create a release from a version |

### Share Links

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/share-links/releases/{release_id}/share-links` | Bearer | Create password-protected share link |
| GET | `/api/v1/share-links/releases/{release_id}/share-links` | Bearer | List share links for a release |
| POST | `/api/v1/share-links/{share_id}/resolve` | None | Resolve a share link (with password) |
| POST | `/api/v1/share-links/{share_id}/revoke` | Bearer | Revoke a share link |

### Search

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/search` | Bearer | Full-text search across skills |

### Activity

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/activity` | Bearer | Activity log for the current user |

### Background & Theme

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/background/presets` | None | List available background presets |
| POST | `/api/v1/background/set` | Cookie | Set user background preference |

### Admin / Maintainer Endpoints

The following endpoints require `maintainer` role:

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/agent-codes` | List agent codes (NOT IMPLEMENTED) |
| GET | `/api/v1/agent-presets` | List agent presets (NOT IMPLEMENTED) |
| GET | `/api/v1/review-cases/{id}` | Get a review case |
| POST | `/api/v1/review-cases/{id}/decisions` | Act on a review case |

## Error Responses

All API errors return a JSON response with a `detail` field:

```json
{
  "detail": "Not found"
}
```

Common status codes:

| Code | Meaning |
|---|---|
| 400 | Bad Request — invalid input |
| 401 | Unauthorized — missing or invalid credentials |
| 403 | Forbidden — insufficient permissions or CSRF failure |
| 404 | Not Found — resource does not exist |
| 422 | Unprocessable Entity — Pydantic validation error |
| 500 | Internal Server Error |

For a detailed error catalog, see [`error-catalog.md`](error-catalog.md).

## Rate Limiting

The login endpoint (`POST /api/v1/auth/login`) is protected by a pluggable rate limiter. The default
`MemoryRateLimiter` keeps attempt counts in memory; for multi-node deployments, switch to
`DBRateLimiter` which stores counts in the `rate_limit_entries` table. For additional protection,
consider adding a reverse-proxy rate limit (e.g., nginx `limit_req` or Cloudflare).

## OpenAPI Schema

The canonical OpenAPI schema is generated from the running application. To keep a static copy:

```bash
uv run python3 scripts/generate-openapi.py
```
