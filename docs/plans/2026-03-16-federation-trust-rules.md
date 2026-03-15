# Federation Trust Rules Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Define additive mirror/federation trust rules for selected upstream registries so namespace mapping, immutability requirements, and source-of-truth boundaries become machine-validated before later export work.

**Architecture:** Reuse `config/registry-sources.json` and `scripts/registry_source_lib.py` as the Phase 3 control-plane instead of inventing a second policy file. Add an optional per-registry `federation` block, enforce the new trust constraints in validation, and surface stable federation metadata through registry identity, resolver JSON, and `catalog/registries.json` without changing the existing one-way hosted mirror helper semantics.

**Tech Stack:** Python 3.11 CLI scripts, JSON schema validation, generated catalog JSON, script-style regression tests in `scripts/test-*.py`, and Markdown docs.

---

## Preconditions

- Work in this dedicated worktree: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`
- Use `@superpowers:test-driven-development` before each behavior change.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep 11-06 additive:
  - no standalone audit/inventory export yet; that belongs to 11-07
  - no reverse-sync from mirrors into the writable source-of-truth repo
  - no change to the current hosted one-way mirror executor in `scripts/mirror-registry.sh`

## Scope decisions

- Recommended approach: extend `registry_sources` with an optional `federation` block so federation policy lives beside existing trust, pin, and update rules.
- Recommended `federation` shape for this phase:
  - `mode`: `mirror` or `federated`
  - `allowed_publishers`: upstream publisher slugs this registry may surface
  - `publisher_map`: upstream publisher slug to local publisher slug mapping
  - `require_immutable_artifacts`: whether the registry may only satisfy resolution through immutable distribution artifacts
- Rejected approach: treat `INFINITAS_SERVER_MIRROR_REMOTE` as the source of federation truth, because that env var configures an operational hook, not consumer-visible source policy.
- Rejected approach: allow federation rules to silently weaken mutable git tracking; `federated` registries should stay pinned, remote-only, or otherwise immutable enough for later verification work.
- Rejected approach: bundle independent audit export files into 11-06, because 11-05 intentionally kept audit metadata on the release/provenance path and 11-07 is where separate export products belong.
- 11-06 should define three rule layers:
  - registry boundary:
    - trust tier
    - update mode
    - immutable artifact requirement
  - namespace boundary:
    - which upstream publishers are allowed
    - how upstream publishers map to local publisher namespaces
  - explainability boundary:
    - registry identity and resolver JSON show the effective federation mode and any publisher mapping applied

### Task 1: Add failing federation validation coverage

**Files:**
- Create: `scripts/test-registry-federation-rules.py`
- Reference: `schemas/registry-sources.schema.json`
- Reference: `scripts/registry_source_lib.py`

**Step 1: Write the failing test**

Create `scripts/test-registry-federation-rules.py` with focused config fixtures that assert all of the following:

- a trusted HTTP registry with `federation.mode = "federated"` plus `allowed_publishers` and `publisher_map` is valid
- a registry rooted at the current repository (the existing `self` pattern) cannot declare a federation block
- an `untrusted` registry cannot declare `federation.mode = "federated"`
- a git registry using `update_policy.mode = "track"` cannot declare `federation.mode = "federated"`
- `publisher_map` keys must stay within `allowed_publishers` when `allowed_publishers` is present

Use direct assertions like:

```python
errors = validate_registry_config(ROOT, cfg)
if not any("cannot federate the working repository root" in item for item in errors):
    fail(f"expected self-registry federation rejection, got {errors!r}")
```

**Step 2: Run the focused test to verify it fails**

Run:

```bash
python3 scripts/test-registry-federation-rules.py
```

Expected: FAIL because `registry-sources` schema and validation do not yet understand the `federation` block.

**Step 3: Commit**

```bash
git add scripts/test-registry-federation-rules.py
git commit -m "test: add federation trust rule coverage"
```

### Task 2: Implement the federation config contract

**Files:**
- Modify: `schemas/registry-sources.schema.json`
- Modify: `scripts/registry_source_lib.py`
- Reference: `config/registry-sources.json`

**Step 1: Implement the minimal schema and validation**

Update `schemas/registry-sources.schema.json` and `scripts/registry_source_lib.py` so registry entries may include an additive `federation` object with:

- `mode`
- `allowed_publishers`
- `publisher_map`
- `require_immutable_artifacts`

Add helper normalization and export fields in `registry_identity()` such as:

- `registry_federation_mode`
- `registry_allowed_publishers`
- `registry_publisher_map`
- `registry_require_immutable_artifacts`

Validation should enforce:

- no federation block for the working-repository `self` source
- `untrusted` registries cannot be `federated`
- `federated` git registries cannot use `update_policy.mode = "track"`
- `publisher_map` keys are well-formed publisher slugs
- `publisher_map` keys stay within `allowed_publishers` when that list exists

Keep the new fields additive so existing registry configs and callers remain valid.

**Step 2: Re-run the focused validation test**

Run:

```bash
python3 scripts/test-registry-federation-rules.py
python3 scripts/test-hosted-registry-source.py
python3 scripts/check-registry-sources.py
```

Expected: PASS.

**Step 3: Commit**

```bash
git add schemas/registry-sources.schema.json scripts/registry_source_lib.py scripts/test-registry-federation-rules.py
git commit -m "feat: add federation trust rules to registry sources"
```

### Task 3: Add failing federation resolution and registry-view coverage

**Files:**
- Create: `scripts/test-federated-registry-resolution.py`
- Modify: `scripts/test-policy-pack-loading.py`
- Reference: `scripts/resolve-skill-source.py`
- Reference: `scripts/build-catalog.sh`
- Reference: `scripts/list-registry-sources.py`

**Step 1: Write the failing tests**

Create a regression script that prepares:

- a local upstream registry fixture outside the repo root
- one registry entry with `federation.mode = "federated"`
- one registry entry with `federation.mode = "mirror"`
- a publisher mapping such as `partner -> partner-labs`

Assert that:

- `python3 scripts/resolve-skill-source.py partner-labs/demo --registry upstream-fed --json` can only succeed after the mapped publisher contract exists
- the resolved JSON preserves the upstream publisher while also surfacing the mapped local publisher / qualified name
- a `mirror` registry does not become a normal resolver candidate
- `scripts/build-catalog.sh` writes additive federation fields into `catalog/registries.json`
- `scripts/test-policy-pack-loading.py` proves `registry_sources` pack defaults can deep-merge the new `federation` block

Use assertion shapes like:

```python
resolved = payload.get('resolved') or {}
if resolved.get('publisher') != 'partner-labs':
    fail(f"expected mapped publisher 'partner-labs', got {resolved!r}")
