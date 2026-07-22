---
audience: Coolify operators and release maintainers
owner: repository maintainers
source_of_truth: docker-compose.coolify.yml and hosted runtime contract
last_reviewed: 2026-07-21
status: maintained
---

# Deploy the Hosted Registry on Coolify

This is the production installation path for a single Coolify server. It deploys one API
container and one worker against the same SQLite database, writable Git repository, artifact
store, backup directory, and runtime home.

The supported v0.1 topology is deliberately single-node:

- `app` replicas: exactly `1`
- `worker` replicas: exactly `1`
- database: SQLite on the `infinitas-data` volume
- artifacts: filesystem storage on the `infinitas-artifacts` volume
- HTTPS and public routing: Coolify proxy

Do not horizontally scale either service. Multi-node operation and PostgreSQL are not current
production claims.

The app emits a server-generated `X-Request-ID` on every HTTP response and includes it in JSON
logs. Keep that header when escalating a failed request so Coolify log searches can isolate the
request without exposing credentials.

## 1. Prepare the domain and secrets

Create a DNS record such as `skills.example.com` pointing to the Coolify server. Coolify will
provision HTTPS after the domain is attached to the `app` service.

Generate independent values locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"  # session secret
python -c "import secrets; print(secrets.token_urlsafe(32))"  # maintainer Agent token
python -c "import secrets; print(secrets.token_urlsafe(32))"  # registry read token
```

Choose a strong browser password separately. The browser password, Agent token, registry read
token, and session secret must not be the same value.

## 2. Create the Coolify resource

1. In the target Coolify project and environment, create a **Docker Compose** resource.
2. Select the Git repository containing this project.
3. Set the Compose file to `docker-compose.coolify.yml`.
4. If `ghcr.io/eudonline/infinitas-skill` is private, add a GHCR registry credential that can
   pull the package before the first deployment.
5. Do not add host port mappings or a custom Docker network. Coolify owns the proxy network.

The checked-in Coolify Compose file uses named volumes. `init-permissions` runs once as root to
make fresh volumes writable by the image's UID/GID `1000:1000`; `init-repo` then creates the
writable runtime repository before `app` and `worker` start.

## 3. Configure environment variables

Add these variables to the Coolify resource before deploying:

```dotenv
INFINITAS_IMAGE=ghcr.io/eudonline/infinitas-skill:sha-<verified-commit>
INFINITAS_SERVER_ALLOWED_HOSTS=["skills.example.com"]
INFINITAS_SERVER_SECRET_KEY=<strong-random-session-secret>
INFINITAS_SERVER_BOOTSTRAP_USERS=[{"username":"maintainer","display_name":"Maintainer","role":"maintainer","password":"<strong-browser-password>","token":"<distinct-agent-token>"}]
INFINITAS_REGISTRY_READ_TOKENS=["<distinct-registry-read-token>"]
```

Important details:

- Use a released version or `sha-*` image tag in production. `latest` is convenient for initial
  evaluation but is not a stable rollback target.
- `INFINITAS_SERVER_ALLOWED_HOSTS` and token settings are JSON arrays, not comma-separated text.
- `INFINITAS_SERVER_BOOTSTRAP_USERS` is a JSON array on one line. Production startup requires at
  least one maintainer with a valid browser password.
- Mark secrets, passwords, and tokens as secret values in Coolify. Do not commit them to Git.
- Leave `INFINITAS_SERVER_REPO_BOOTSTRAP_RESET=0`. Enabling it can replace an invalid runtime
  repository and is only appropriate during deliberate recovery.

Optional variables:

```dotenv
INFINITAS_LOG_LEVEL=INFO
INFINITAS_LOG_FORMAT=json
INFINITAS_SERVER_GIT_BRANCH=main
INFINITAS_SERVER_GIT_ORIGIN_URL=
INFINITAS_SERVER_GIT_USER_NAME=Infinitas Hosted Registry
INFINITAS_SERVER_GIT_USER_EMAIL=hosted-registry@example.com
INFINITAS_SERVER_TRUSTED_PROXIES=[]
INFINITAS_SERVER_CONTENT_PENDING_TTL_HOURS=24
INFINITAS_SERVER_CONTENT_MAX_PENDING_PER_SKILL=10
INFINITAS_SERVER_CONTENT_MAX_PENDING_BYTES_PER_PRINCIPAL=268435456
INFINITAS_WORKER_POLL_INTERVAL=5
INFINITAS_WORKER_HEALTH_MAX_AGE_SECONDS=30
```

Coolify's proxy normally reaches the app over its internal network. Only set
`INFINITAS_SERVER_TRUSTED_PROXIES` when the proxy source addresses are known and stable and you
need forwarded client addresses for rate limiting or audit data. Never trust `0.0.0.0/0` or
`::/0`.

If the runtime repository must push to a private Git remote, set
`INFINITAS_SERVER_GIT_ORIGIN_URL` and provision credentials in the persistent
`infinitas-home` volume. An image-only deployment otherwise starts with a local Git history
seeded from the image snapshot.

## 4. Attach the public domain

Attach `https://skills.example.com` to the child service named `app` and its container port
`8000`.

