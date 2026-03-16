# Multi-Registry Sources

Version 9 turns `config/registry-sources.json` from descriptive metadata into enforced source policy.

Version 11-01 keeps that file path compatible while allowing shared `registry_sources` defaults to come from ordered packs declared in `policy/policy-packs.json`.

## Why this exists

A registry source now has to answer three operational questions explicitly:

1. **How much do we trust it?**
2. **What exact ref family or immutable object may it resolve from?**
3. **May sync move with a branch, stay pinned, or refuse to mutate local state?**

That lets install, sync, and catalog outputs report an exact source identity instead of only a best-effort path.

## Config shape

```json
{
  "$schema": "../schemas/registry-sources.schema.json",
  "default_registry": "self",
  "registries": [
    {
      "name": "self",
      "kind": "git",
      "url": "https://github.com/EudOnline/infinitas-skill.git",
      "local_path": ".",
      "branch": "main",
      "priority": 100,
      "enabled": true,
      "trust": "private",
      "allowed_hosts": ["github.com"],
      "allowed_refs": ["refs/heads/main"],
      "pin": {
        "mode": "branch",
        "value": "main"
      },
      "update_policy": {
        "mode": "local-only"
      }
    }
  ]
}
```

When policy packs are active, the effective registry-source policy is resolved in this order:

1. ordered `registry_sources` domains from `policy/packs/*.json`
2. final repository-local overrides from `config/registry-sources.json`

That keeps existing operators and scripts compatible while still allowing reusable pack defaults.

## Field meanings

### `trust`

Allowed tiers:

- `private` — operator-controlled registry; may use moving refs when policy allows it.
- `trusted` — external but still allowed to track configured branches.
- `public` — must use immutable sync (`pinned`) or a local-only checkout.
- `untrusted` — may only be declared as `local-only`; tooling refuses mutable sync.

### `allowed_hosts`

Remote git sources must declare which hosts are acceptable. Validation and sync refuse a configured or cloned remote whose host is outside this allowlist.

### `allowed_refs`

Branch- and tag-based registries must declare the exact refs that are allowed to satisfy sync. Sync refuses refs outside this list.

### `pin`

`pin` tells tooling what the source is anchored to:

- `branch` — a moving branch name such as `main`
- `tag` — an immutable tag name
- `commit` — a full 40-character git SHA

### `update_policy.mode`

- `local-only` — never fetch or reset; use the local checkout as-is and only surface its current identity.
- `track` — fetch the configured branch and materialize the current branch head into a detached cache checkout.
- `pinned` — fetch and materialize an exact tag or commit into a detached cache checkout.

### `federation`

Selected upstream registries may now declare an additive `federation` block:

```json
{
  "federation": {
    "mode": "federated",
    "allowed_publishers": ["partner"],
    "publisher_map": {
      "partner": "partner-labs"
    },
    "require_immutable_artifacts": true
  }
}
```

`mode` may be:

- `federated` — the upstream registry can satisfy normal resolver queries, and publisher-qualified requests may be rewritten into a local namespace through `publisher_map`.
- `mirror` — the registry remains visible in operator and catalog views, but it is not a default resolver candidate.

Validation enforces the current trust boundary:

- the working repository root (`self` / `local_path = "."`) cannot declare a federation block
- `untrusted` registries cannot use `federation.mode = "federated"`
- federated Git registries cannot use `update_policy.mode = "track"`
- `publisher_map` keys must be valid publisher slugs and must stay inside `allowed_publishers` when that list is present

`require_immutable_artifacts` is an explicit trust contract. It tells downstream tooling and exports that this upstream should only be consumed through immutable release artifacts, rather than being treated as an authoritative mutable working tree.

## Safe sync semantics

`self` now uses `update_policy.mode = local-only` together with `local_path = "."`.

That means:

- `scripts/sync-registry-source.sh self` no longer fetches or hard-resets the working repository.
- `scripts/sync-all-registries.sh` is safe to run even when `self` is enabled.
- mutable sync is limited to cache clones under `.cache/registries/<name>`.

For tracked or pinned remote registries, sync now:

1. validates the configured policy,
2. checks the remote host against `allowed_hosts`,
3. refuses refs outside `allowed_refs`,
4. resolves an exact commit, and
5. checks out that commit in detached state.

## Hosted HTTP registries

The registry source model now also supports a hosted distribution source:

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

Use `kind: "http"` when operators want clients to install from hosted immutable artifacts instead of cloning or caching a Git checkout.

Hosted registries differ from Git registries in three important ways:

