---
audience: contributors, operators, integrators
owner: repository maintainers
source_of_truth: private-first cutover guide
last_reviewed: 2026-04-03
status: maintained
---

# Private-First Cutover

## What changed

The hosted registry now uses the private-first domain model end to end:

- `principals`, `teams`, `service_principals`
- `skills`, `skill_drafts`, `skill_versions`
- `releases`, `artifacts`
- `exposures`, `review_cases`, `review_decisions`
- `access_grants`, `credentials`
- `audit_events`, `jobs`

An optional advisory memory layer now sits beside that model:

- recommend and inspect may read cognitive memory when explicitly enabled
- lifecycle hooks may write best-effort experience memory after core transactions commit
- `audit_events` remain the durable trace for those writeback attempts
- releases, reviews, exposures, grants, and credentials still remain local source-of-truth state

The legacy product workflow is removed:

- no `submissions` product surface
- no `reviews` product surface
- no `jobs` surface tied to submission state
- no `publish-skill.sh`, `promote-skill.sh`, `request-review.sh`, or `approve-skill.sh` operator path

## Multi-object vocabulary

The maintained hosted vocabulary now distinguishes three first-class publishable object kinds:

- `skill` for installable skill bundles
- `agent_preset` for shared OpenClaw runtime configuration bundles
- `agent_code` for lightweight runnable agent code bundles

Later hosted lifecycle work must use these exact object-kind names. The install and release path also uses two exact content-shape terms:

- `memory_mode` for the selected preset memory variant
- `content_mode` for whether hosted content comes from an uploaded bundle or an immutable external reference

## Supported runtime model

1. author into a draft
2. seal into an immutable version
3. create a release
4. materialize immutable artifacts
5. expose the release to `private`, `grant`, or `public`
6. approve the review case when public exposure is required
7. discover and install through audience-scoped registry or API surfaces

## Registry surface

`/registry/*` remains available, but only as a projection of private-first release state.

- `ai-index.json` is install-oriented
- `discovery-index.json` is listing-oriented
- artifact paths are authorized by current audience scope
- catalog alias paths are served by the same projection layer

Hosted storage is no longer limited to metadata snapshots. The maintained model allows the platform to own complete content bundles for supported object kinds and release them as platform-managed artifacts.

## Verification used for the cutover

- schema cutover
- access context auth
- authoring API
- release API
- exposure and review workflow
- discovery and install resolution
- registry audience scoping and artifact aliases
- release worker
- private-first CLI surface
- hosted UI rendering
- advisory memory retrieval and auditable lifecycle writeback without policy bypass
