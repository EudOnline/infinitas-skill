---
audience: operators and release maintainers
owner: repository maintainers
source_of_truth: hosted deployment runbook
last_reviewed: 2026-03-30
status: maintained
---

# Hosted Registry Server Deployment

This runbook describes the smallest hosted deployment for the server-owned `infinitas-skill` registry.

The recommended single-node deployment shape now includes a generated `systemd` bundle so operators do not have to hand-write service units for the API, worker, and scheduled backups.

## Core services

- **Reverse proxy**: terminate TLS and expose the hosted API plus static artifact paths
- **App**: run `uvicorn server.app:app`
- **Worker**: run the maintained `infinitas server worker` entrypoint on the same host or a trusted sibling process
- **Repo path**: a writable checkout of the private source-of-truth repository
- **Artifact path**: a filesystem directory served over HTTPS for `ai-index.json`, `catalog/`, provenance, and bundles
- **Secrets**: bootstrap user tokens, SSH signing key wiring, and any database credentials

## Required environment

- `INFINITAS_SERVER_ENV=production`
- `INFINITAS_SERVER_DATABASE_URL`
- `INFINITAS_SERVER_SECRET_KEY`
- `INFINITAS_SERVER_BOOTSTRAP_USERS`
- `INFINITAS_SERVER_REPO_PATH`
- `INFINITAS_SERVER_ARTIFACT_PATH`
- optional `INFINITAS_REGISTRY_READ_TOKENS`
- optional `INFINITAS_SERVER_REPO_LOCK_PATH`
- optional `INFINITAS_SERVER_MIRROR_REMOTE`
- optional `INFINITAS_SERVER_MIRROR_BRANCH`

Production safety rails:

- `INFINITAS_SERVER_SECRET_KEY` must not be left empty or set to `change-me`
- `INFINITAS_SERVER_BOOTSTRAP_USERS` must be a non-empty JSON array in production
- fixture defaults now remain available only in `development` or `test` mode, so a misconfigured production deployment fails fast during startup

## Startup sequence

1. Provision the private repo checkout on the server
2. Bootstrap trusted SSH release signing in that checkout
3. Point `INFINITAS_SERVER_REPO_PATH` at the writable checkout
4. Point `INFINITAS_SERVER_ARTIFACT_PATH` at a durable filesystem path
5. Start the API app with `uv run uvicorn server.app:app --host 0.0.0.0 --port 8000`
6. Start a worker loop process that drains queued validate / promote / publish jobs, for example `uv run infinitas server worker --poll-interval 5`
7. Configure the reverse proxy so hosted registry clients reach the API and immutable artifacts over HTTPS

The built-in hosted app now serves immutable distribution artifacts directly from the synchronized artifact root under `/registry/*`. That means operators can expose both the control-plane API and hosted install surface through the same app process, for example:

- `https://skills.example.com/healthz`
- `https://skills.example.com/api/v1/...`
- `https://skills.example.com/registry/ai-index.json`
- `https://skills.example.com/registry/skills/<publisher>/<skill>/<version>/manifest.json`
- `https://skills.example.com/skills`
- `https://skills.example.com/access/tokens`
- `https://skills.example.com/review-cases`

If `INFINITAS_REGISTRY_READ_TOKENS` is unset or empty, `/registry/*` stays public for local/dev compatibility.
If it is set to a JSON array of bearer tokens, hosted installers must send one of those tokens when reading `/registry/*`.

## Container image

The repository now includes a container image path for the hosted registry:

- `Dockerfile` packages the hosted API, worker entrypoints, ops scripts, and templates
- `.github/workflows/container-image.yml` builds `linux/amd64` and `linux/arm64` images
- pull requests build the image without pushing
- pushes to `main`, version tags matching `v*`, and manual workflow runs publish to GHCR as `ghcr.io/<owner>/infinitas-skill`

The workflow emits branch, semver, `sha-*`, and default-branch `latest` tags. The image contains a full runtime snapshot of the repository contents needed by the hosted control plane, and compose seeds that snapshot into a writable runtime repo on first boot.

## Docker Compose deployment

