---
audience: contributors, integrators, operators
owner: repository maintainers
source_of_truth: registry refresh policy reference
last_reviewed: 2026-03-30
status: maintained
---

# Registry Refresh Policy

Version 13 Phase 1 adds an explicit freshness contract for cached remote Git registries.

Use it when an external registry is allowed to live in `.cache/registries/<name>`, but operators still want a deterministic answer to "how stale is too stale?"

## Configure a refresh policy

Add `refresh_policy` to a remote cached Git registry in `config/registry-sources.json` or a policy pack:

```json
{
  "name": "upstream",
  "kind": "git",
  "url": "https://github.com/example/upstream-skills.git",
  "priority": 90,
  "enabled": true,
  "trust": "trusted",
  "allowed_hosts": ["github.com"],
  "allowed_refs": ["refs/tags/v1.2.3"],
  "pin": {
    "mode": "tag",
    "value": "v1.2.3"
  },
  "update_policy": {
    "mode": "pinned"
  },
  "refresh_policy": {
    "interval_hours": 24,
    "max_cache_age_hours": 72,
    "stale_policy": "warn"
  }
}
```

Rules:

- `interval_hours` must be a positive integer
- `max_cache_age_hours` must be a positive integer and must be greater than or equal to `interval_hours`
- `stale_policy` must be one of `ignore`, `warn`, or `fail`
- local-only registries such as `self` may omit `refresh_policy`

## Where refresh state lives

Successful remote syncs write one JSON state file per registry:

```text
.cache/registries/_state/<registry>.json
```

The recorded payload includes:

- `registry`
- `kind`
- `refreshed_at`
- `source_commit`
- `source_ref`
- `source_tag`
- `cache_path`

That state is intentionally local cache metadata. It is not part of the committed repository contract.

When operators later create an immutable registry snapshot, that refresh-state payload is copied into the snapshot metadata so the snapshot still carries the source freshness context that existed at capture time.

## Inspect freshness

To inspect one registry directly:

```bash
python3 scripts/registry-refresh-status.py upstream --json
```

The JSON output reports:

- whether refresh state exists
- the last successful refresh time
- the current cache age
- configured `interval_hours`
- configured `max_cache_age_hours`
- derived `freshness_state`

Typical states:

- `fresh` — cache age is still within the configured interval
- `refresh-due` — cache age exceeded `interval_hours`, but is still within `max_cache_age_hours`
- `stale-warning` — cache age exceeded `max_cache_age_hours` and resolution stays allowed with a warning
- `stale-fail` — cache age exceeded `max_cache_age_hours` and resolution is blocked
- `not-configured` — no freshness policy applies to this registry

## Resolver behavior

`python3 scripts/resolve-skill-source.py ... --json` now surfaces registry freshness metadata in resolved output:

- `registry_freshness_state`
- `registry_freshness_warning`
- `registry_refresh_age_hours`

Behavior by policy:

- `ignore`: resolution continues without extra enforcement
- `warn`: resolution continues, but the resolved payload includes an actionable `registry_freshness_warning`
- `fail`: stale remote caches are rejected with an error that tells the operator to run `scripts/sync-registry-source.sh <registry>`

Explicit snapshot resolution is the deliberate exception. If an operator resolves with `--registry <name> --snapshot <id|latest>`, the resolver reads from `.cache/registry-snapshots/<name>/...` instead of the mutable cache and does not apply live-cache freshness blocking to that request.

## Recover from stale caches

Refresh the registry cache:

```bash
scripts/sync-registry-source.sh upstream
```

A successful sync rewrites the refresh-state file with the latest timestamp and source commit. Once that happens, stale-cache `warn` or `fail` decisions clear automatically on the next resolution attempt.

If you need a stable offline recovery point before refreshing again, create an immutable snapshot first:

```bash
python3 scripts/create-registry-snapshot.py upstream --json
```
