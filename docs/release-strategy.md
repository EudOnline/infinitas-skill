# Release and Tag Strategy

This repository tracks skill evolution inside git, but runtime installs happen from local skill directories. Releases should therefore be lightweight, explicit, and easy to trace.

## Versioning

Use semantic versioning for every skill:

- `major`: incompatible workflow or contract change
- `minor`: meaningful capability expansion, new references, new scripts, or changed behavior
- `patch`: wording cleanup, metadata fixes, small corrections

## Changelog policy

Every skill under `skills/` should keep a `CHANGELOG.md`.

Recommended format:

```md
# Changelog

## 0.2.0 - 2026-03-08
- Added manifest-aware install flow.
- Added lineage diff helper.
```

## Tag naming

If you create git tags for notable stable releases, prefer a per-skill naming convention:

- `skill/<name>/v<version>`

Examples:

- `skill/repo-audit/v0.3.0`
- `skill/feishu-doc/v1.0.0`

This avoids collisions across many skills living in one repository.

## Promotion guidance

Typical flow:

1. Work in `skills/incubating/<name>`
2. Update `_meta.json.version`
3. Add or update `CHANGELOG.md`
4. Run `scripts/check-all.sh`
5. Set `review_state` appropriately
6. Promote to `skills/active/`
7. Optionally tag a stable milestone

## Helpful commands

```bash
# bump patch version and seed changelog entry
scripts/bump-skill-version.sh repo-audit patch --note "Refined repo scoring rubric"

# inspect lineage against a declared ancestor
scripts/lineage-diff.sh repo-audit-plus
```

## Tag helper

Use the helper to print the expected tag or create it locally:

```bash
# print the recommended tag
scripts/release-skill-tag.sh repo-audit

# create the tag locally
scripts/release-skill-tag.sh repo-audit --create
```

This keeps per-skill release tags consistent with the documented naming scheme.

## Release helper

Use the higher-level helper to validate the registry, print release notes from the current changelog section, and optionally create/push a tag or GitHub release:

```bash
# print the release summary
scripts/release-skill.sh repo-audit

# create the local tag
scripts/release-skill.sh repo-audit --create-tag

# create and push the tag
scripts/release-skill.sh repo-audit --push-tag
```

If you also pass `--github-release`, the helper will call `gh release create` with the extracted changelog notes.
