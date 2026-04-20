---
audience: contributors, operators, integrators
owner: repository maintainers
source_of_truth: guide landing page
last_reviewed: 2026-04-20
status: maintained
---

# Retired Multi-Object Branch Notes

This note captures the useful ideas from the retired branch `codex/multi-object-agent-distribution` before deleting it. The branch was an earlier implementation line for multi-object distribution and overlapped heavily with work that has already landed on `main`.

## Branch scope

The retired branch contained six committed themes plus local work-in-progress:

- multi-object distribution vocabulary and schema definitions
- shared hosted object storage primitives
- draft content artifact storage for hosted objects
- inline hosted bundle materialization
- agent preset publishing APIs
- memory-aware preset install variants
- uncommitted `agent_code` routing and release work

## What was good about it

### 1. It treated `agent_preset` and `agent_code` as first-class registry objects

The strongest idea in the branch was to make object-native publishing flows explicit instead of forcing everything through the legacy skill-only lifecycle. In practice, that meant:

- dedicated read and write APIs for `agent_preset` and `agent_code`
- object-native release creation instead of only skill-version releases
- object-aware release snapshots and ownership checks

This is still a good direction for `main`, because it makes object semantics visible at the API boundary instead of hiding them behind skill compatibility shims.

### 2. It pushed memory configuration through discovery, registry, and install together

The branch did more than store memory metadata. It carried `supported_memory_modes`, `default_memory_mode`, and the selected install mode through:

- release projections
- registry listing payloads
- install planning
- end-to-end integration tests

That end-to-end framing is valuable. It keeps memory mode from becoming a write-only field that exists in storage but never influences what clients can discover or install.

### 3. It used stronger end-to-end contract tests

The branch included good scenario coverage around:

- hosted draft content storage
- bundle materialization for hosted releases
- preset publishing APIs
- memory-aware install variants
- external `agent_code` import and release paths

The main lesson is not that the exact tests should be restored verbatim, but that these behaviors are cross-module contracts and should keep integration-level protection.

### 4. It separated stable ideas from transport details

A useful modeling choice in the branch was to distinguish:

- stored draft content artifacts
- uploaded bundle materialization
- external immutable refs such as `git+...#commit`

That separation made it easier to reason about what was being stored, what was being materialized, and what kind of provenance a release could claim.

## Why it should not be migrated directly

Deleting the branch is the right choice because its implementation diverged from the current `main` in several important ways:

- it used older API shapes for `agent_preset` and `agent_code`
- it overlapped with newer multi-object work already merged into `main`
- direct cherry-picks now produce broad conflicts across release, discovery, and authoring modules
- the old worktree also contained uncommitted `agent_code` changes, so the branch no longer represented a clean, reviewable unit

The right move is to keep the ideas, not the branch history.

## Recommended follow-up on `main`

Future enhancements on `main` should borrow the branch's intent in smaller, explicit patches:

1. finish object-native read and release APIs for `agent_preset` and `agent_code`
2. keep memory-mode metadata flowing through discovery, registry, and install as a single contract
3. preserve integration tests for hosted content storage, bundle materialization, and install variants
4. continue separating uploaded bundles, stored artifacts, and external immutable refs in release logic

## Disposition

This branch was documented and then retired so future work can continue directly on `main` without carrying an increasingly stale parallel history.
