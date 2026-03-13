# Hosted server API

The hosted control plane exposes a small bearer-token API for submission, review, and publish orchestration.

## Auth

- Send `Authorization: Bearer <token>`
- Tokens map to hosted `users.role`
- `contributor` may create submissions and request validation / review
- `maintainer` may approve, reject, and queue publish requests

## Endpoints

- `GET /healthz`
- `GET /api/v1/me`
- `POST /api/v1/submissions`
- `GET /api/v1/submissions/{id}`
- `POST /api/v1/submissions/{id}/request-validation`
- `POST /api/v1/submissions/{id}/request-review`
- `POST /api/v1/reviews/{id}/approve`
- `POST /api/v1/reviews/{id}/reject`
- `GET /api/v1/skills`
- `POST /api/v1/skills/{skill_name}/publish`

## CLI mapping

`scripts/registryctl.py` calls the hosted API instead of mutating the repository directly:

- `submissions create`
- `submissions request-validation`
- `submissions request-review`
- `reviews approve`
- `reviews reject`
- `releases publish`
