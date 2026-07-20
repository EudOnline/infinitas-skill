---
audience: operators and contributors
owner: repository maintainers
source_of_truth: server/settings.py and container runtime entrypoints
last_reviewed: 2026-07-20
status: maintained
---

# Runtime Configuration

The hosted service reads configuration from environment variables. The supported production
profile is one app and one worker on a single node, using SQLite and filesystem-backed
artifacts. See the [Coolify deployment runbook](../ops/coolify-deployment.md) for a complete
container installation.

## Required in production

| Variable | Required value and behavior |
|---|---|
| `INFINITAS_SERVER_ENV` | Must be `production`. Other accepted values are `development` and `test`. |
| `INFINITAS_SERVER_SECRET_KEY` | Random value of at least 32 characters. Weak/default patterns and low-entropy values are rejected. |
| `INFINITAS_SERVER_ALLOWED_HOSTS` | Non-empty JSON array of hostnames, for example `["skills.example.com"]`. Include the public domain without a URL scheme. |
| `INFINITAS_SERVER_BOOTSTRAP_USERS` | Non-empty JSON array. At least one `maintainer` must have a valid browser password. A user's password and Agent token must differ. |

Generate a session secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Example bootstrap configuration:

```json
[
  {
    "username": "maintainer",
    "display_name": "Maintainer",
    "role": "maintainer",
    "password": "a-strong-browser-password",
    "token": "a-distinct-agent-token"
  }
]
```

Bootstrap users are configuration-managed identities. Changing a configured password or token
rotates the stored credential during the next application lifespan startup; unchanged passwords
are not rehashed. The product does not currently provide complete user/team CRUD.

## Persistent state

| Variable | Container recommendation | Description |
|---|---|---|
| `INFINITAS_SERVER_DATABASE_URL` | `sqlite:////srv/infinitas/data/server.db` | SQLAlchemy database URL. Defaults to `.state/server.db` outside the container deployment. |
| `INFINITAS_SERVER_REPO_PATH` | `/srv/infinitas/repo` | Writable source-of-truth Git worktree. |
| `INFINITAS_SERVER_ARTIFACT_PATH` | `/srv/infinitas/artifacts` | Hosted `/api/v1/registry/*` artifact root. |
| `INFINITAS_SERVER_REPO_LOCK_PATH` | `/srv/infinitas/data/repo.lock` | Cross-process lock used while bootstrapping the runtime repository. |
| `HOME` | `/srv/infinitas/home` | Persistent Git/SSH client home for optional push and mirror credentials. |
| `INFINITAS_BACKUP_OUTPUT_DIR` | `/srv/infinitas/backups` | Default deployment path used by backup operations. The backup CLI still receives `--output-dir` explicitly. |

All of these paths must survive a redeploy. In Coolify they are named volumes; in generic
Compose they are bind mounts.

The runtime includes a PostgreSQL driver and accepts PostgreSQL URLs for development evaluation,
but PostgreSQL is not a release-supported production profile until health checks,
backup/restore, concurrency behavior, and the CI matrix are validated end to end.

## Hosted registry reads and proxy trust

| Variable | Default | Description |
|---|---|---|
| `INFINITAS_REGISTRY_READ_TOKENS` | `[]` | JSON array of bearer tokens accepted by `/api/v1/registry/*`. An empty list makes hosted artifact reads public. |
| `INFINITAS_SERVER_TRUSTED_PROXIES` | `[]` | JSON array of trusted proxy IP addresses/networks used when resolving forwarded client addresses. |
| `INFINITAS_SERVER_SECURE_COOKIES` | automatic | Optional boolean override. By default cookies become secure when the request or `X-Forwarded-Proto` is HTTPS. |

Only trust known proxy addresses. Never configure `0.0.0.0/0` or `::/0`. Registry read tokens
are distinct from browser passwords and Agent API tokens.

## Pending content limits

| Variable | Default | Description |
|---|---:|---|
| `INFINITAS_SERVER_CONTENT_PENDING_TTL_HOURS` | `24` | Lifetime of a validated upload before version creation. |
| `INFINITAS_SERVER_CONTENT_MAX_PENDING_PER_SKILL` | `10` | Maximum pending uploads per Skill. |
| `INFINITAS_SERVER_CONTENT_MAX_PENDING_BYTES_PER_PRINCIPAL` | `268435456` | Maximum pending bytes per publisher (256 MiB). |

