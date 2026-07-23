---
audience: agent developers, CLI maintainers, integrators
owner: repository maintainers
source_of_truth: FastAPI OpenAPI schema
last_reviewed: 2026-07-23
status: maintained
---

# API Reference

The hosted registry exposes server-rendered HTML for human administrators and JSON APIs for Agents, the CLI, and automation. The route families are intentionally separate consumers of shared domain services.

The old lifecycle model is not maintained. The current contract is the canonical `object/release/exposure/distribution` flow described by the routes below.

## OpenAPI

Development environments expose:

- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`
- Schema artifact: `openapi.json`

Regenerate or check the tracked schema with:

```bash
.venv/bin/python scripts/generate-openapi.py
.venv/bin/python scripts/generate-openapi.py --check
```

`--check` does not write files or initialize the database.

## Authentication

### Agent and CLI requests

Use a Bearer credential:

```http
Authorization: Bearer <token>
```

Credential scopes and release access are enforced by the access domain. Registry artifact reads may additionally require the configured registry read token.

### Browser requests

The Web UI uses a signed session cookie. State-changing browser requests require the CSRF token issued by `GET /api/v1/auth/csrf`.

### Share links

Share-link creation returns a `resolve_url`. Passwordless links also return a one-time
`resolve_secret`; store it with the URL because later list responses do not expose it.

`POST /api/v1/share-links/{share_id}/resolve` is an anonymous credential-exchange
endpoint:

- password-protected links send `{"password":"..."}`;
- passwordless links send `{"secret":"<resolve_secret>"}`;
- a successful response returns `access_token` and `install_path`/`install_url`;
- use the returned token as `Authorization: Bearer <access_token>` when requesting the
  grant install route.

The password or resolve secret is never itself a Bearer credential. Expiry and usage
limits are checked atomically, and usage is consumed only by a successful exchange.

## JSON route families

### System and identity

- `GET /api/v1/system/healthz`
- `GET /api/v1/system/readyz`
- `GET /api/v1/access/me`
- `GET /api/v1/auth/me`
- `GET /api/v1/profile/me`
- `GET /api/v1/profile/{credential_id}`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/csrf`

The two `/me` routes serve different contexts: access identity for Agent/API authorization and browser session identity for the Web UI.

`healthz` is a process liveness probe. `readyz` additionally verifies the database,
server-owned git checkout, and artifact directory; it returns `503` with per-dependency
checks when the instance should not receive traffic.

All HTTP responses include an `X-Request-ID` response header. It is a server-generated correlation
identifier for support and log investigation and is not an authentication credential.

### Library and publishing

- `GET /api/v1/library/`
- `GET /api/v1/library/{object_id}`
- `GET /api/v1/library/{object_id}/releases`
- `POST /api/v1/skills`
- `GET /api/v1/skills`
- `GET /api/v1/skills/{skill_id}`
- `POST /api/v1/skills/{skill_id}/archive`
- `POST /api/v1/skills/{skill_id}/content`
- `GET|POST /api/v1/skills/{skill_id}/versions`
- `GET /api/v1/skills/{skill_id}/versions/{version}`
- `POST /api/v1/versions/{version_id}/releases`
- `GET /api/v1/releases/{release_id}`
- `GET /api/v1/releases/{release_id}/exposures`
- `GET /api/v1/releases/{release_id}/artifacts`

Skill content and versions are Agent-owned mutations. Versions are immutable: the same semantic
version may only point to the same content digest. Archive is idempotent and permanently blocks
new content/version writes. Browser routes only expose read views, digest comparison, and Share
Link distribution.

### Visibility and review

- `POST /api/v1/releases/{release_id}/exposures`
- `PATCH /api/v1/exposures/{exposure_id}`
- `POST /api/v1/exposures/{exposure_id}/activate`
- `POST /api/v1/exposures/{exposure_id}/revoke`
- `POST /api/v1/exposures/{exposure_id}/review-cases`
- `GET /api/v1/review-cases/{review_case_id}`
- `POST /api/v1/review-cases/{review_case_id}/decisions`

### Tokens and share links

- `GET|POST /api/v1/object-tokens/objects/{object_id}/tokens`
- `POST /api/v1/object-tokens/tokens/{token_id}/revoke`
- `GET|POST /api/v1/share-links/releases/{release_id}/share-links`
- `POST /api/v1/share-links/{share_id}/resolve`
- `POST /api/v1/share-links/{share_id}/revoke`
- `PATCH /api/v1/credentials/{credential_id}/policy`

### Discovery, catalog, and install

- `GET /api/v1/search`
- `GET /api/v1/catalog/public`
- `GET /api/v1/catalog/me`
- `GET /api/v1/catalog/grant`
- `GET /api/v1/install/public/{skill_ref}`
- `GET /api/v1/install/me/{skill_ref}`
- `GET /api/v1/install/grant/{skill_ref}`
- `GET /api/v1/registry/{registry_path}`
- `GET /api/v1/registry/ai-index.json`
- `GET /api/v1/registry/discovery-index.json`
- `GET /api/v1/registry/distributions.json`
- `GET /api/v1/registry/compatibility.json`

The compatibility document describes current runtime/platform support; it is not an adapter for superseded repository data.

### Activity

- `GET /api/v1/activity/`
- `GET /api/v1/activity/tokens/{token_id}/activity`
- `GET /api/v1/activity/share-links/{share_id}/activity`

## HTML routes

- `GET /`
- `GET /manage`
- `GET /library/{object_id}`
- `GET /library/{object_id}/releases/{release_id}`
- `GET /profile`
- `GET /settings`
- `GET /login`

These routes return `HTMLResponse` and use Cookie + CSRF authentication. They are not aliases for the JSON API.

## Error contract

Domain exceptions are converted at the application boundary into stable HTTP status codes and JSON error payloads. Clients should branch on status and documented error fields rather than parsing human-readable messages.

Common statuses:

- `400` invalid state or request contract;
- `401` missing or invalid authentication;
- `403` authenticated but not authorized;
- `404` resource not found;
- `409` state conflict;
- `422` FastAPI/Pydantic validation failure;
- `429` rate limit exceeded.
- `503` runtime dependency unavailable; retry against a ready instance.

The generated OpenAPI schema is authoritative for request bodies, response models, and endpoint-specific status codes.
