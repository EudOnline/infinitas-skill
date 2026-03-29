# infinitas-skill

Private-first skill registry and hosted control plane.

This repository now runs on a single lifecycle:

`skill -> draft -> sealed version -> release -> exposure -> review case -> grant/credential -> discovery/install`

The legacy `submissions / reviews / jobs` product workflow and the old shell-driven publish flow are no longer part of the supported runtime model.

## Current product surface

Hosted UI:

- `/`
- `/skills`
- `/skills/{skill_id}`
- `/drafts/{draft_id}`
- `/releases/{release_id}`
- `/releases/{release_id}/share`
- `/access/tokens`
- `/review-cases`

Hosted control-plane API:

- `/api/auth/*`
- `/api/v1/me`
- `/api/v1/access/*`
- `/api/v1/skills`
- `/api/v1/skills/{skill_id}/drafts`
- `/api/v1/drafts/{draft_id}`
- `/api/v1/drafts/{draft_id}/seal`
- `/api/v1/versions/{version_id}/releases`
- `/api/v1/releases/{release_id}`
- `/api/v1/releases/{release_id}/artifacts`
- `/api/v1/releases/{release_id}/exposures`
- `/api/v1/exposures/{exposure_id}`
- `/api/v1/exposures/{exposure_id}/activate`
- `/api/v1/exposures/{exposure_id}/revoke`
- `/api/v1/exposures/{exposure_id}/review-cases`
- `/api/v1/review-cases/{review_case_id}`
- `/api/v1/review-cases/{review_case_id}/decisions`
- `/api/v1/catalog/{public|me|grant}`
- `/api/v1/search/{public|me|grant}`
- `/api/v1/install/{public|me|grant}/{skill_ref}`

Hosted registry surface:

- `/registry/ai-index.json`
- `/registry/discovery-index.json`
- `/registry/distributions.json`
- `/registry/compatibility.json`
- `/registry/skills/{publisher}/{skill}/{version}/manifest.json`
- `/registry/skills/{publisher}/{skill}/{version}/skill.tar.gz`
- `/registry/provenance/{publisher}--{skill}-{version}.json`
- `/registry/provenance/{publisher}--{skill}-{version}.json.ssig`
- `/registry/catalog/distributions/...` and `/registry/catalog/provenance/...` remain as artifact aliases backed by the same private-first release data

## Local development

```bash
uv sync

uv run python3 scripts/test-private-first-cutover-schema.py
uv run python3 scripts/test-settings-hardening.py
uv run python3 scripts/test-private-registry-access-api.py
uv run python3 scripts/test-private-registry-authoring-api.py
uv run python3 scripts/test-private-registry-release-api.py
uv run python3 scripts/test-private-registry-exposure-review.py
uv run python3 scripts/test-private-registry-discovery.py
uv run python3 scripts/test-private-registry-install-resolution.py
uv run python3 scripts/test-private-registry-access-policy.py
uv run python3 scripts/test-private-registry-audience-views.py
uv run python3 scripts/test-private-registry-grant-install.py
uv run python3 scripts/test-private-first-release-worker.py
uv run python3 scripts/test-private-first-cli.py
uv run python3 scripts/test-private-registry-ui.py
uv run python3 scripts/test-home-auth-session-runtime.py
```

Local runs default to `INFINITAS_SERVER_ENV=development`. If you want fixture-safe defaults in automated checks, set `INFINITAS_SERVER_ENV=test`; both modes can still use the built-in `change-me` secret and bootstrap user fixtures.

`scripts/test-home-auth-session-runtime.py` uses the Codex Playwright wrapper under `$CODEX_HOME`. If that wrapper is unavailable, keep using the API/UI suite locally and treat the browser runtime check as an opt-in regression pass.

## Production configuration

Production startup is now intentionally strict:

- set `INFINITAS_SERVER_ENV=production`
- replace `INFINITAS_SERVER_SECRET_KEY=change-me` with a real secret before boot
- set `INFINITAS_SERVER_BOOTSTRAP_USERS` to a non-empty JSON array of bootstrap operators

If `INFINITAS_SERVER_ENV=production` is set and either the secret remains `change-me` or bootstrap users are omitted, the app now fails fast during startup instead of silently falling back to fixture defaults.

## Policy trace and validation output

Policy enforcement and release decisions now expose structured debug output for operators:

- `scripts/check-promotion-policy.py --json` returns a `policy_trace` payload for promotion decisions, including exception usage when a break-glass path waives a blocker.
- `scripts/check-release-state.py operate-infinitas-skill --json` returns the current release decision payload plus `policy_trace` details for the requested skill.
- `scripts/validate-registry.py --json` returns namespace-level `policy_traces` together with `validation_errors` so callers can distinguish policy blockers from content validation failures.
- The default team-review contract is sourced from `policy/team-policy.json`, which keeps the CLI output and hosted governance checks aligned around the same policy inputs.

## Compatibility terms

The compatibility surface now distinguishes between two meanings:

- `declared support`: the agent runtimes a skill claims to support through author metadata such as `_meta.json.agent_compatible`
- `verified support`: the runtimes confirmed by recent platform-specific checks and recorded compatibility evidence

`catalog/compatibility.json` is the generated summary view that exposes both layers together.

## Discovery and recommendation

For audience-aware skill selection, start with:

- `scripts/search-skills.sh` for broad discovery
- `scripts/recommend-skill.sh` when you want the best-ranked fit for a task
- `docs/ai/workflow-drills.md` for the current search / inspect / confirm workflow drills

## Operator workflow

Use the hosted API or `scripts/registryctl.py` instead of repository-mutation shell scripts.

Typical sequence:

```bash
# create a skill namespace record
python3 scripts/registryctl.py skills create \
  --slug demo-skill \
  --display-name "Demo Skill" \
  --summary "Private-first demo skill"

# create and patch a draft
python3 scripts/registryctl.py drafts create 1 \
  --content-ref 'git+https://example.com/demo-skill.git#<commit>' \
  --metadata-json '{"entrypoint":"SKILL.md","manifest":{"name":"demo-skill","version":"0.1.0"}}'

# seal the draft into an immutable version
python3 scripts/registryctl.py drafts seal 1 --version 0.1.0

# create a release and let the worker materialize artifacts
python3 scripts/registryctl.py releases create 1

# expose the release to an audience
python3 scripts/registryctl.py exposures create 1 \
  --audience-type public \
  --listing-mode listed \
  --install-mode enabled \
  --requested-review-mode none
```

Public exposures become installable only after their review case is approved. Private and grant exposures can activate immediately unless policy requires review.

## Design notes

- The database is Alembic-managed only. Unversioned compatibility databases are intentionally not auto-upgraded.
- `INFINITAS_REGISTRY_READ_TOKENS` is no longer a primary auth path for the registry surface. Access is derived from private-first credentials and bridged hosted user tokens.
- The registry surface is generated from release/exposure/access state. It is no longer a compatibility view layered on top of submission state.

Additional migration notes live in [docs/private-first-cutover.md](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-private-first-cutover/docs/private-first-cutover.md).