1. they resolve through HTTPS endpoints instead of a local repository root
2. they do not expose Git commit / tag identity at install time
3. they are intended to serve generated catalog views and immutable release artifacts

For `private`, `trusted`, and `public` hosted registries, `base_url` must use HTTPS.

Optional `catalog_paths` overrides may be provided only when the registry does not serve the default paths:

- `ai_index`
- `distributions`
- `compatibility`

Auth currently supports:

- `none`
- `token` via an environment variable named in `auth.env`

## Resolution and install identity

`resolve-skill-source.py --json` now includes registry policy and exact git identity fields such as:

- `publisher`
- `qualified_name`
- `identity_mode`
- `upstream_publisher`
- `upstream_qualified_name`
- `federation_mode`
- `publisher_mapping_applied`
- `registry_name`
- `registry_ref`
- `registry_commit`
- `registry_tag`
- `registry_update_mode`
- `registry_pin_mode`
- `registry_pin_value`
- `expected_tag`

Use `publisher/skill` when you need to disambiguate two publishers that share the same bare skill slug. Legacy unqualified names still resolve for backward compatibility.

For federated registries, the resolved `publisher` / `qualified_name` may be the mapped local namespace, while `upstream_publisher` / `upstream_qualified_name` preserve the original upstream identity for auditability.

Install and sync manifests persist the same identity so `scripts/list-installed.sh` can show where a skill came from with its publisher namespace plus exact registry commit/tag.

For hosted registries, manifests should instead persist:

- `registry_name`
- `registry_url` / `registry_base_url`
- resolved hosted version
- any compatible publisher-qualified skill identity

## Discovery across registries

The registry now also exports `catalog/discovery-index.json` as a private-first discovery layer.

Discovery follows these rules:

1. local private registry entries are considered first
2. synced external registries only contribute candidates when the private registry has no suitable match
3. external matches are discoverable, but `install-by-name` keeps them confirmation-gated by default
4. registries with `federation.mode = "mirror"` remain visible to operators, but they do not participate as normal resolver candidates

That means multiple agents can share a single local search/install surface without silently treating every configured registry as equally trusted.

## Dependency resolution rules

Dependency planning now follows a deterministic registry-aware order:

1. An explicit dependency `registry` hint is authoritative.
2. Otherwise, the planner prefers the same registry that supplied the requesting skill.
3. Remaining registries are considered by configured `priority` and then by name.
4. An already-installed dependency is kept when it still satisfies every constraint and does not violate an explicit registry hint.
5. `archived` candidates are only considered for exact version requests, while `incubating` candidates require `allow_incubating: true`.
6. If the final plan would violate an installed dependency lock or leave an unresolved conflict, install/sync fails before mutating the target directory.

`scripts/resolve-install-plan.py` exposes the same planner that `install-skill.sh`, `sync-skill.sh`, `check-install-target.py`, and `check-registry-integrity.py` now use.

## Catalog output

`catalog/registries.json` now exports each configured registry together with:

- `resolved_root`
- `resolved_ref`
- `resolved_commit`
- `resolved_tag`
- `resolved_origin_url`
- `resolved_federation_mode`
- `resolved_allowed_publishers`
- `resolved_publisher_map`
- `resolved_require_immutable_artifacts`
- `resolver_candidate`

When the local repository itself is the catalog source in `local-only` mode, catalog generation intentionally leaves `resolved_commit` / `resolved_tag` (and per-skill `source_registry_commit` / `source_registry_tag`) empty. That keeps committed catalog snapshots stable instead of making every new commit invalidate `catalog/registries.json` on the next validation pass. Operators can still inspect the live checkout identity with `scripts/list-registry-sources.py`.

## Integration exports

11-07 adds two integration-facing static export artifacts under `catalog/`:

- `catalog/inventory-export.json`
- `catalog/audit-export.json`

`inventory-export.json` is catalog-derived. It is the right surface when a portal or inventory system needs:

- the configured registry list
- resolver visibility such as `resolver_candidate`
- federation identity such as `federation_mode`, `allowed_publishers`, and `publisher_map`
- skill inventory with source-registry and release/installability summary

`audit-export.json` is provenance-derived. It is the right surface when an external reviewer needs:

- immutable release evidence
- provenance and signature paths
- source snapshot tag / ref / commit
- delegated review context and release authority context when present
- applied exception usage without relying on debug-only `policy_trace`

These export files are generated by `scripts/build-catalog.sh` and validated by `python3 scripts/check-catalog-exports.py`.
