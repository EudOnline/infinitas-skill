# Multi-Registry Sources

Version 6 adds an explicit source registry configuration file:

- `config/registry-sources.json`

## Why this exists

Even if the current setup only uses one private repo, the registry now has a formal place to describe multiple sources, trust levels, priorities, and default resolution behavior.

## File shape

```json
{
  "default_registry": "self",
  "registries": [
    {
      "name": "self",
      "kind": "git",
      "url": "https://github.com/EudOnline/infinitas-skill.git",
      "branch": "main",
      "priority": 100,
      "enabled": true,
      "trust": "private"
    }
  ]
}
```

## Current behavior

Today the registry still resolves local paths only, but the config is already used for:

- validation via `scripts/check-registry-sources.py`
- exported catalog view via `catalog/registries.json`
- provenance generation

That means a future multi-source resolver can build on a stable config format rather than inventing one later.

## Resolution behavior

`resolve-skill-source.py` now merges candidates from all enabled local registry sources and chooses between them by:

1. explicit registry filter when provided
2. requested version / snapshot exactness
3. registry priority
4. stage preference (`active` before `archived` for default installs)

That gives the repository a real multi-source resolution path rather than only a config placeholder.

## Syncing git registries

Use:

```bash
scripts/sync-registry-source.sh <name>
scripts/sync-all-registries.sh
```

Git registries without a fixed `local_path` are cloned or fetched into `.cache/registries/<name>`.
