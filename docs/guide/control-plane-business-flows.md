---
audience: contributors, operators, integrators
owner: repository maintainers
source_of_truth: business-flow audit of the maintained control plane
last_reviewed: 2026-05-13
status: maintained
---

# Control-Plane Business Flows

This guide summarizes the maintained business flows for `infinitas-skill` after the private-first and OpenClaw-first cutovers.

The old lifecycle model is not maintained as a product story. Old routes exist only as redirects or migration shims, and new work must use the canonical `object/release/exposure/distribution` flow.

Use this page when you need one conceptual model that explains:

- how agent-facing publish, discovery, and install flows work
- how the browser admin surface maps onto the same backend lifecycle
- where the real source-of-truth boundaries live
- which parts of the current implementation still show dual-track or migration-era behavior

For lower-level route and command details, continue into:

- [Private-first cutover](private-first-cutover.md)
- [Frontend control-plane alignment](frontend-control-plane-alignment.md)
- [OpenClaw runtime contract](../reference/openclaw-runtime-contract.md)
- [API reference](../reference/api-reference.md)
- [CLI reference](../reference/cli-reference.md)

## One-sentence model

`infinitas-skill` is a private-first distribution control plane.

It does not treat "skill exists" or even "release exists" as enough for downstream use. A downstream agent or human only reaches a usable install surface after the object has passed through release materialization, audience-scoped exposure, and access distribution.

## Unified Overview

```mermaid
flowchart TD
  A["Author / Agent / Automation"] --> B["Create or update object
  skill / agent_preset / agent_code"]
  B --> C["Generate version
  legacy authoring internals may still run behind the facade"]
  C --> D["Create release
  state=preparing"]
  D --> E["Worker materializes immutable artifacts
  bundle / manifest / provenance / signature"]
  E --> F["Release ready"]

  F --> G["Exposure decision"]
  G --> G1["private / authenticated
  auto active"]
  G --> G2["grant
  review mode depends on request"]
  G --> G3["public
  forced blocking review"]

  G1 --> H["Distribution surfaces open"]
  G2 --> H
  G3 --> I["Review case approved"]
  I --> H

  H --> J["Token / share / registry projection"]
  H --> K["Catalog / search / install APIs"]
  K --> L["Install planning"]
  L --> M["OpenClaw workspace skill dirs"]
```

## Source-Of-Truth Boundary

The repository uses one backend truth set for both agent and frontend flows:

- `RegistryObject` is the durable identity for `skill`, `agent_preset`, and `agent_code`
- version and release state remain backend-owned
- immutable release artifacts remain backend-owned
- exposure, review, token, share, and audit state remain backend-owned
- OpenClaw defines runtime semantics, but it does not replace release or access truth

That separation is important because the project intentionally avoids letting the runtime itself become the authority for release governance.

## Runtime And Admin Surfaces

```mermaid
flowchart LR
  subgraph Runtime["Agent Runtime Surface"]
    R1["infinitas CLI"]
    R2["OpenClaw contract checks"]
    R3["Discovery / install flows"]
  end

  subgraph Control["Backend Source Of Truth"]
    C1["Objects"]
    C2["Versions / releases"]
    C3["Exposure / review"]
    C4["Tokens / shares / credentials"]
    C5["Audit / jobs"]
  end

  subgraph Admin["Browser Admin Surface"]
    F1["/library"]
    F2["/access"]
    F3["/shares"]
    F4["/activity"]
  end

  R1 --> C1
  R1 --> C2
  R2 --> R3
  R3 --> C2
  R3 --> C3
  R3 --> C4

  F1 --> C1
  F1 --> C2
  F1 --> C3
  F2 --> C4
  F3 --> C4
  F4 --> C5
```

## Agent Version

### Primary goal

The agent-facing product surface is optimized for publication, discovery, and installation into the OpenClaw runtime model.

The maintained entrypoint is the package CLI:

- `infinitas discovery ...`
- `infinitas install ...`
- `infinitas openclaw ...`
- `infinitas release ...`
- `infinitas registry ...`

### Flow summary

```mermaid
flowchart LR
  A["Agent / automation"] --> B["CLI or publish API"]
  B --> C["Publish object facade"]
  C --> D["Internal versioning lifecycle"]
  D --> E["Release created"]
  E --> F["Materialization worker"]
  F --> G["Ready release"]
  G --> H["Exposure and review policy"]
  H --> I["Catalog / search / install API"]
  I --> J["Install plan"]
  J --> K["OpenClaw workspace directories"]
```

### Detailed narrative

1. The agent starts from the maintained CLI or the publish facade.
2. Object creation is object-centric, not draft-centric.
3. Release creation may still translate into legacy authoring internals for `skill` and related object kinds.
4. A new release begins in `preparing`.
5. A worker materializes immutable artifacts before the release becomes `ready`.
6. A ready release still cannot be used broadly until exposure policy opens the appropriate audience surface.
7. Discovery and install then resolve from audience-scoped projections and immutable release artifacts.
8. The final local result is an OpenClaw-targeted install plan against workspace or shared skill directories.

