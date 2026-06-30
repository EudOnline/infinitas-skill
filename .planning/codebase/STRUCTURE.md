# Structure

> Snapshot of the repository layout. Last refreshed 2026-06-30 alongside the
> memory-subsystem and `share_links`-table removal. Treat the live tree as
> authoritative when this drifts; regenerate facts with `git ls-files`.

The project is the **infinitas hosted registry** — a FastAPI control plane
(`server/`) plus a Python CLI/library package (`src/infinitas_skill/`) that
governs a private skill registry. `scripts/` holds auxiliary tooling and a
shadow test suite; `catalog/`, `config/`, `policy/`, `schemas/`, `profiles/`
hold generated views and machine-readable contracts.

## Top-level layout

```text
├─ src/infinitas_skill/   CLI + library package (compatibility, discovery, install, openclaw, policy, registry, release, server ops, skills)
├─ server/                FastAPI hosted control plane (app, models, auth, modules/* feature packages, ui/, api/)
├─ alembic/               database migrations (env.py + versions/)
├─ tests/                 pytest suite (unit/, integration/, e2e/, security/, performance/, fixtures/, helpers/)
├─ scripts/               operational tooling + a shadow test-* suite run via scripts/check-all.sh
├─ catalog/               generated registry indexes and provenance (catalog.json, active.json, compatibility.json, ...)
├─ config/                operational config (registry-sources, signing, compatibility/install-integrity policy)
├─ policy/                declarative governance (promotion, exception, namespace, team, policy-packs/)
├─ schemas/               JSON schema contracts for metadata, manifests, indexes, exports
├─ profiles/              platform runtime profiles (claude.json, codex.json, openclaw.json)
├─ skills/                lifecycle-managed skill source trees (incubating/active/archived)
├─ templates/             scaffold sources for new skills
├─ docs/                  human guidance (guide/, reference/, specs/, ops/, plans/, archive/, platform-contracts/)
├─ docker/                container build support
├─ .github/workflows/     CI (delegates to scripts/check-all.sh)
├─ .planning/             planning metadata; not part of the registry runtime
├─ openapi.json           generated API schema (regenerate via scripts/generate-openapi.py)
├─ pyproject.toml         project + tooling config (ruff, mypy, pytest, coverage)
└─ Makefile               developer entrypoints (bootstrap, ci-fast, check-all, typecheck, ...)
```

## Primary code surfaces

### `src/infinitas_skill/` — CLI + library

The installable package (`infinitas` entrypoint → `cli.main:main`). Subpackages
map to domains:

- `cli/` — argparse builders + `reference.py` (regenerates `docs/reference/cli-reference.md`)
- `compatibility/` — platform-contract checks and evidence
- `discovery/` — search, recommend, inspect, AI index validation
- `install/` — install planning, distribution, registry sources
- `openclaw/` — OpenClaw runtime model, plugins, contracts
- `policy/` — promotion, exceptions, reviews, trace
- `registry/` — hosted-registry client CLI + refresh state
- `release/` — release readiness, attestation, signing, transparency log
- `server/` — server-side ops helpers (backup, db_utils, health, ops, systemd)
- `skills/` — canonical skill model, render, schema version
- `testing/` — test helpers (env)

### `server/` — FastAPI hosted control plane

The web application. Core modules at `server/*.py` (`app`, `models`, `auth`,
`db`, `middleware`, `settings`, `worker`, `repo_ops`, `rate_limit`, ...).
Feature code is organized under `server/modules/<feature>/` with a consistent
`router.py` + `service.py` + `schemas.py` + `models.py` shape:

- `modules/access` `audit` `authoring` `discovery` `exposure` `profile`
- `modules/registry` `release` `review` `shared` `shares`

UI layer: `server/ui/` (routes, queries, formatting, i18n, library_* views),
`server/templates/` (Jinja2 + partials), `server/static/{css,js}`,
`server/locales/`. API routers live under `server/api/`.

