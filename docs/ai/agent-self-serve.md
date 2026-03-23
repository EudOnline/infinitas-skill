# Agent Self-Serve Guide

## Purpose

This is the single-file self-serve guide for an agent that needs to:

- deploy the hosted `infinitas-skill` control plane from a published container image
- bootstrap the runtime repo without cloning the source repository first
- operate the hosted control plane through supported APIs and CLI commands
- consume the hosted registry as an immutable install source

Use this guide when the task is "deploy and use the project" rather than "modify the repository source code".

## Read Order

For deployment and hosted operations, prefer this order:

- `README.md`
- `docs/ai/agent-self-serve.md`
- `docs/ops/server-deployment.md`
- `docs/ai/server-api.md`
- `docs/ai/hosted-registry.md`
- `docs/ai/publish.md`
- `docs/ai/pull.md`

Do not start by reading random implementation files unless one of the stop conditions below is hit.

## Deployment Model

The current recommended hosted deployment model is:

- one published container image from GHCR
- one `docker compose` stack
- one writable runtime repo mounted at `INFINITAS_SERVER_REPO_PATH`
- one SQLite database file
- one artifact directory served by the built-in app under `/registry/*`

Important distinction:

- the image contains a bundled repository snapshot at `/opt/infinitas/bundle`
- the live writable repo is still `INFINITAS_SERVER_REPO_PATH`, usually `/srv/infinitas/repo`
- `init-repo` or the shared entrypoint seeds that writable repo from the bundled snapshot when the host directory is empty
- future validate/promote/publish jobs mutate the writable runtime repo, not the bundled snapshot

## Hard Rules

- Do not require a manual `git clone` when using the image-only compose flow.
- Do not install runtime skills from mutable source folders such as `skills/active/` or `skills/incubating/`.
- Do not read `/registry/*` as if it were writable control-plane state; it is immutable-artifact-first.
- Do not queue publish or mirror operations unless the runtime repo has push credentials and, when needed, `INFINITAS_SERVER_GIT_ORIGIN_URL`.
- Do not wipe `.deploy/repo` unless the operator explicitly wants to discard the current runtime history.
- Do not assume image bootstrap preserves upstream commit history; it creates a new local git history from the bundled snapshot.

## Prerequisites

Before deployment, ensure:

- Docker and Docker Compose are available
- the target host has persistent directories for repo, data, artifacts, backups, and git home state
- a reverse proxy or direct port exposure plan exists for `8000`
- bootstrap API users and optional registry-read tokens are prepared
- if publish jobs should push outward, `.deploy/home/.ssh` and `.deploy/home/.gitconfig` are prepared and `INFINITAS_SERVER_GIT_ORIGIN_URL` is set

## Minimal Deploy Flow

1. Create the runtime directories:

```bash
mkdir -p .deploy/{repo,data,artifacts,backups,home}
```

2. Copy the compose env template:

```bash
cp .env.compose.example .env.compose
```

3. Edit at least these values in `.env.compose`:

```env
INFINITAS_IMAGE=ghcr.io/eudonline/infinitas-skill:main
INFINITAS_SERVER_SECRET_KEY=replace-with-random-secret
INFINITAS_SERVER_BOOTSTRAP_USERS=[{"username":"maintainer","display_name":"Maintainer","role":"maintainer","token":"replace-maintainer-token"},{"username":"contributor","display_name":"Contributor","role":"contributor","token":"replace-contributor-token"}]
INFINITAS_REGISTRY_READ_TOKENS=[]
INFINITAS_SERVER_GIT_ORIGIN_URL=
```

4. If publish jobs should push to a remote, set:

```env
INFINITAS_SERVER_GIT_ORIGIN_URL=git@github.com:your-org/your-registry.git
INFINITAS_SERVER_GIT_USER_NAME=Infinitas Hosted Registry
INFINITAS_SERVER_GIT_USER_EMAIL=hosted-registry@example.com
```

5. Pull the image and validate compose:

```bash
docker compose --env-file .env.compose pull
docker compose --env-file .env.compose config
```

6. Seed the runtime repo from the image snapshot:

```bash
docker compose --env-file .env.compose run --rm init-repo
```

7. Start the API and worker:

```bash
docker compose --env-file .env.compose up -d app worker
```

## Post-Deploy Verification

Run these checks after startup:

```bash
docker compose --env-file .env.compose ps
docker compose --env-file .env.compose logs --tail=100 app worker
docker compose --env-file .env.compose --profile ops run --rm inspect
python3 .deploy/repo/scripts/server-healthcheck.py \
  --api-url http://127.0.0.1:8000 \
  --repo-path .deploy/repo \
  --artifact-path .deploy/artifacts \
  --database-url sqlite:///$PWD/.deploy/data/server.db \
  --json
```

Healthy deployment expectations:

- `GET /healthz` returns `ok=true`
- `.deploy/repo` is a valid git worktree
- `.deploy/artifacts` contains `ai-index.json` and `catalog/`
- `.deploy/data/server.db` exists
- `inspect` returns queue and submission summaries without fatal errors

## Hosted Surfaces

After deployment, the built-in app exposes:

- control-plane API: `http(s)://<host>/api/v1/...`
- maintainer pages: `http(s)://<host>/submissions`, `/reviews`, `/jobs`
- immutable registry surface: `http(s)://<host>/registry/...`

