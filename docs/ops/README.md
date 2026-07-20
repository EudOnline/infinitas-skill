---
audience: operators and release maintainers
owner: repository maintainers
source_of_truth: operations landing page
last_reviewed: 2026-07-20
status: maintained
---

# Operations

Use the ops section for procedures that keep the hosted control plane, release flow, and platform evidence healthy.

## Core runbooks

- [Hosted registry server deployment](server-deployment.md)
- [Coolify deployment](coolify-deployment.md) — recommended container installation on a Coolify server
- [Hosted registry backup and restore](server-backup-and-restore.md)
- [Signing bootstrap](signing-bootstrap.md)
- [Signing operations](signing-operations.md)
- [Release checklist](release-checklist.md)

## Drift and freshness management

- [Platform drift playbook](platform-drift-playbook.md)
- [Registry refresh policy](../reference/registry-refresh-policy.md)
- [Federation operations guide](federation-operations.md)

Historical scorecards and transitional release narratives are not operational instructions. Use the maintained runbooks above and the current audit under `docs/audits/`.
