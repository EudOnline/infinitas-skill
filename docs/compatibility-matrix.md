# Compatibility Matrix

The registry now exports a machine-readable compatibility view at:

- `catalog/compatibility.json`

## What it contains

- per-agent skill listings derived from `_meta.json.agent_compatible`
- stage counts for `incubating`, `active`, and `archived`
- version + path data for quick lookup

## Why this exists

As the registry grows, consumers often need to answer questions like:

- Which skills claim to work with OpenClaw?
- Which ones are suitable for Codex or Claude Code?
- How many stable vs experimental skills do we currently have?

`catalog/compatibility.json` gives you a single generated file for that.

## Current compatibility source of truth

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

`catalog/compatibility.json` reflects runtime compatibility claims derived from `_meta.json.agent_compatible`.

It does **not** guarantee:

- `_meta.json` file-format compatibility across schema versions
- install-manifest compatibility across tool versions
- migration support for persisted state

Those concerns are defined separately in `docs/compatibility-contract.md`.
