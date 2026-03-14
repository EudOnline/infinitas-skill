# Hosted server API

The hosted control plane exposes a small bearer-token API for submission, review, and publish orchestration.

The same hosted app also exposes a read-only distribution surface for installers. That surface is not part of the authenticated control-plane API; it serves immutable registry artifacts from `/registry/*`.

## Auth

- Send `Authorization: Bearer <token>`
- Tokens map to hosted `users.role`
- `contributor` may create submissions and request validation / review
- `maintainer` may approve, reject, and queue publish requests

## Endpoints

- `GET /healthz`
- `GET /registry/ai-index.json`
- `GET /registry/distributions.json`
- `GET /registry/compatibility.json`
- `GET /registry/skills/{publisher}/{skill}/{version}/manifest.json`
- `GET /registry/skills/{publisher}/{skill}/{version}/skill.tar.gz`
- `GET /registry/provenance/{skill}-{version}.json`
- `GET /registry/provenance/{skill}-{version}.json.ssig`
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

Hosted installers and registry source configs should target the distribution surface with a `base_url` like `https://skills.example.com/registry`.
