# Compatibility Matrix

The registry now exports a machine-readable compatibility view at:

- `catalog/compatibility.json`

## What it contains

- declared support exported from author metadata such as `_meta.json.agent_compatible`
- verified support derived from compatibility evidence and platform-specific checks
- stage counts for `incubating`, `active`, and `archived`
- version + path data for quick lookup

## Why this exists

As the registry grows, consumers often need to answer questions like:

- Which skills claim to work with OpenClaw?
- Which ones are suitable for Codex or Claude Code?
- How many stable vs experimental skills do we currently have?

`catalog/compatibility.json` gives you a single generated file for that.

## Current compatibility source of truth

During the migration window, compatibility has two sources of truth with different meanings:

- **declared support** is still read from author metadata such as `_meta.json.agent_compatible`
- **verified support** is produced by platform-specific compatibility checks and evidence files
- `python3 scripts/record-verified-support.py <skill> --platform ... --build-catalog` is the canonical way to refresh verified support evidence after a real release/export check

Compatibility is still declared manually in each skill's `_meta.json`:

```json
{
  "agent_compatible": ["openclaw", "claude-code", "codex"]
}
```

The matrix is only a generated view; edit `_meta.json`, then run:

```bash
scripts/build-catalog.sh
```

## What this does not guarantee

`catalog/compatibility.json` currently reflects declared support from `_meta.json.agent_compatible`, and will increasingly add verified support from compatibility evidence as the new pipeline lands.

It does **not** guarantee:

- `_meta.json` file-format compatibility across schema versions
- install-manifest compatibility across tool versions
- migration support for persisted state

Those concerns are defined separately in `docs/compatibility-contract.md`.