if resolved.get('upstream_publisher') != 'partner':
    fail(f"expected upstream publisher 'partner', got {resolved!r}")
```

**Step 2: Run the focused tests to verify they fail**

Run:

```bash
python3 scripts/test-federated-registry-resolution.py
python3 scripts/test-policy-pack-loading.py
```

Expected: FAIL because resolver and catalog outputs do not yet understand federation mode or publisher mapping.

**Step 3: Commit**

```bash
git add scripts/test-federated-registry-resolution.py scripts/test-policy-pack-loading.py
git commit -m "test: add federated registry resolution coverage"
```

### Task 4: Surface federation metadata through resolver and registry views

**Files:**
- Modify: `scripts/resolve-skill-source.py`
- Modify: `scripts/build-catalog.sh`
- Modify: `scripts/list-registry-sources.py`
- Modify: `scripts/registry_source_lib.py`

**Step 1: Implement the minimal federation surface**

Update resolver and registry-view code so:

- `resolve-skill-source.py` can match mapped publisher-qualified requests for `federated` registries
- resolved JSON includes both preserved upstream identity and mapped local identity fields such as:
  - `upstream_publisher`
  - `upstream_qualified_name`
  - `federation_mode`
  - `publisher_mapping_applied`
- `mirror` registries remain visible in registry listings but do not act as normal install resolution candidates
- `build-catalog.sh` exports additive federation fields in `catalog/registries.json`
- `list-registry-sources.py` prints the effective federation mode and mapping summary for human operators

Keep this phase additive:

- do not change the current one-way push semantics of `scripts/mirror-registry.sh`
- do not add separate audit or inventory export files yet
- do not rewrite discovery ranking rules unless a focused regression proves it is necessary

**Step 2: Re-run the focused tests**

Run:

```bash
python3 scripts/test-federated-registry-resolution.py
python3 scripts/test-policy-pack-loading.py
python3 scripts/test-registry-federation-rules.py
```

Expected: PASS.

**Step 3: Commit**

```bash
git add scripts/resolve-skill-source.py scripts/build-catalog.sh scripts/list-registry-sources.py scripts/registry_source_lib.py scripts/test-federated-registry-resolution.py scripts/test-policy-pack-loading.py scripts/test-registry-federation-rules.py
git commit -m "feat: expose federation trust metadata"
```

### Task 5: Document 11-06 and run final verification

**Files:**
- Modify: `docs/multi-registry.md`
- Modify: `docs/trust-model.md`
- Modify: `docs/ai/pull.md`
- Modify: `.planning/PROJECT.md`
- Modify: `.planning/ROADMAP.md`
- Modify: `.planning/STATE.md`
- Modify: `.planning/REQUIREMENTS.md`

**Step 1: Update docs**

Document:

- the new `registry_sources.federation` contract and its allowed values
- that mirrors remain one-way and non-authoritative
- how publisher mapping preserves upstream identity while exposing a local namespace
- that 11-06 defines trust rules only; standalone audit/export formats still belong to 11-07

**Step 2: Run focused verification**

Run:

```bash
python3 scripts/test-registry-federation-rules.py
python3 scripts/test-federated-registry-resolution.py
python3 scripts/test-policy-pack-loading.py
```

Expected: PASS.

**Step 3: Run full verification**

Run:

```bash
scripts/check-all.sh
```

Expected: PASS, with hosted e2e allowed to skip when its optional Python dependencies are unavailable.

**Step 4: Commit**

```bash
git add docs/multi-registry.md docs/trust-model.md docs/ai/pull.md .planning/PROJECT.md .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md
git commit -m "docs: close out federation trust rules phase"
```
