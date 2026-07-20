---
audience: contributors, integrators, automation authors
owner: repository maintainers
source_of_truth: maintained discovery and install workflow reference
last_reviewed: 2026-07-20
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

## Configure a hosted registry

For a server deployed at `https://skills.example.com`, add an HTTP source to the client
repository's `config/registry-sources.json` or effective registry-source policy:

```json
{
  "registries": [
    {
      "name": "hosted",
      "kind": "http",
      "base_url": "https://skills.example.com/api/v1/registry",
      "trust": "private",
      "auth": {
        "mode": "token",
        "env": "INFINITAS_REGISTRY_READ_TOKEN"
      }
    }
  ]
}
```

Then validate the effective source configuration:

```bash
export INFINITAS_REGISTRY_READ_TOKEN=<registry-read-token>
uv run infinitas registry sources --repo-root . check
uv run infinitas registry sources --repo-root . status hosted --json
```

The `base_url` must point to `/api/v1/registry`, not the application root. The environment
variable name is a local indirection: the token itself does not belong in the JSON file.

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

To install immediately after reviewing the plan, use `--mode auto`:

```bash
uv run infinitas install by-name \
  <publisher>/<skill> \
  ~/.openclaw/skills \
  --mode auto \
  --json
```

## Installed Integrity Follow-up

Release trust does not end at artifact download. After install, verify the concrete target-local runtime copy:

```bash
uv run infinitas install report ~/.openclaw/skills --json
uv run infinitas install report ~/.openclaw/skills --refresh --json
```

Important boundaries:

- `.infinitas-skill-installed-integrity.json` is the target-local installed-integrity snapshot beside the runtime copy.
- `catalog/audit-export.json` is the repository-side release audit surface, not a substitute for target-local verification.
- local freshness or drift follow-up should start with `infinitas install report`, not with a guess based on catalog state.

## Trust Boundary

Keep these layers separate:

- discovery answers "what might fit"
- inspect answers "what release evidence and runtime facts exist"
- install preview answers "what would change locally"
- installed integrity answers "what is the trust state of this target-local copy right now"

That split keeps recommendation convenience from silently replacing provenance, distribution verification, or installed-runtime trust.

For server-side installation, domain, token, backup, and upgrade steps, see the
[Coolify deployment runbook](../ops/coolify-deployment.md).