All three values must be positive integers. Expired content is rejected during version creation,
pruned opportunistically on later uploads, and processed by the production startup cleanup job.
Files created by a request are removed if the surrounding database transaction rolls back.

## Runtime repository bootstrap and Git

The container image carries a repository snapshot under `/opt/infinitas/bundle`. On first boot,
the entrypoint seeds an empty writable repository and synchronizes generated catalog artifacts.

| Variable | Default | Description |
|---|---|---|
| `INFINITAS_BUNDLED_REPO_PATH` | `/opt/infinitas/bundle` | Read-only repository snapshot packaged in the image. |
| `INFINITAS_SERVER_GIT_BRANCH` | `main` | Branch created for an image-seeded runtime repository. |
| `INFINITAS_SERVER_GIT_ORIGIN_URL` | empty | Optional origin configured on the runtime repository. |
| `INFINITAS_SERVER_GIT_USER_NAME` | `Infinitas Hosted Registry` | Git author name used by hosted operations. |
| `INFINITAS_SERVER_GIT_USER_EMAIL` | `hosted-registry@example.com` | Git author email used by hosted operations. |
| `INFINITAS_SERVER_REPO_BOOTSTRAP_RESET` | `0` | If truthy, permits deliberate replacement of an invalid runtime repo. Keep disabled in normal production. |
| `INFINITAS_SERVER_MIRROR_REMOTE` | empty | Optional named remote used by one-shot mirror automation. |
| `INFINITAS_SERVER_MIRROR_BRANCH` | empty | Optional branch override for mirror automation. |

Image bootstrap creates a fresh local history. To preserve existing upstream history exactly,
pre-seed or restore the runtime repository instead of relying on the image snapshot.

## Worker and operational controls

| Variable | Compose default | Description |
|---|---:|---|
| `INFINITAS_WORKER_POLL_INTERVAL` | `5` | Seconds between worker queue polls. |
| `INFINITAS_WORKER_HEALTH_PATH` | `/srv/infinitas/data/worker.heartbeat` | Shared heartbeat file checked by the container health check. |
| `INFINITAS_WORKER_HEALTH_MAX_AGE_SECONDS` | `30` | Maximum accepted heartbeat age. Keep above the refresh interval. |
| `INFINITAS_BACKUP_LABEL` | `nightly` | Label used by the generic Compose one-shot backup service. |
| `INFINITAS_PRUNE_KEEP_LAST` | `7` | Retention count used by the generic Compose prune service. |
| `INFINITAS_INSPECT_LIMIT` | `10` | Number of recent records shown by the generic Compose inspector. |
| `INFINITAS_INSPECT_MAX_QUEUED_JOBS` | `10` | Optional alert threshold. |
| `INFINITAS_INSPECT_MAX_RUNNING_JOBS` | `2` | Optional alert threshold. |
| `INFINITAS_INSPECT_MAX_FAILED_JOBS` | `0` | Optional alert threshold. |
| `INFINITAS_INSPECT_MAX_WARNING_JOBS` | `0` | Optional alert threshold. |
| `INFINITAS_INSPECT_ALERT_WEBHOOK_URL` | empty | Optional alert webhook for state inspection. |
| `INFINITAS_INSPECT_ALERT_FALLBACK_FILE` | deployment-specific | Optional JSON fallback path if webhook delivery is unavailable. |

The Coolify deployment fixes the heartbeat and persistent paths and lets operators run backup,
prune, and inspect commands from a service terminal or scheduled Coolify job.

## Logging

| Variable | Default | Description |
|---|---|---|
| `INFINITAS_LOG_LEVEL` | `INFO` | Python log level; invalid names fall back to `INFO`. |
| `INFINITAS_LOG_FORMAT` | `text` | `text` or `json`. The Coolify Compose file defaults to `json`. |

## Client-side variables

These variables configure a CLI client and are not server secrets:

| Variable | Default | Description |
|---|---|---|
| `INFINITAS_REGISTRY_API_BASE_URL` | `http://127.0.0.1:8000` | Hosted JSON API origin, without `/api/v1`. |
| `INFINITAS_REGISTRY_API_TOKEN` | empty | Agent/publisher/maintainer Bearer token for JSON APIs. |
| `INFINITAS_REGISTRY_READ_TOKEN` | operator-selected name | Example local variable referenced by `auth.env` in a hosted registry source. |

Development and test environments may use documented fixture defaults. Production validation
cannot be bypassed with an insecure-default flag; startup fails before serving traffic when the
required security configuration is absent or malformed.
