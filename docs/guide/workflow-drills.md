---
audience: contributors, operators, automation authors
owner: repository maintainers
source_of_truth: maintained workflow drill guide
last_reviewed: 2026-04-21
status: maintained
---

# Workflow Drills

Use this drill when you want a safe discovery-to-install flow without dropping back to the removed `docs/ai` annex.

## Discovery Drill

1. Search for candidates.
2. Ask for the best-ranked fit.
3. Inspect the chosen release.
4. Preview install before mutating the local runtime.

```bash
uv run infinitas discovery search operate --json
uv run infinitas discovery recommend "Need a codex skill for repository operations" --json
uv run infinitas discovery inspect lvxiaoer/operate-infinitas-skill --json
uv run infinitas install by-name operate-infinitas-skill ~/.openclaw/skills --mode confirm --json
```

## Why This Order

- `search` gives you breadth
- `recommend` gives you ranked fit
- `inspect` gives you trust and release detail
- install preview tells you what would actually change on disk

Use the deeper reference docs when you need exact contract wording:

- [Discovery and install workflows](../reference/discovery-install-workflows.md)
- [CLI reference](../reference/cli-reference.md)
- [Release attestation](../reference/release-attestation.md)
