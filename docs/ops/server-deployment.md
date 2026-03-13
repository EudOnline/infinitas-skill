# Hosted Registry Server Deployment

This runbook describes the smallest hosted deployment for the server-owned `infinitas-skill` registry.

## Core services

- **Reverse proxy**: terminate TLS and expose the hosted API plus static artifact paths
- **App**: run `uvicorn server.app:app`
- **Worker**: run `server.worker` on the same host or a trusted sibling process
- **Repo path**: a writable checkout of the private source-of-truth repository
- **Artifact path**: a filesystem directory served over HTTPS for `ai-index.json`, `catalog/`, provenance, and bundles
- **Secrets**: bootstrap user tokens, SSH signing key wiring, and any database credentials

## Required environment

- `INFINITAS_SERVER_DATABASE_URL`
- `INFINITAS_SERVER_SECRET_KEY`
- `INFINITAS_SERVER_BOOTSTRAP_USERS`
- `INFINITAS_SERVER_REPO_PATH`
- `INFINITAS_SERVER_ARTIFACT_PATH`
- optional `INFINITAS_SERVER_REPO_LOCK_PATH`

## Startup sequence

1. Provision the private repo checkout on the server
2. Bootstrap trusted SSH release signing in that checkout
3. Point `INFINITAS_SERVER_REPO_PATH` at the writable checkout
4. Point `INFINITAS_SERVER_ARTIFACT_PATH` at a durable filesystem path
5. Start the API app with `uv run uvicorn server.app:app --host 0.0.0.0 --port 8000`
6. Start a worker loop process that drains queued validate / promote / publish jobs
7. Configure the reverse proxy so hosted registry clients reach the API and immutable artifacts over HTTPS

## Mirroring

GitHub is an optional **one-way mirror** only. The hosted server remains the writable source of truth.

- Use `scripts/mirror-registry.sh --remote <mirror-remote>`
- Never fetch or merge GitHub back into the hosted repo
- Mirror after successful publish or on a scheduled operator action

## Operational notes

- Keep the repo checkout on fast local storage; worker jobs mutate it directly
- Serve artifacts from the synced artifact directory, not from editable skill folders
- Monitor job logs for failed `check-skill`, promotion, or publish steps
- Prefer SQLite only for single-node deployments; move to PostgreSQL when multiple app/worker nodes are needed
