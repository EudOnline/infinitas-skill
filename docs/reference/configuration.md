---
audience: operators and contributors
owner: repository maintainers
source_of_truth: server/settings.py
last_reviewed: 2026-07-19
status: maintained
---

# Runtime Configuration

The hosted service reads configuration from environment variables. Production requires explicit values for the secret, allowed hosts, bootstrap users, and any registry read tokens.

## Required production settings

```text
INFINITAS_SERVER_ENV=production
INFINITAS_SERVER_SECRET_KEY=<at least 32 random characters>
INFINITAS_SERVER_ALLOWED_HOSTS=["registry.example.com"]
INFINITAS_SERVER_BOOTSTRAP_USERS=[{"username":"admin","display_name":"Admin","role":"maintainer","token":"...","password":"..."}]
```

`INFINITAS_SERVER_DATABASE_URL` defaults to a file-backed SQLite database under
`.state/server.db`. v0.1 supports a durable SQLite URL in a single-node deployment.
The runtime includes the psycopg driver and accepts PostgreSQL URLs for development
evaluation, but PostgreSQL is not a release-supported production profile until its
health checks, backup/restore automation, concurrency behavior, and CI matrix are
validated end to end. `INFINITAS_SERVER_REPO_PATH` and
`INFINITAS_SERVER_ARTIFACT_PATH` should point to durable server-owned storage.

Bootstrap users are configuration-managed identities. Changing a configured password
or token rotates the stored credential during the next application lifespan startup;
unchanged passwords are not rehashed. v0.1 does not provide full user/team CRUD and
does not claim horizontally scaled API or Worker operation.

`INFINITAS_REGISTRY_READ_TOKENS` is a JSON array. When non-empty, hosted `/registry/*` reads require one of these bearer tokens. `INFINITAS_SERVER_TRUSTED_PROXIES` is an optional JSON array used when resolving client addresses behind a trusted proxy.

Pending Hosted content uses three bounded-storage controls:

- `INFINITAS_SERVER_CONTENT_PENDING_TTL_HOURS` — validated upload lifetime, default `24`
- `INFINITAS_SERVER_CONTENT_MAX_PENDING_PER_SKILL` — pending count per Skill, default `10`
- `INFINITAS_SERVER_CONTENT_MAX_PENDING_BYTES_PER_PRINCIPAL` — pending bytes per publisher,
  default `268435456` (256 MiB)

Expired content is rejected during version creation, pruned opportunistically on later uploads,
and processed by the production startup cleanup job. Files created by a request are removed if
the surrounding database transaction rolls back.

Development and test environments may use the documented defaults. Production always
requires explicit secure values: `INFINITAS_SERVER_ALLOW_INSECURE_DEFAULTS` cannot bypass
production validation. Never reuse development secrets in production.
