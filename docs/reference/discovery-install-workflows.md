---
audience: contributors, integrators, automation authors
owner: repository maintainers
source_of_truth: maintained discovery and install workflow reference
last_reviewed: 2026-04-21
status: maintained
---

# Discovery and Install Workflows

Use the maintained discovery surface when you know the task or skill shape, but you still want release trust and install verification to stay explicit.

## Discovery CLI

Search a generated discovery surface:

```bash
uv run infinitas discovery search operate --json
uv run infinitas discovery search --publisher lvxiaoer --agent openclaw --json
```

Recommend the best fit for a task:

```bash
uv run infinitas discovery recommend "Need a codex skill for repository operations" --json
uv run infinitas discovery recommend "Need an OpenClaw publishing helper" --target-agent openclaw --json
```

Inspect one released skill before install:

```bash
uv run infinitas discovery inspect lvxiaoer/operate-infinitas-skill --json
```

These commands read the maintained generated surfaces under `catalog/` rather than scraping `skills/active/` or `skills/incubating/`.

## What Each Step Is For

- `search` gives a broad candidate list from the generated discovery index.
- `recommend` ranks candidates and explains why the winner outranks nearby alternatives.
- `inspect` is the trust-focused read path for one released object, including runtime, provenance, and distribution detail.

Use `inspect` before mutation whenever provenance, compatibility, or trust state matters.

## Install Preview

Discovery resolves what to consider. Install preview resolves what would actually change in a target runtime:

```bash
uv run infinitas install by-name operate-infinitas-skill ~/.openclaw/skills --mode confirm --json
```

Treat the preview as the last check before materializing local changes.

## Installed Integrity Follow-up

Release trust does not end at artifact download. After install, verify the concrete target-local runtime copy:

```bash
python3 scripts/report-installed-integrity.py ~/.openclaw/skills --json
python3 scripts/report-installed-integrity.py ~/.openclaw/skills --refresh --json
```

Important boundaries:

- `.infinitas-skill-installed-integrity.json` is the target-local installed-integrity snapshot beside the runtime copy.
- `catalog/audit-export.json` is the repository-side release audit surface, not a substitute for target-local verification.
- local freshness or drift follow-up should start with `report-installed-integrity.py`, not with a guess based on catalog state.

## Trust Boundary

Keep these layers separate:

- discovery answers "what might fit"
- inspect answers "what release evidence and runtime facts exist"
- install preview answers "what would change locally"
- installed integrity answers "what is the trust state of this target-local copy right now"

That split keeps recommendation convenience from silently replacing provenance, distribution verification, or installed-runtime trust.