For a single-node container deployment, use the checked-in `docker-compose.yml` plus `.env.compose.example`.

The compose stack assumes:

- the app image is pulled from GHCR or built separately from the same repository
- `INFINITAS_SERVER_REPO_PATH` points at a writable host directory such as `.deploy/repo`
- SQLite, hosted artifacts, backups, and git home state live on durable host paths
- git credentials for push or optional mirror jobs live under the mounted compose home directory

Recommended bootstrap flow:

```bash
cp .env.compose.example .env.compose
mkdir -p .deploy/{repo,data,artifacts,backups,home}

# Edit .env.compose before starting the stack:
# - keep INFINITAS_SERVER_ENV=production
# - replace INFINITAS_SERVER_SECRET_KEY=change-me
# - replace the bootstrap operator tokens in INFINITAS_SERVER_BOOTSTRAP_USERS

# If git push uses SSH, place credentials under .deploy/home/.ssh and ensure permissions are strict.
# Optionally copy or create .deploy/home/.gitconfig for user.name / user.email / signing policy.
# If the runtime repo should push to a remote, set INFINITAS_SERVER_GIT_ORIGIN_URL in .env.compose.

docker compose --env-file .env.compose config
docker compose --env-file .env.compose pull
docker compose --env-file .env.compose run --rm init-repo
docker compose --env-file .env.compose up -d app worker
```

Important runtime detail:

- the bundled repository snapshot lives at `/opt/infinitas/bundle`
- the writable source-of-truth checkout is still `INFINITAS_SERVER_REPO_PATH` such as `/srv/infinitas/repo`
- `init-repo` and the shared container entrypoint bootstrap that runtime repo from the bundled snapshot when the host directory is empty, create a local git history, optionally configure `origin`, and sync `catalog/` into `INFINITAS_SERVER_ARTIFACT_PATH`
- if `.deploy/repo` already contains a valid git worktree, compose reuses it as-is

The default compose environment uses these host mounts:

- `INFINITAS_HOST_REPO_PATH` → mounted writable runtime repo initialized from the image snapshot
- `INFINITAS_HOST_DATA_PATH` → SQLite DB and repo lock
- `INFINITAS_HOST_ARTIFACT_PATH` → hosted `/registry/*` artifact root
- `INFINITAS_HOST_BACKUP_PATH` → backup snapshots and optional inspect fallback files
- `INFINITAS_HOST_HOME_PATH` → `.ssh`, `.gitconfig`, and related git client state for push/mirror operations

Important caveat:

- image-only bootstrap creates a fresh local git history from the bundled snapshot
- if you need the runtime repo to preserve an existing upstream history exactly, restore a backup into `.deploy/repo` or pre-seed that directory yourself before starting compose
- if you only need image-driven deployment plus future worker pushes, setting `INFINITAS_SERVER_GIT_ORIGIN_URL` is usually enough

After the stack is up, validate with:

```bash
docker compose --env-file .env.compose ps
docker compose --env-file .env.compose logs --tail=100 app worker
docker compose --env-file .env.compose --profile ops run --rm inspect
uv run infinitas server healthcheck \
  --api-url http://127.0.0.1:8000 \
  --repo-path .deploy/repo \
  --artifact-path .deploy/artifacts \
  --database-url sqlite:///$PWD/.deploy/data/server.db \
  --json
```

The compose file also exposes one-shot ops helpers behind the `ops` profile:

```bash
docker compose --env-file .env.compose --profile ops run --rm backup
docker compose --env-file .env.compose --profile ops run --rm prune
docker compose --env-file .env.compose --profile ops run --rm inspect
docker compose --env-file .env.compose --profile ops run --rm mirror
```

These services intentionally run on demand. If you want scheduled backups, prune, inspect, or mirror jobs in a compose-based deployment, attach host cron, `systemd` timers, or your existing CI scheduler around the matching one-shot compose commands.

## Health checks

Use the hosted ops health check to verify the minimum single-node deployment contract:

```bash
uv run infinitas server healthcheck \
  --api-url http://127.0.0.1:8000 \
  --repo-path /srv/infinitas/repo \
  --artifact-path /srv/infinitas/artifacts \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --json
```

