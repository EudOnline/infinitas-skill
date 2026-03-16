# Federation Trust Boundaries and Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Document the operational trust boundaries, failure modes, and recovery procedures for mirrors, federated registries, provenance-derived audit exports, and catalog-derived inventory exports.

**Architecture:** Add one dedicated operations document so boundary and recovery guidance lives in a single operator-facing source of truth, then update existing registry, trust, release, and planning docs to reference that guide and summarize the stable rules. Keep this phase documentation-only; do not change resolver or export behavior.

**Tech Stack:** Markdown docs, existing planning files, and existing documentation validation commands.

---

## Preconditions

- Work in this dedicated worktree: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep 11-08 documentation-only:
  - no schema or script behavior changes
  - no new export formats
  - no new policy sources beyond the existing `registry_sources`, catalog, provenance, and export artifacts

## Scope decisions

- Recommended approach: create one dedicated doc that answers three operator questions clearly:
  - which surface is authoritative for each trust decision
  - what common failure states look like
  - what exact recovery order to follow
- Recommended doc focus:
  - source-of-truth boundaries between `self`, federated registries, mirror registries, hosted registries, provenance, and export artifacts
  - failure-mode examples such as stale mirror data, missing provenance, invalid signature or attestation, registry policy drift, and outdated export artifacts
  - recovery procedures that point back to existing repo commands instead of inventing manual workflows
- Rejected approach: spread all new guidance only across `docs/multi-registry.md` and `docs/trust-model.md`, because operators need one place to read the full recovery story end-to-end.
- Rejected approach: document hypothetical automation or background refresh jobs, because the repo remains Git-native and operator-driven.

### Task 1: Add the dedicated federation operations guide

**Files:**
- Create: `docs/federation-operations.md`
- Reference: `docs/multi-registry.md`
- Reference: `docs/trust-model.md`
- Reference: `docs/release-strategy.md`
- Reference: `docs/ai/pull.md`

**Step 1: Write the guide**

Create `docs/federation-operations.md` covering:

- trust boundaries:
  - writable source-of-truth vs federated upstream vs mirror-only upstream
  - catalog-derived inventory vs provenance-derived audit evidence
  - what `resolver_candidate` means operationally
- common failure modes:
  - stale mirror data
  - mapped namespace no longer allowed by policy
  - missing or invalid provenance / signature
  - exports older than the current committed catalog state
  - policy-pack drift changing effective federation rules
- recovery playbooks:
  - validate policy
  - rebuild catalog
  - re-check provenance / distribution
  - decide whether to disable, demote to mirror, or remove a registry

**Step 2: Commit**

```bash
git add docs/federation-operations.md
git commit -m "docs: add federation operations guide"
```

### Task 2: Link the guide from existing docs

**Files:**
- Modify: `docs/multi-registry.md`
- Modify: `docs/trust-model.md`
- Modify: `docs/release-strategy.md`
- Modify: `docs/ai/pull.md`

**Step 1: Add concise summaries and links**

Update the existing docs so they:

- point readers to `docs/federation-operations.md` for failure-mode and recovery guidance
- summarize the new authoritative boundaries without duplicating the whole guide
- clarify that `audit-export.json` and `inventory-export.json` are stable integration surfaces, while `policy_trace` and live release-state remain operator/debug surfaces

**Step 2: Commit**

```bash
git add docs/multi-registry.md docs/trust-model.md docs/release-strategy.md docs/ai/pull.md
git commit -m "docs: link federation boundary guidance"
```

### Task 3: Close out planning state and verify docs

**Files:**
- Modify: `.planning/PROJECT.md`
- Modify: `.planning/ROADMAP.md`
- Modify: `.planning/STATE.md`
- Modify: `.planning/REQUIREMENTS.md`

**Step 1: Update planning state**

Mark 11-08 complete and v11 Phase 3 complete. Capture that the next work is no longer Phase 3 execution, but future milestone planning or backlog selection.

**Step 2: Run verification**

Run:

```bash
python3 scripts/test-search-docs.py
python3 scripts/test-recommend-docs.py
python3 scripts/check-catalog-exports.py
scripts/check-all.sh
```

Expected: PASS, with the existing hosted-registry e2e dependency skip still allowed when optional Python packages are unavailable.

**Step 3: Commit**

```bash
git add .planning/PROJECT.md .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md
git commit -m "docs: close out federation trust boundaries phase"
```
