---
audience: contributors, integrators, reviewers
owner: repository maintainers
source_of_truth: generated runtime compatibility view
last_reviewed: 2026-07-14
status: maintained
---

# Runtime Compatibility Matrix

The generated view is `catalog/compatibility.json` and the hosted API exposes it at `GET /api/v1/registry/compatibility.json`.

## Contents

- declared support from `_meta.json.agent_compatible`;
- verified support from current platform evidence;
- freshness state, reason, verification time, and freshness deadline;
- skill stage, version, and path.

## Interpretation

- `fresh`: current evidence satisfies the configured age and platform-contract checks.
- `stale`: evidence exists but is older than policy or predates a newer platform contract.
- `unknown`: the platform has no accepted evidence for this skill version.

OpenClaw is the canonical runtime and its freshness can block preflight or stable release modes. Other platforms remain visible for consumers that target them.

The matrix does not override release attestations, distribution hashes, namespace policy, access control, or installed-integrity verification.

## Source declaration

```json
{
  "agent_compatible": ["openclaw", "claude-code", "codex"]
}
```

Rebuild current registry views with:

```bash
uv run infinitas registry catalog build
```

Inspect release readiness with:

```bash
uv run infinitas release check-state <skill> --mode local-preflight --json
```

See [compatibility-contract.md](compatibility-contract.md) and [openclaw-runtime-contract.md](openclaw-runtime-contract.md).
