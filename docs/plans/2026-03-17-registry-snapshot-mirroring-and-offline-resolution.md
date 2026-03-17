# Registry Snapshot Mirroring And Offline Resolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let operators materialize immutable snapshots of remote registries and explicitly use those snapshots for offline or recovery resolution, install, and sync workflows.

**Architecture:** Treat registry snapshots as additive artifacts derived from an existing remote registry cache, not as a new authoritative registry kind. Store snapshots under `.cache/registry-snapshots/<registry>/<snapshot_id>/` with a machine-readable metadata file that preserves source identity, trust policy, and copied refresh metadata. Expose snapshot visibility through catalog exports and explicit CLI selection so offline workflows can opt in without changing existing default authority or federation behavior.

**Tech Stack:** Existing Bash and Python 3.11 CLI tooling, `scripts/registry_source_lib.py`, `scripts/resolve-skill-source.py`, `scripts/materialize-skill-source.py`, `scripts/install-skill.sh`, JSON metadata files under `.cache/`, and Markdown operator docs.

---

### Task 1: Define registry snapshot metadata and catalog visibility

**Files:**
- Create: `scripts/test-registry-snapshot-mirror.py`
- Create: `scripts/registry_snapshot_lib.py`
- Modify: `scripts/build-catalog.sh`
- Modify: `scripts/list-registry-sources.py`
- Modify: `docs/multi-registry.md`

**Step 1: Write the failing snapshot metadata test**

Create `scripts/test-registry-snapshot-mirror.py` with fixture scenarios that:

- create a copied remote registry snapshot under `.cache/registry-snapshots/upstream/snap-20260317/registry/`
- write a snapshot metadata file such as `.cache/registry-snapshots/upstream/snap-20260317/snapshot.json`
- assert snapshot metadata records:
  - `registry`
  - `snapshot_id`
  - `created_at`
  - `source_registry` identity including `commit`, `ref`, `tag`, `trust`, and `update_mode`
  - copied `refresh_state`
  - `snapshot_root`
  - `authoritative: false`
- run `bash scripts/build-catalog.sh` and assert `catalog/registries.json` exports additive snapshot visibility such as:
  - `snapshot_count`
  - `latest_snapshot`
  - `available_snapshots`

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-registry-snapshot-mirror.py
```

Expected: FAIL because no snapshot metadata helpers or catalog export support exist yet.

**Step 3: Implement the minimal snapshot metadata contract**

Create a small shared snapshot helper library that can:

- resolve the snapshot root and metadata paths for one registry
- load snapshot metadata records
- summarize snapshots for catalog visibility

Update catalog and registry-listing surfaces so snapshot summaries become visible without changing current registry authority rules.

**Step 4: Re-run the focused test**

Run:

```bash
python3 scripts/test-registry-snapshot-mirror.py
```

Expected: PASS.

### Task 2: Add snapshot creation and verification tooling

**Files:**
- Modify: `scripts/test-registry-snapshot-mirror.py`
- Modify: `scripts/registry_snapshot_lib.py`
- Create: `scripts/create-registry-snapshot.py`
- Modify: `scripts/check-all.sh`

**Step 1: Extend the failing test**

Add scenarios that:

- sync a remote registry cache fixture
- run `python3 scripts/create-registry-snapshot.py upstream --json`
- assert the command copies the cached registry into a new immutable snapshot directory
- assert the returned JSON includes:
  - `registry`
  - `snapshot_id`
  - `snapshot_root`
  - `source_commit`
  - `source_ref` or `source_tag`
  - `refresh_state`
- assert verification fails for:
  - `local-only` registries
  - missing cache roots
  - missing refresh state for registries that declare `refresh_policy`

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-registry-snapshot-mirror.py
```

Expected: FAIL because snapshot creation tooling does not exist yet.

**Step 3: Implement minimal snapshot creation**

Create `scripts/create-registry-snapshot.py` so it:

- accepts a registry name
- validates the registry is a remote cached Git source
- copies the current cached registry checkout into a deterministic snapshot directory
- writes snapshot metadata with source identity and refresh-state context
- prints JSON describing the created snapshot

Keep the first pass additive and local-cache only. Do not change current sync defaults yet.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-registry-snapshot-mirror.py
python3 scripts/create-registry-snapshot.py upstream --help
```

Expected: PASS.

### Task 3: Teach resolver, install, and sync flows to consume explicit snapshot sources

**Files:**
- Modify: `scripts/test-registry-snapshot-mirror.py`
- Modify: `scripts/resolve-skill-source.py`
- Modify: `scripts/materialize-skill-source.py`
- Modify: `scripts/install-skill.sh`
- Modify: `scripts/sync-registry-source.sh`
- Modify: `scripts/registry_snapshot_lib.py`
- Create: `docs/registry-snapshot-mirrors.md`
- Modify: `docs/registry-refresh-policy.md`
- Modify: `docs/multi-registry.md`

**Step 1: Extend the failing test**

Add scenarios that:

- resolve a skill from `--registry upstream --snapshot <snapshot_id>` and assert the result:
  - uses the snapshot path instead of the live cache path
  - carries explicit snapshot metadata in JSON
  - does not fall back to the mutable cache if the requested snapshot is missing
- install from a snapshot-backed resolved source and assert the install manifest records snapshot identity
- run `scripts/sync-registry-source.sh upstream --snapshot <snapshot_id>` and assert it validates and returns the snapshot root without fetching remote state

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-registry-snapshot-mirror.py
```

Expected: FAIL because resolver/install/sync do not understand explicit snapshot selection yet.

**Step 3: Implement explicit snapshot consumption**

Update the relevant scripts so operators can explicitly select one snapshot for offline or recovery work:

- resolver returns a snapshot-backed source when `--snapshot` is set
- install/materialize preserve snapshot identity in downstream metadata
- sync validates and surfaces the snapshot root instead of mutating live remote state when `--snapshot` is set

Keep snapshot usage explicit. Default resolution should continue to use normal registry authority rules unless a snapshot is requested.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-registry-snapshot-mirror.py
python3 scripts/resolve-skill-source.py demo --registry upstream --snapshot latest --json
```

Expected: PASS for fixture-backed scenarios.

### Task 4: Run full verification and capture the Phase 2 start commit

**Files:**
- Modify: any files changed above

**Step 1: Run targeted checks**

Run:

```bash
python3 scripts/test-registry-snapshot-mirror.py
python3 scripts/test-registry-refresh-policy.py
```

Expected: PASS.

**Step 2: Run full verification**

Run:

```bash
./scripts/check-all.sh
```

Expected: PASS, with the existing hosted-registry e2e environment skip if Python extras remain unavailable.

**Step 3: Commit**

Run:

```bash
git add .planning/PROJECT.md .planning/REQUIREMENTS.md .planning/ROADMAP.md .planning/STATE.md docs/plans/2026-03-17-registry-snapshot-mirroring-and-offline-resolution.md scripts/test-registry-snapshot-mirror.py scripts/registry_snapshot_lib.py scripts/create-registry-snapshot.py scripts/resolve-skill-source.py scripts/materialize-skill-source.py scripts/install-skill.sh scripts/sync-registry-source.sh scripts/list-registry-sources.py scripts/build-catalog.sh docs/multi-registry.md docs/registry-refresh-policy.md docs/registry-snapshot-mirrors.md
git commit -m "feat: add registry snapshot mirrors"
```