Do not attach a domain to:

- `worker`
- `init-repo`
- `init-permissions`

The app serves all public surfaces through the same origin:

- `/manage` — browser administration
- `/api/v1/*` — Agent/CLI JSON API
- `/api/v1/registry/*` — hosted discovery and immutable install artifacts
- `/api/v1/system/healthz` — process liveness
- `/api/v1/system/readyz` — database, repository, and artifact readiness

Use `/api/v1/system/readyz` for Coolify health/readiness routing. Keep
`/api/v1/system/healthz` as the independent liveness monitor.

## 5. Deploy and verify

Deploy the resource and wait for both long-running services to become healthy. The two init
services should finish successfully and remain stopped.

Verify from outside the server:

```bash
curl --fail --silent --show-error https://skills.example.com/api/v1/system/healthz
curl --fail --silent --show-error https://skills.example.com/api/v1/system/readyz
curl --fail --silent --show-error \
  -H "Authorization: Bearer $INFINITAS_REGISTRY_READ_TOKEN" \
  https://skills.example.com/api/v1/registry/ai-index.json
```

Then open `https://skills.example.com/login`, sign in with the configured browser password, and
confirm that `/manage` loads.

From the Coolify terminal for `app`, inspect persisted state:

```bash
export PYTHONPATH=/srv/infinitas/repo/src
python3 -m infinitas_skill.cli.main server inspect-state \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --limit 10 \
  --json
```

From the `worker` terminal, verify its heartbeat:

```bash
export PYTHONPATH=/srv/infinitas/repo/src
python3 -m infinitas_skill.cli.main server worker-healthcheck \
  --health-path /srv/infinitas/data/worker.heartbeat \
  --max-age-seconds 30 \
  --json
```

## 6. Configure clients for hosted discovery and install

On each client repository, add the hosted source to `config/registry-sources.json` or the
effective registry-source policy:

```json
{
  "registries": [
    {
      "name": "hosted",
      "kind": "http",
      "base_url": "https://skills.example.com/api/v1/registry",
      "trust": "private",
      "auth": {
        "mode": "token",
        "env": "INFINITAS_REGISTRY_READ_TOKEN"
      }
    }
  ]
}
```

Validate and use it:

```bash
export INFINITAS_REGISTRY_READ_TOKEN=<registry-read-token>
uv run infinitas registry sources --repo-root . check
uv run infinitas registry sources --repo-root . sync hosted --json
uv run infinitas registry catalog build --repo-root .
uv run infinitas discovery search registry --json
uv run infinitas discovery inspect <publisher>/<skill> --json
uv run infinitas install by-name <publisher>/<skill> ~/.openclaw/skills --mode confirm --json
uv run infinitas install report ~/.openclaw/skills --refresh --json
```

The source `base_url` must end in `/api/v1/registry`; it is not the application root. Registry
read tokens protect artifact reads. Publisher/maintainer Agent tokens authenticate JSON
authoring APIs and are configured separately through `INFINITAS_REGISTRY_API_TOKEN` on the
client.