Important endpoints:

- `GET /healthz`
- `GET /api/v1/me`
- `GET /api/v1/submissions`
- `GET /api/v1/reviews`
- `GET /api/v1/jobs`
- `POST /api/v1/submissions`
- `POST /api/v1/submissions/{id}/request-validation`
- `POST /api/v1/submissions/{id}/request-review`
- `POST /api/v1/reviews/{id}/approve`
- `POST /api/v1/reviews/{id}/reject`
- `POST /api/v1/skills/{skill_name}/publish`
- `GET /registry/ai-index.json`
- `GET /registry/discovery-index.json`
- `GET /registry/distributions.json`
- `GET /registry/skills/<publisher>/<skill>/<version>/manifest.json`

## Operator Usage

For hosted control-plane operations, prefer `scripts/registryctl.py` from the runtime repo:

```bash
python3 .deploy/repo/scripts/registryctl.py --base-url http://127.0.0.1:8000 --token <maintainer-token> submissions list
python3 .deploy/repo/scripts/registryctl.py --base-url http://127.0.0.1:8000 --token <maintainer-token> reviews list
python3 .deploy/repo/scripts/registryctl.py --base-url http://127.0.0.1:8000 --token <maintainer-token> jobs list
```

To create and move a hosted submission through the queue:

```bash
python3 .deploy/repo/scripts/registryctl.py \
  --base-url http://127.0.0.1:8000 \
  --token <contributor-token> \
  submissions create \
  --skill-name my-skill \
  --publisher my-publisher \
  --summary "Hosted submission" \
  --payload-json '{"files":{"SKILL.md":"---\\nname: my-skill\\ndescription: Example.\\n---\\n","_meta.json":{"name":"my-skill","publisher":"my-publisher","qualified_name":"my-publisher/my-skill","version":"0.1.0","status":"incubating","summary":"Example","owner":"maintainer","review_state":"draft","risk_level":"low","distribution":{"installable":true,"channel":"git"}},"CHANGELOG.md":"# Changelog\\n","tests/smoke.md":"# Smoke\\n"}}'

python3 .deploy/repo/scripts/registryctl.py --base-url http://127.0.0.1:8000 --token <contributor-token> submissions request-validation 1
python3 .deploy/repo/scripts/registryctl.py --base-url http://127.0.0.1:8000 --token <contributor-token> submissions request-review 1
python3 .deploy/repo/scripts/registryctl.py --base-url http://127.0.0.1:8000 --token <maintainer-token> reviews approve 1 --note "Looks good"
python3 .deploy/repo/scripts/registryctl.py --base-url http://127.0.0.1:8000 --token <maintainer-token> releases publish my-skill
```

## Consumer Usage

When another agent should consume the hosted registry, point the registry source `base_url` at `/registry`:

```json
{
  "name": "hosted",
  "kind": "http",
  "base_url": "https://skills.example.com/registry",
  "enabled": true,
  "priority": 100,
  "trust": "private",
  "auth": {
    "mode": "token",
    "env": "INFINITAS_REGISTRY_TOKEN"
  }
}
```

Consumer-side rules:

- use `search`, `recommend`, `inspect`, and `pull` against the hosted registry surface
- treat `/registry/*` as immutable install input
- do not copy source out of `.deploy/repo`

Example consumer flow:

```bash
scripts/search-skills.sh operate
scripts/inspect-skill.sh lvxiaoer/operate-infinitas-skill
scripts/pull-skill.sh lvxiaoer/operate-infinitas-skill ~/.openclaw/skills --mode confirm
scripts/pull-skill.sh lvxiaoer/operate-infinitas-skill ~/.openclaw/skills
```

## Day-2 Operations

One-shot ops services exposed through compose:

```bash
docker compose --env-file .env.compose --profile ops run --rm backup
docker compose --env-file .env.compose --profile ops run --rm prune
docker compose --env-file .env.compose --profile ops run --rm inspect
docker compose --env-file .env.compose --profile ops run --rm mirror
```

Useful host-side paths:

- `.deploy/repo` — writable runtime repo
- `.deploy/data/server.db` — SQLite database
- `.deploy/artifacts` — hosted registry artifact root
- `.deploy/backups` — backup and fallback alert output
- `.deploy/home` — `.ssh`, `.gitconfig`, and git client state

## Stop Conditions

Stop and escalate instead of guessing when:

- `init-repo` fails because `.deploy/repo` contains non-git files and reset was not explicitly approved
- publish or mirror is requested but `.deploy/home` lacks credentials or `INFINITAS_SERVER_GIT_ORIGIN_URL`
- `/healthz` is healthy but `.deploy/artifacts` is missing required catalog files
- the registry base URL does not end in `/registry`
- you need exact preservation of an upstream git history rather than image-seeded local history
- the user asks for multi-node, PostgreSQL, or object storage deployment; this guide is single-node and SQLite-first

## Decision Summary

- Deploy from image: use `docker compose`, not a manual source checkout.
- Bootstrap runtime repo: use `init-repo`.
- Operate hosted workflow: use `scripts/registryctl.py` against `/api/v1/*`.
- Install for other agents: use the hosted `/registry/*` surface with `pull-skill.sh`.
- Inspect health and queue state: use `server-healthcheck.py` and `inspect-hosted-state.py`.
