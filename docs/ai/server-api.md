# Hosted server API

The hosted control plane exposes a small token-backed API for submission, review, and publish orchestration.

The same hosted app also exposes a read-only distribution surface for installers. That surface remains immutable-artifact-first under `/registry/*`, and can be left public in dev or protected with dedicated registry bearer tokens in hosted deployments.

## Auth

- Send `Authorization: Bearer <token>`
- `/api/v1/*` accepts bearer tokens directly and maps them to hosted `users.role`
- Maintainer HTML pages can also bootstrap a browser session through `POST /api/auth/login`, which sets the same token into the `infinitas_auth_token` cookie
- Browser UI code can probe `GET /api/auth/me` to restore cookie-backed session state after reloads
- `POST /api/auth/logout` clears the browser session cookie
- `contributor` may create submissions and request validation / review
- `maintainer` may approve, reject, and queue publish requests
- `/registry/*` optionally uses `INFINITAS_REGISTRY_READ_TOKENS` instead of database-backed users

## Endpoints

- `GET /healthz`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /registry/ai-index.json`
- `GET /registry/distributions.json`
- `GET /registry/compatibility.json`
- `GET /registry/discovery-index.json`
- `GET /registry/skills/{publisher}/{skill}/{version}/manifest.json`
- `GET /registry/skills/{publisher}/{skill}/{version}/skill.tar.gz`
- `GET /registry/provenance/{skill}-{version}.json`
- `GET /registry/provenance/{skill}-{version}.json.ssig`
- `GET /registry/catalog/...` (legacy artifact compatibility aliases)
- `GET /api/v1/me`
- `GET /api/v1/submissions`
- `POST /api/v1/submissions`
- `GET /api/v1/submissions/{id}`
- `POST /api/v1/submissions/{id}/request-validation`
- `POST /api/v1/submissions/{id}/request-review`
- `GET /api/v1/reviews`
- `POST /api/v1/reviews/{id}/approve`
- `POST /api/v1/reviews/{id}/reject`
- `GET /api/v1/jobs`
- `GET /api/v1/skills`
- `POST /api/v1/skills/{skill_name}/publish`

## Operator pages

- `GET /login`
- `GET /submissions`
- `GET /reviews`
- `GET /jobs`

These pages are intentionally minimal server-rendered maintainer views for queue inspection; they are not yet a full workflow UI. `/login` and the inline console auth modal both bootstrap the same cookie-backed browser session, while bearer tokens remain the underlying auth primitive.

## CLI mapping

`scripts/registryctl.py` calls the hosted API instead of mutating the repository directly:

- `submissions list`
- `submissions create`
- `submissions request-validation`
- `submissions request-review`
- `reviews list`
- `reviews approve`
- `reviews reject`
- `jobs list`
- `releases publish`

Hosted installers and registry source configs should target the distribution surface with a `base_url` like `https://skills.example.com/registry`.