`registry sources sync hosted` atomically caches the hosted AI index, distribution index, and
compatibility catalog under `.cache/registries/hosted`. `registry catalog build` then refreshes
the aggregate discovery index. `discovery inspect` follows the winning entry's HTTP source and
loads its distribution manifest and provenance directly; operators no longer need to mirror
hosted artifacts into the client repository before inspection.

## Configure a persistent release signer

The worker cannot materialize releases without a trusted SSH signing key. Generate a dedicated
key inside a persistent mounted path such as `/srv/infinitas/data`, not inside the image layer:

```bash
ssh-keygen -t ed25519 \
  -f /srv/infinitas/data/infinitas-release-signing-key \
  -C infinitas-production-release \
  -N ''
chmod 600 /srv/infinitas/data/infinitas-release-signing-key
```

Add the public key to `config/allowed_signers` with a stable production identity and commit that
public entry to the source repository. Never commit or print the private key. In Coolify, set:

```text
INFINITAS_SKILL_GIT_SIGNING_KEY=/srv/infinitas/data/infinitas-release-signing-key
```

Redeploy the complete Compose service so both `app` and `worker` receive the same path. Verify the
key exists in the worker container, matches the committed allowed-signer entry, and can complete a
fresh release materialization before declaring the deployment ready for publishing.

## Back up before every upgrade

In the Coolify terminal for `app`, create a consistent repository, SQLite, and artifact backup:

```bash
export PYTHONPATH=/srv/infinitas/repo/src
python3 -m infinitas_skill.cli.main server backup \
  --repo-path /srv/infinitas/repo \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --artifact-path /srv/infinitas/artifacts \
  --output-dir /srv/infinitas/backups \
  --label pre-upgrade \
  --json
```

The `infinitas-backups` volume is still on the same server. Copy completed backup directories to
independent object storage or another host. A backup that disappears with the Coolify server is
not disaster recovery.

When deleting or recreating the Coolify resource, preserve all five named volumes. Ordinary
redeploys should not delete them.

## Upgrade and rollback

1. Record the currently deployed `INFINITAS_IMAGE` value.
2. Create and export a pre-upgrade backup.
3. Change `INFINITAS_IMAGE` to a verified version or `sha-*` tag.
4. Redeploy in Coolify without deleting persistent volumes.
5. Verify readiness, worker heartbeat, browser login, hosted artifact access, and
   `server inspect-state`.

To roll back application code, restore the previous image tag and redeploy. If the deployment
changed persisted state incompatibly, stop `app` and `worker`, restore repo + database +
artifacts from the same backup set, and then start the previous image. Never mix a database from
one point in time with a repository or artifact snapshot from another.

The project has one current schema and one initial migration, not a historical compatibility
chain. During the pre-release period, use a consistent backup/restore or deliberate clean
rebuild instead of expecting old database formats to be adapted.

## Troubleshooting

### `init-permissions` fails

Confirm the service runs as `0:0`, the five named volumes exist, and the server allows the
container to change volume ownership. Do not work around this by running `app` as root.

### `app` fails during startup

Check for malformed JSON environment values and production guards first. Common causes are a
weak secret, missing maintainer password, or an allowed-host list that does not contain the
public domain.

### The domain returns 502/503

Confirm the domain is attached to `app:8000`, not to a worker or init service. Inspect the app
readiness result and the `init-repo` logs. No host `ports:` mapping is required.

### The worker is unhealthy

Check the worker logs and `/srv/infinitas/data/worker.heartbeat`. Both app and worker must mount
the same `infinitas-data` and `infinitas-repo` volumes. Do not add a second worker to mask a
stalled one.

### Login loops or CSRF failures

Use the HTTPS Coolify domain, confirm it is present in `INFINITAS_SERVER_ALLOWED_HOSTS`, and do
not put another proxy in front of Coolify without preserving the original scheme and host.

### Hosted installs return 401

Send a token listed in `INFINITAS_REGISTRY_READ_TOKENS` as a Bearer token and make the client
source reference the matching environment variable. An Agent API token is not automatically a
registry artifact-read token.

## Related runbooks

- [Hosted registry server deployment](server-deployment.md)
- [Hosted registry backup and restore](server-backup-and-restore.md)
- [Runtime configuration](../reference/configuration.md)
- [Discovery and install workflows](../reference/discovery-install-workflows.md)
