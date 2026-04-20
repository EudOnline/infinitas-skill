---
audience: contributors, integrators, automation authors
owner: repository maintainers
source_of_truth: legacy ai protocol landing page
last_reviewed: 2026-04-21
status: legacy
---

# Legacy AI Protocol Docs

This section collects the older machine-facing protocol pages that still describe important repository behavior, but have not yet been fully migrated into the maintained `guide/`, `reference/`, and `ops/` trees.

Treat this section as an indexed legacy annex:

- use it when you need the historical AI-facing wrapper-command flows or protocol-specific phrasing that is still referenced by tests and automation
- prefer maintained docs under [../reference/README.md](../reference/README.md), [../guide/README.md](../guide/README.md), and [../ops/README.md](../ops/README.md) when a topic exists in both places
- promote durable truth out of this annex instead of expanding it with new long-lived canonical docs

## Discovery, recommendation, and install flows

- [Discovery and install semantics](discovery.md)
- [Search and inspect](search-and-inspect.md)
- [Recommendation workflow](recommend.md)
- [Pull and download](pull.md)
- [Workflow drills](workflow-drills.md)

## Hosted control plane and publishing

- [Hosted registry protocol](hosted-registry.md)
- [Hosted server API](server-api.md)
- [Publish and release](publish.md)
- [CI-native attestation verification](ci-attestation.md)

## Memory

- [Memory operating model](memory.md)
