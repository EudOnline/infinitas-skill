# Multi-Registry Sources

Version 9 turns `config/registry-sources.json` from descriptive metadata into enforced source policy.

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

## Resolution and install identity

`resolve-skill-source.py --json` now includes registry policy and exact git identity fields such as:

- `registry_name`
- `registry_ref`
- `registry_commit`
- `registry_tag`
- `registry_update_mode`
- `registry_pin_mode`
- `registry_pin_value`
- `expected_tag`

Install and sync manifests persist the same identity so `scripts/list-installed.sh` can show where a skill came from with its registry plus exact commit/tag.

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

When the local repository itself is the catalog source, `catalog/catalog.json` and `catalog/active.json` also attach registry identity fields to each skill entry.