This checks:

- `GET /healthz` responds with `ok=true`
- the server-owned repo path is a real git worktree
- the artifact directory contains `ai-index.json` and `catalog/`
- the configured SQLite database file exists and answers a simple query

Phase 1 automation validates SQLite deployments only. PostgreSQL health probes can be added later without changing the hosted artifact contract.

For hosted installs on other machines, point the registry source `base_url` at the `/registry` prefix, not the app root.
If the hosted registry requires bearer auth, set the registry source `auth.mode` to `token` and point `auth.env` at the local environment variable that holds one of the configured read tokens.

For operators inspecting queue state manually, the hosted app now exposes private-first maintainer HTML views at `/skills`, `/access/tokens`, and `/review-cases`, and the matching CLI surface is available through:

```bash
python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> skills get <skill-id>
python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> reviews get-case <review-case-id>
python scripts/registryctl.py --base-url https://skills.example.com --token <maintainer-token> jobs list
```

## State inspection

Use the hosted state inspector alongside `infinitas server healthcheck` when you need queue depth and failed-job visibility:

```bash
uv run infinitas server inspect-state \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --limit 10 \
  --max-queued-jobs 10 \
  --max-running-jobs 2 \
  --max-failed-jobs 0 \
  --max-warning-jobs 0 \
  --alert-webhook-url https://ops.example/hooks/infinitas \
  --alert-fallback-file /var/lib/infinitas/alerts/latest-inspect-alert.json \
  --json
```

This summarizes:

- jobs by status
- recent failed jobs with error messages
- recent queued/running jobs
- recent jobs whose logs contain `WARNING:`
- releases grouped by exposure audience and review state

When any configured threshold is exceeded, the script still emits its summary but exits with status code `2`. That makes it suitable for `systemd` oneshot health/alert runs.
This is especially useful for best-effort publish mirror hooks: a publish may still complete successfully while leaving a warning that operators should inspect.
When `--alert-webhook-url` is provided, alerting runs also POST the full JSON summary to that endpoint and record delivery status in the returned `notification` block.
When `--alert-fallback-file` is provided, alerting runs write the same JSON summary to that file whenever webhook delivery is unavailable, including webhook failures or runs with no webhook configured. The returned `notification.fallback` block records whether the fallback write was attempted, whether it succeeded, the target path, and any write error.

This is intentionally SQLite-first for the current single-node deployment shape.

## `systemd` bundle

Generate a ready-to-install deployment bundle with:

```bash
python scripts/render-hosted-systemd.py \
  --output-dir /tmp/infinitas-systemd \
  --repo-root /srv/infinitas/repo \
  --python-bin /srv/infinitas/.venv/bin/python \
  --env-file /etc/infinitas/hosted-registry.env \
  --service-prefix infinitas-hosted \
  --backup-output-dir /srv/infinitas/backups \
  --backup-on-calendar daily \
  --backup-label nightly \
  --prune-on-calendar daily \
  --prune-keep-last 7 \
  --inspect-max-warning-jobs 0 \
  --inspect-alert-webhook-url https://ops.example/hooks/infinitas \
  --inspect-alert-fallback-file /var/lib/infinitas/alerts/latest-inspect-alert.json
```

To include optional one-way mirror automation in the same rendered bundle, render with:

```bash
python scripts/render-hosted-systemd.py \
  --output-dir /tmp/infinitas-systemd \
  --repo-root /srv/infinitas/repo \
  --python-bin /srv/infinitas/.venv/bin/python \
  --env-file /etc/infinitas/hosted-registry.env \
  --service-prefix infinitas-hosted \
  --backup-output-dir /srv/infinitas/backups \
  --backup-on-calendar daily \
  --backup-label nightly \
  --mirror-remote github-mirror \
  --mirror-branch main \
  --mirror-on-calendar daily \
  --prune-on-calendar daily \
  --prune-keep-last 7 \
  --inspect-max-warning-jobs 0 \
  --inspect-alert-webhook-url https://ops.example/hooks/infinitas \
  --inspect-alert-fallback-file /var/lib/infinitas/alerts/latest-inspect-alert.json
```

