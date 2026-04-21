---
audience: contributors, operators, reviewers
owner: repository maintainers
source_of_truth: docs landing page
last_reviewed: 2026-04-21
status: maintained
---

# Documentation Map

The docs tree is being rebuilt around audience and task instead of historical file order. Start from the section that matches what you are trying to do, not from the oldest file you happen to find.

## Canonical sections

- [Guide](guide/README.md): onboarding, migration rules, and concept-first explanations
- [Reference](reference/README.md): CLI surfaces, schemas, contracts, and policy details
- [Operations](ops/README.md): deployment, backup, signing, release, and drift-management runbooks
- [ADRs](adr/0001-maintainability-reset.md): durable architecture decisions and policy cut lines, including the OpenClaw runtime cutover in [0003](adr/0003-openclaw-runtime-canonical.md)
- [Archive](archive/README.md): historical plans, superseded narratives, and closeout material

## Indexed legacy annexes

- [Legacy platform contracts](platform-contracts/README.md): source snapshots for external runtime/platform assumptions
- [Release, tag, and attestation strategy](release-strategy.md): transitional top-level release policy narrative
- [Registry snapshot mirrors](registry-snapshot-mirrors.md): transitional top-level mirror and snapshot narrative
- [Project closeout](project-closeout.md): historical closeout and steady-state verification context

## Migration rules

- `docs/plans/` is archival planning context during the reset, not the primary user entrypoint.
- Top-level docs that are not yet under `guide/`, `reference/`, `ops/`, `archive/`, or `adr/` should be treated as legacy pages until they are moved or explicitly linked from one of the maintained landing pages.
- New maintained docs should include `audience`, `owner`, `source_of_truth`, `last_reviewed`, and `status` metadata.

## Fast paths

- If you are changing repository structure or contributor workflows, start in [guide/README.md](guide/README.md).
- If you need exact command, schema, or policy behavior, start in [reference/README.md](reference/README.md).
- If you are operating the hosted server or preparing a release, start in [ops/README.md](ops/README.md).
- If you are investigating why the reset exists, start in [adr/0001-maintainability-reset.md](adr/0001-maintainability-reset.md).
- If you need the maintained agent runtime contract, start in [docs/reference/openclaw-runtime-contract.md](reference/openclaw-runtime-contract.md) and [adr/0003-openclaw-runtime-canonical.md](adr/0003-openclaw-runtime-canonical.md).
