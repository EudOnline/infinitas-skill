---
audience: integrators, API consumers, frontend developers
owner: repository maintainers
source_of_truth: API reference
last_reviewed: 2026-04-29
status: maintained
---

# API Reference

The infinitas hosted registry exposes a REST API built on FastAPI. This document provides a high-level overview of the available endpoints. For the full interactive schema, see the auto-generated documentation.

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
  https://skills.infinitas.fun/api/v1/me
```

### Session Cookie (Browser)

The web UI uses HMAC-signed session cookies (`infinitas_auth_token`). Cookie-authenticated POST requests must include a valid CSRF token via the `X-CSRF-Token` header (double-submit cookie pattern).

## Core Endpoints

### Health & Identity

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/healthz` | None | Service health check + user count |
| GET | `/api/v1/me` | Bearer or Cookie | Current user identity |

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | None | Exchange username + token for session |
| POST | `/api/auth/logout` | Cookie | Clear session cookies |
| GET | `/api/auth/csrf` | None | Refresh CSRF token cookie |

### Library & Objects

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/library` | Bearer | List published library entries |
| GET | `/api/library/{id}` | Bearer | Get library entry details |
| GET | `/api/library/{id}/releases` | Bearer | List releases for an object |
| POST | `/api/objects/{id}/tokens` | Bearer | Create access token |
| POST | `/api/tokens/{token_id}/revoke` | Bearer | Revoke a token |

### Publishing

| Method | Path | Auth | Description |
|---|---|---|---|
| PUT | `/api/publish/objects/{slug}` | Bearer | Publish or update an object |
| POST | `/api/publish/objects/{object_id}/releases` | Bearer | Publish a release |
| POST | `/api/publish/drafts` | Bearer | Create or update a draft |

### Share Links

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/releases/{id}/share-links` | Bearer | Create password-protected share link |
| POST | `/api/share-links/{id}/resolve` | None | Resolve a share link (with password) |

### Search

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/search` | Bearer | Full-text search across skills |

### Activity

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/activity` | Bearer | Activity log for the current user |

### Background & Theme

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/background/presets` | None | List available background presets |
| POST | `/api/background/set` | Cookie | Set user background preference |

### Admin / Maintainer Endpoints

The following endpoints require `maintainer` role:

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/agent-codes` | List agent codes |
| GET | `/api/v1/agent-presets` | List agent presets |
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

The login endpoint (`POST /api/auth/login`) has an in-memory rate limiter. For high-traffic deployments, consider adding a reverse-proxy rate limit (e.g., nginx `limit_req` or Cloudflare).

## OpenAPI Schema

The canonical OpenAPI schema is generated from the running application. To keep a static copy:

```bash
uv run python3 scripts/generate-openapi.py
```