> Note: the `share_links` **table** was dropped (migration `df25325e7fd0`);
> share-link functionality survives, reimplemented on `AccessGrant`
> (`grant_type == "link"`). The `memory` subsystem was removed entirely.

## Database

- `alembic/env.py` wires `server.models.Base`; single head `6fe6c7710a23`.
- ORM models live in `server/models.py`. Migrations under `alembic/versions/`.

## Tests

`tests/` mirrors the code surfaces: `unit/` (mirrors `src/` + `server/modules/`),
`integration/` (API/CLI/workflow), `e2e/` (browser flows), `security/`,
`performance/`, plus `fixtures/` and `helpers/`. pytest config:
`testpaths=["tests"]`, coverage over `src` and `server`. Shared script-side
fixtures live in `scripts/test_support/` (imported by some pytest tests, e.g.
`tests/fixtures/repo_state.py` — do not remove).

## Auxiliary: `scripts/`

Operational tooling and validators, plus a **shadow test suite** of
`test-*.py` runners invoked by `scripts/check-all.sh` (these are NOT collected
by pytest — see structural debt below). Families: `check-*` (compat/integrity
gates), `verify-*`, `generate-*` (openapi, provenance, manifests, CI
attestation), `sign-*`, `export-*`/`import-*`, plus bash glue (`.sh`).

## Contract / data directories

- `config/` — `registry-sources.json` (registry source list/trust), `signing.json`
  + `allowed_signers` (SSH signing trust), `compatibility-policy.json`,
  `install-integrity-policy.json`.
- `policy/` — `promotion-policy.json`, `exception-policy.json`,
  `namespace-policy.json`, `team-policy.json`, `policy-packs.json`, `packs/`.
- `schemas/` — JSON schema anchors (skill-meta, install/distribution manifests,
  discovery/ai indexes, audit/inventory exports, policy schemas).
- `profiles/` — per-platform runtime profiles consumed by compatibility checks.
- `catalog/` — **generated** views (`catalog.json`, `active.json`,
  `compatibility.json`, `registries.json`, `ai-index.json`, `discovery-index.json`,
  ...) + `provenance/`. Treat as output, not editable source.
- `skills/` — `incubating/` `active/` `archived/`; per-skill shape is
  `SKILL.md` + `_meta.json` + `CHANGELOG.md` (+ optional `scripts/`,
  `references/`, `assets/`, `tests/smoke.md`).
- `templates/` — starter skeletons consumed by skill scaffolding.

## Key structural relationships

- `config/` declares inputs → `src/infinitas_skill/` + `server/` resolve,
  validate, and expose them → `catalog/` stores generated views.
- `schemas/` + `policy/` are the machine-readable contracts; `docs/reference/`
  is the human explanation of the same; `scripts/check-*` and `server/modules/*`
  enforce them.
- CI (`.github/workflows/validate.yml`) delegates to `scripts/check-all.sh`, so
  new invariants that should fail PRs must be wired into `check-all.sh`.

## Naming and layout conventions that matter structurally

- Skill names are lowercase-hyphenated slugs; folder name must match
  `_meta.json.name` and `SKILL.md` `name:` for non-archived skills.
- `tests/smoke.md` is the default minimum validation artifact per skill.
- Active overwrite history is stored as timestamped dirs under `skills/archived/`.
- Release tags use `skill/<name>/v<version>`.
- Installed copies are tracked by `.infinitas-skill-install-manifest.json`.
- Script file names use hyphens (`check-registry-integrity.py`); the
  `scripts/test_support/` package uses underscores (it is an importable package).

## Structural debt (known)

- **Shadow test suite:** ~97 `scripts/test-*.py` runners are invoked only by
  `scripts/check-all.sh`, outside pytest — no fixtures, no coverage, lint-exempt.
  Migrating the live ones into `tests/` is the main remaining maintainability lever.
- The older `docs/plans/*.md` still cite scripts and modules removed during the
  refactor; they are retained as historical record (see `docs/plans/README.md`).