### Why this matters

This means the agent-facing happy path deliberately hides lifecycle complexity without deleting it. The facade simplifies how callers think, but the backend still preserves stronger release invariants than a simple "upload and use" model.

## Frontend Version

### Primary goal

The browser product is a human-admin distribution console. The old lifecycle model is not maintained for browser work, and any legacy browser routes are temporary redirects or migration shims into the maintained `/library`, `/access`, `/shares`, and `/activity` surfaces.

The maintained browser routes are:

- `/library`
- `/library/{object_id}`
- `/library/{object_id}/releases/{release_id}`
- `/access`
- `/shares`
- `/activity`
- `/settings`

### Flow summary

```mermaid
flowchart LR
  U["Admin user"] --> R["UI routes and SSR context"]
  R --> S["Library scope aggregation"]
  S --> T["Rendered pages"]
  T --> J["Lightweight JS interactions"]
  J --> P["Library / token / share APIs"]
  P --> B["Backend truth"]
```

### Detailed narrative

1. The frontend enters through server-rendered routes instead of a standalone SPA shell.
2. Each page loads aggregated backend context through `load_library_scope` and related UI projection helpers.
3. The primary browser mental model is Object, Release, Visibility, Token, Share Link, and Activity.
4. The frontend uses light JavaScript for search, tab switching, copy actions, revoke actions, and release-detail mutation helpers.
5. The browser does not own lifecycle truth. It consumes server-built summaries and calls maintained APIs for mutations.

### What the frontend is really doing

The frontend is mostly a projection layer over backend state:

- `/library` projects object and release inventory
- object detail projects release history plus access distribution summaries
- release detail projects artifact readiness and visibility state
- access projects token inventory and token usage summaries
- shares projects share inventory and share state
- activity projects audit-like activity views for humans

## State Machine That Actually Controls Consumption

The single most important business rule is:

`release exists` does not mean `release is consumable`

The effective gating chain is:

1. the release must reach `ready`
2. an exposure must exist for the intended audience
3. the exposure must be active
4. any required review must be resolved
5. the downstream caller must arrive through a matching access path

### Exposure policy

The maintained exposure rules are:

- `private`: no review, auto-activate
- `authenticated`: no review, auto-activate
- `grant`: supports `none`, `advisory`, or `blocking`
- `public`: always forced to `blocking`

### Business consequence

The public path is intentionally conservative. Even if a release is technically ready, public distribution cannot proceed until blocking review is approved.

## Registry, Discovery, And Install As Projections

The registry and discovery surfaces are not separate sources of truth. They are projections of the backend release and exposure model.

That includes:

- `/registry/ai-index.json`
- `/registry/discovery-index.json`
- `/api/v1/catalog/*`
- `/api/v1/search/*`
- `/api/v1/install/*`
- `/api/search`

Operationally, this means search and install resolve from materialized and audience-filtered release projections, not from mutable authoring state.

## Current Dual-Track Areas

The repository is already consolidated around the maintained model, but a few areas still show dual-track behavior.

### 1. Publish facade vs internal lifecycle

The agent-facing publish API is object-centric and hides legacy authoring mechanics.

Internally, the backend still uses legacy draft and sealed-version transitions for some object kinds. This is intentional, but it means maintainers should not mistake those internals for the maintained product model.

### 2. Frontend distribution console vs legacy lifecycle JavaScript

The routed browser product now redirects legacy authoring pages into the Library surfaces, but the global application bootstrap still initializes lifecycle-era JavaScript modules. That is a maintainability signal that old frontend plumbing has not been fully retired.

### 3. Share-link implementation split

There are currently two share-oriented models in the repository:

- Library release share creation built on `AccessGrant + Credential`
- standalone share-link routes backed by `ShareLink`

The Library UI summaries currently aggregate the grant-based model. That makes share behavior one of the most important areas to keep aligned before expanding the browser product further.

### 4. Activity projection vs raw audit API

The browser activity page is assembled from UI aggregation helpers rather than directly mirroring the raw audit API output. This is useful for readability, but it also means "frontend activity" and "backend audit events" are related rather than identical views.

## Recommended Reading Order

When onboarding a contributor, the fastest path is:

1. this business-flow guide
2. [Private-first cutover](private-first-cutover.md)
3. [Frontend control-plane alignment](frontend-control-plane-alignment.md)
4. [OpenClaw runtime contract](../reference/openclaw-runtime-contract.md)
5. [API reference](../reference/api-reference.md)
6. [CLI reference](../reference/cli-reference.md)

## Practical Takeaways

- Treat the backend as the only durable business authority.
- Treat OpenClaw as the runtime semantics authority, not the release-governance authority.
- Treat the browser product as a distribution console, not an authoring-first console.
- Treat `object/release/exposure/distribution` as the only maintained product story for new work.
- Treat discovery, search, registry, and install as audience-filtered projections of release truth.
- Treat exposure state as the real gate between "artifact exists" and "artifact can be consumed".
