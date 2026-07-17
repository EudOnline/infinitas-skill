---
audience: contributors, operators, reviewers
owner: repository maintainers
source_of_truth: docs landing page
last_reviewed: 2026-07-14
status: maintained
---

# Documentation Map

The docs tree is being rebuilt around audience and task instead of historical file order. Start from the section that matches what you are trying to do, not from the oldest file you happen to find.

## Canonical sections

- [Guide](guide/README.md): onboarding, migration rules, and concept-first explanations
- [Reference](reference/README.md): CLI surfaces, schemas, contracts, and policy details
- [Operations](ops/README.md): deployment, backup, signing, release, and drift-management runbooks
- [ADRs](adr/0001-maintainability-reset.md): durable architecture decisions and policy cut lines, including the OpenClaw runtime cutover in [0003](adr/0003-openclaw-runtime-canonical.md)
- [Latest project audit](audits/2026-07-17-post-merge-project-audit.md): post-merge release, product, security, engineering, and interface assessment
- [Archive](archive/README.md): historical plans, superseded narratives, and closeout material

## Historical annexes

- [Legacy platform contracts](platform-contracts/README.md): source snapshots for external runtime/platform assumptions
- [Archive](archive/README.md): superseded plans and historical snapshots that are not operational instructions

## Migration rules

- `docs/plans/` is archival planning context during the reset, not the primary user entrypoint.
- Top-level documentation is limited to this landing page; maintained content belongs under `guide/`, `reference/`, `ops/`, `specs/`, or `adr/`.
- New maintained docs should include `audience`, `owner`, `source_of_truth`, `last_reviewed`, and `status` metadata.

## Fast paths

- If you are changing repository structure or contributor workflows, start in [guide/README.md](guide/README.md).
- If you need exact command, schema, or policy behavior, start in [reference/README.md](reference/README.md).
- If you are operating the hosted server or preparing a release, start in [ops/README.md](ops/README.md).
- If you are investigating why the reset exists, start in [adr/0001-maintainability-reset.md](adr/0001-maintainability-reset.md).
- If you need the maintained agent runtime contract, start in [docs/reference/openclaw-runtime-contract.md](reference/openclaw-runtime-contract.md) and [adr/0003-openclaw-runtime-canonical.md](adr/0003-openclaw-runtime-canonical.md).