The rendered directory contains:

- `infinitas-hosted.env.example`
- `infinitas-hosted-api.service`
- `infinitas-hosted-worker.service`
- `infinitas-hosted-backup.service`
- `infinitas-hosted-backup.timer`
- `infinitas-hosted-prune.service`
- `infinitas-hosted-prune.timer`
- `infinitas-hosted-inspect.service`
- `infinitas-hosted-inspect.timer`

When `--mirror-remote` is provided, it also contains:

- `infinitas-hosted-mirror.service`
- `infinitas-hosted-mirror.timer`

Suggested install flow:

1. Copy `*.service` and `*.timer` into `/etc/systemd/system/`
2. Copy `infinitas-hosted.env.example` to `/etc/infinitas/hosted-registry.env`
3. Replace placeholder secrets and bootstrap tokens in the env file
4. Run `sudo systemctl daemon-reload`
5. Enable and start:
   - `sudo systemctl enable --now infinitas-hosted-api.service`
   - `sudo systemctl enable --now infinitas-hosted-worker.service`
   - `sudo systemctl enable --now infinitas-hosted-backup.timer`
   - `sudo systemctl enable --now infinitas-hosted-prune.timer`
   - `sudo systemctl enable --now infinitas-hosted-inspect.timer`

If mirror automation is enabled in the rendered bundle, also run:

- `sudo systemctl enable --now infinitas-hosted-mirror.timer`

The API service starts `uvicorn`, and the worker, backup, prune, and inspect units all run `python -m infinitas_skill.cli.main server ...` with `PYTHONPATH` pointed at `<repo>/src`. The backup timer runs `server backup`, the prune timer runs `server prune-backups` against the backup root, and the inspect timer runs `server inspect-state` with the configured alert thresholds.
When configured, the mirror timer runs `scripts/mirror-registry.sh` for one-way outward mirroring only.
If `INFINITAS_SERVER_MIRROR_REMOTE` is set in the worker environment, each successful publish also attempts an immediate best-effort one-way mirror push after artifact sync and the primary `origin` push complete.
Published artifacts remain filesystem-backed under `INFINITAS_SERVER_ARTIFACT_PATH`, and the hosted app serves that synchronized artifact root read-only from `/registry/*`.

For a small single-node deployment, a reasonable starting point is:

- `--prune-keep-last 7`
- `--inspect-max-queued-jobs 10`
- `--inspect-max-running-jobs 2`
- `--inspect-max-failed-jobs 0`
- `--inspect-max-warning-jobs 0`
- optional `--inspect-alert-webhook-url https://ops.example/hooks/infinitas`
- optional `--inspect-alert-fallback-file /var/lib/infinitas/alerts/latest-inspect-alert.json`

An inspect service failure means the queue or failure counts crossed a threshold. It does not necessarily mean the process crashed.
If both webhook delivery and the fallback file are configured, the webhook remains the primary alert path and the file becomes the durable local safety net only when delivery is unavailable.
The prune service deletes only older recognized hosted backup snapshots, not arbitrary folders under the backup root.

## Mirroring

GitHub is an optional **one-way mirror** only. The hosted server remains the writable source of truth.

- Use `scripts/mirror-registry.sh --remote <mirror-remote>`
- Or render an optional `infinitas-hosted-mirror.timer` with `--mirror-remote <mirror-remote>`
- Or set `INFINITAS_SERVER_MIRROR_REMOTE=<mirror-remote>` for an immediate best-effort publish-completion hook
- Never fetch or merge GitHub back into the hosted repo
- Mirror after successful publish or on a scheduled operator action
- If the immediate publish hook warns, treat the scheduled mirror timer as the fallback safety net and inspect the publish job log

## Operational notes

- Keep the repo checkout on fast local storage; worker jobs mutate it directly
- Serve artifacts from the synced artifact directory, not from editable skill folders
- Monitor job logs for failed `check-skill`, promotion, or publish steps
- Prefer SQLite only for single-node deployments; move to PostgreSQL when multiple app/worker nodes are needed
