---
audience: contributors, operators, integrators
owner: repository maintainers
source_of_truth: repository entry page
last_reviewed: 2026-07-23
status: maintained
---

# infinitas-skill

Private skill registry and hosted control plane for human administrators, Agents, and automation.

The repository is intentionally pre-release and uses one current architecture: one FastAPI application, one initial database migration, one `infinitas` CLI, pytest-only automated tests, and no project-internal upgrade adapters.

The supported v0.1 deployment profile is single-node SQLite with filesystem-backed
artifacts. PostgreSQL driver support is present for development evaluation, but
multi-node production operation and PostgreSQL backup/restore are not release claims.

OpenClaw is now the canonical agent runtime. The registry/release/install backend remains the durable control plane; OpenClaw-specific runtime metadata is a consumer contract, not a replacement for registry ownership or release verification.

## Product split

- Human administrators use the server-rendered Web UI to browse the Library, inspect immutable Releases and version digests, create Share Links, and review Activity. The Web UI deliberately does not create or edit skills.
- Agents and automation use JSON APIs or the `infinitas` CLI to publish, discover, inspect, install, and operate skills.

These consumers share domain services and read models. UI routes never replace Agent APIs, and JSON APIs are not dead code merely because browser templates do not call them.

## Repository layout

```text
server/                         Hosted FastAPI control plane
server/modules/<domain>/        Domain models, services, repositories, routers, schemas
server/ui/routes/               Human-facing HTML routes
src/infinitas_skill/            CLI and repository-domain logic
skills/active/                  Skill definitions consumed by Agents
schemas/                        Current JSON schemas
alembic/versions/0001_initial.py
tests/                          All automated tests
scripts/                        Four build/verification entrypoints only
```

See [AGENTS.md](AGENTS.md) for the ownership map, transaction rule, lifecycle rule, and review constraints.

## Maintained surfaces

- package-owned: `src/infinitas_skill/` owns the `infinitas` CLI and repository-domain logic.
- runtime-owned: `server/modules/` owns JSON APIs and domain services; `server/ui/` owns server-rendered HTML.
- automation-owned: the four files in `scripts/` own full validation, OpenAPI generation, CSS purging, and asset hashing.

## Web admin

Primary routes:

- `/manage` — Library, Access, Shares, and Activity
- `/library/{object_id}` — Object detail
- `/library/{object_id}/releases/{release_id}` — Release detail
- `/profile`
- `/settings`
- `/login`

Browser authentication uses a session cookie and CSRF token. Agent requests use Bearer credentials.

## CLI

`uv run infinitas ...` is the only user-facing command surface. Representative commands:

```bash
uv run infinitas discovery search registry --json
uv run infinitas discovery inspect lvxiaoer/operate-infinitas-skill --json
uv run infinitas install by-name lvxiaoer/operate-infinitas-skill .agents/skills
uv run infinitas registry publish ./my-skill --version 1.0.0 --visibility private
uv run infinitas registry bootstrap hosted https://skills.infinitas.fun/api/v1/registry \
  --repo-root . --token-env INFINITAS_REGISTRY_READ_TOKEN --set-default --json
uv run infinitas registry versions compare <skill_id> 1.0.0 1.1.0
uv run infinitas install from-share '<resolve-url>' ~/.openclaw/skills
uv run infinitas registry --help
uv run infinitas policy check-promotion skills/active/operate-infinitas-skill --json
uv run infinitas release check-state operate-infinitas-skill --mode local-preflight --json
uv run infinitas server healthcheck --api-url http://127.0.0.1:8000 --json
```

The generated command inventory is [docs/reference/cli-reference.md](docs/reference/cli-reference.md).

## Policy and attestation output

`policy/policy-packs.json` selects shared policy packs and `policy/team-policy.json` defines team ownership. Repository policy commands return `policy_trace` with `effective_sources`, `blocking_rules`, and next actions; catalog validation reports structured `validation_errors`.

```bash
uv run infinitas policy check-promotion <skill> --json
uv run infinitas release check-state operate-infinitas-skill --json
uv run infinitas registry catalog build
uv run infinitas release verify-ci-attestation <provenance.ci.json> --json
```

CI-native attestation is defined by `.github/workflows/release-attestation.yml`; `release_trust_mode` selects `ssh`, `ci`, or `both`. See [docs/reference/release-attestation.md](docs/reference/release-attestation.md).

## Local setup

```bash
make bootstrap
```

Start the application with the project’s configured ASGI command, then open `/manage`. Runtime configuration is documented in [docs/reference/configuration.md](docs/reference/configuration.md).

For a hosted installation on Coolify, use the maintained
[`docker-compose.coolify.yml`](docker-compose.coolify.yml) and follow the
[Coolify deployment runbook](docs/ops/coolify-deployment.md). Do not deploy the generic local
Compose file unchanged: it intentionally uses host bind mounts and explicit host UID/GID values.

## Verification

Fast checks:

```bash
make ci-fast
make test-fast
make lint-maintained
.venv/bin/ruff check .
.venv/bin/ruff format .
```

Complete closeout:

```bash
make test-full
```

`make test-full` delegates to `./scripts/check-all.sh`.

The full gate runs repository-wide Ruff and format checks, strict production Mypy,
coverage-enforced non-E2E pytest, E2E pytest, hermetic Alembic drift detection,
OpenAPI drift detection, dependency audits, and the frontend build. See
[docs/reference/testing.md](docs/reference/testing.md) for focused commands and
environment notes.

## Architecture invariants

- ORM models have one domain owner; `server/model_registry.py` exists only to populate metadata.
- `server.db.get_db()` and `session_scope()` own commit/rollback behavior; services do not commit independently.
- Database initialization and bootstrap run only inside FastAPI lifespan.
- `alembic/versions/0001_initial.py` is the complete schema for an empty database.
- UI routes return HTML; domain routers return JSON with explicit response models.
- Platform/runtime support evaluation remains a current product capability. Superseded repository formats, entrypoints, and route aliases are rejected rather than adapted.
- Top-level `scripts/` contains only build and verification infrastructure; product behavior belongs under `src/infinitas_skill/` or `server/`.

## Documentation

- [Documentation map](docs/README.md)
- [API reference](docs/reference/api-reference.md)
- [Metadata schema](docs/reference/metadata-schema.md)
- [Install manifest format](docs/reference/install-manifest-format.md)
- [Testing](docs/reference/testing.md)
- [Operator runbooks](docs/ops/README.md)
- [Coolify deployment](docs/ops/coolify-deployment.md)
- [ADR 0001: maintainability reset](docs/adr/0001-maintainability-reset.md)
- [ADR 0002: maintained surface cutover](docs/adr/0002-maintained-surface-cutover.md)
- [ADR 0003: OpenClaw runtime canonical](docs/adr/0003-openclaw-runtime-canonical.md)
