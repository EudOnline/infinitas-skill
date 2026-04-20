# Multi-Object Agent Distribution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the hosted registry so it can fully store publishable object content and support three first-class object types: `skill`, `agent_code`, and `agent_preset`, including memory-aware OpenClaw preset sharing.

**Architecture:** Keep the external API object-specific, but move the hosted lifecycle onto a shared object-release core. First add durable hosted content snapshots for the existing skill flow, then introduce `agent_preset`, then add `agent_code` plus immutable external-import support. Reuse existing release, artifact, exposure, and registry projection machinery wherever possible.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Pydantic, Pytest, existing release/attestation helpers, local artifact storage.

---

### Task 1: Freeze The New Product Vocabulary In Docs And Schemas

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/guide/private-first-cutover.md`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/ai/publish.md`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/reference/openclaw-runtime-contract.md`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/schemas/agent-preset.schema.json`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/schemas/agent-code.schema.json`
- Test: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/scripts/test-doc-governance.py`

**Step 1: Write the failing schema contract notes**

Document the new object vocabulary in scratch notes:
- `skill`
- `agent_code`
- `agent_preset`
- `memory_mode`
- `content_mode`

Expected: Every later code path uses these exact names with no alias drift.

**Step 2: Add initial JSON schema stubs**

Create minimal schema files containing:
- top-level `kind`
- `schema_version`
- `runtime`
- `dependencies`
- memory fields for presets

Expected: Schemas are present, parseable, and narrow enough to guide later API and catalog work.

**Step 3: Update the docs to describe the three first-class objects**

Add explicit statements:
- hosted storage can own complete content bundles
- `agent_preset` is the shared OpenClaw configuration object
- `agent_code` is for lightweight runnable agent code

**Step 4: Run doc governance**

Run: `uv run python scripts/test-doc-governance.py`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/guide/private-first-cutover.md docs/ai/publish.md docs/reference/openclaw-runtime-contract.md schemas/agent-preset.schema.json schemas/agent-code.schema.json
git commit -m "docs: define multi-object agent distribution vocabulary"
```

### Task 2: Add Shared Hosted Object Storage Primitives

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/authoring/models.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/release/models.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/alembic/versions/20260419_0007_registry_objects_and_draft_content.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/models.py`
- Test: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/scripts/test-migrations.py`

**Step 1: Write the failing migration test**

Add a migration contract test that expects new durable fields:
- shared object base table or generalized object foreign key
- draft `content_mode`
- draft `content_artifact_id`
- optional sealed manifest payload

Run: `uv run python scripts/test-migrations.py`
Expected: FAIL because the new columns and tables do not exist yet.

**Step 2: Implement the migration**

Create the Alembic revision to add:
- shared object table or generalized object ownership fields
- content artifact references
- optional object kind fields

Expected: Migration upgrades and downgrades cleanly.

**Step 3: Update SQLAlchemy models**

Add model fields matching the migration exactly.

Expected: ORM and migration stay aligned.

**Step 4: Re-run migration test**

Run: `uv run python scripts/test-migrations.py`
Expected: PASS

**Step 5: Commit**

```bash
git add server/modules/authoring/models.py server/modules/release/models.py server/models.py alembic/versions/20260419_0007_registry_objects_and_draft_content.py
git commit -m "feat: add hosted object content storage primitives"
```

### Task 3: Make Hosted Drafts Store Complete Content

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/authoring/schemas.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/authoring/repository.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/authoring/service.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/authoring/router.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_authoring_content_storage.py`

**Step 1: Write the failing integration test**

Add one test for each path:
- create draft with inline uploaded content bundle
- create draft with external immutable `content_ref`
- seal draft and verify both content and metadata digests are frozen

Run: `uv run pytest -q tests/integration/test_authoring_content_storage.py`
Expected: FAIL because the authoring API cannot yet accept durable content artifacts.

**Step 2: Extend the request schema**

Add request fields:
- `content_mode`
- `content_ref`
- `content_upload_token` or equivalent uploaded artifact reference

Expected: API payload shape can represent both inline and external modes.

**Step 3: Implement repository + service storage**

Store:
- `content_mode`
- `content_ref`
- `content_artifact_id`
- frozen manifest metadata at seal time

Expected: Hosted drafts can now persist complete content.

**Step 4: Re-run the authoring integration test**

Run: `uv run pytest -q tests/integration/test_authoring_content_storage.py`
Expected: PASS

**Step 5: Commit**

```bash
git add server/modules/authoring/schemas.py server/modules/authoring/repository.py server/modules/authoring/service.py server/modules/authoring/router.py tests/integration/test_authoring_content_storage.py
git commit -m "feat: store complete hosted draft content"
```

### Task 4: Upgrade Hosted Release Materialization To Bundle Real Content

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/release/materializer.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/release/service.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/release/storage.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/src/infinitas_skill/install/distribution.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_private_registry_release_materialization.py`

**Step 1: Write the failing regression for real-content release output**

Add assertions that a hosted inline-content release bundle contains:
- `SKILL.md`
- `_meta.json`
- other expected files from the uploaded content tree

Run: `uv run pytest -q tests/integration/test_private_registry_release_materialization.py`
Expected: FAIL because hosted materialization still emits only snapshot metadata files.

**Step 2: Implement real bundle materialization**

Replace the current snapshot-only bundle path with:
- inline bundle passthrough for hosted uploaded content
- fetched-and-frozen staging for external immutable refs

Expected: Hosted releases now emit complete install bundles.

**Step 3: Preserve manifest/provenance compatibility**

Ensure the generated manifest still includes:
- `file_manifest`
- `build`
- dependency context
- attestation references

Expected: Existing distribution verification continues to pass.

**Step 4: Re-run the hosted materialization tests**

Run: `uv run pytest -q tests/integration/test_private_registry_release_materialization.py`
Expected: PASS

**Step 5: Commit**

```bash
git add server/modules/release/materializer.py server/modules/release/service.py server/modules/release/storage.py src/infinitas_skill/install/distribution.py tests/integration/test_private_registry_release_materialization.py
git commit -m "feat: materialize complete hosted release bundles"
```

### Task 5: Introduce Agent Preset As The First New Object Type

**Files:**
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_presets/__init__.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_presets/models.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_presets/schemas.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_presets/service.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_presets/router.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/app.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_agent_preset_api.py`

**Step 1: Write the failing preset API test**

Add tests for:
- create preset object
- create draft preset payload
- seal a preset version
- declare pinned skill dependencies
- declare supported memory modes

Run: `uv run pytest -q tests/integration/test_agent_preset_api.py`
Expected: FAIL because the preset module does not exist yet.

**Step 2: Implement the preset extension model**

Store:
- runtime family
- prompt/tool/model fields
- supported memory modes
- default memory mode
- pinned skill dependency list

Expected: Presets become first-class publishable objects.

**Step 3: Mount the router**

Expose:
- `/api/v1/agent-presets`
- preset draft endpoints
- preset seal endpoints

Expected: API surface is available in the app.

**Step 4: Re-run the preset API test**

Run: `uv run pytest -q tests/integration/test_agent_preset_api.py`
Expected: PASS

**Step 5: Commit**

```bash
git add server/modules/agent_presets server/app.py tests/integration/test_agent_preset_api.py
git commit -m "feat: add agent preset publishing APIs"
```

### Task 6: Add Memory Variants To Preset Release And Install Projections

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/discovery/service.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/discovery/schemas.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/registry/service.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/src/infinitas_skill/install/service.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_agent_preset_install_variants.py`

**Step 1: Write the failing install-variant test**

Add tests that expect discovery/install metadata to expose:
- `supported_memory_modes`
- `default_memory_mode`
- selected install variant in the resolved install plan

Run: `uv run pytest -q tests/integration/test_agent_preset_install_variants.py`
Expected: FAIL because memory variants are not projected today.

**Step 2: Extend discovery + registry projections**

Project preset install metadata into:
- discovery payloads
- registry distribution payloads
- install planner output

Expected: Presets advertise memory choices to downstream installers.

**Step 3: Extend install planning**

Allow install requests to choose:
- `none`
- `local`
- `shared`

Expected: Install planning resolves variant metadata without mutating the released preset definition.

**Step 4: Re-run the install-variant test**

Run: `uv run pytest -q tests/integration/test_agent_preset_install_variants.py`
Expected: PASS

**Step 5: Commit**

```bash
git add server/modules/discovery/service.py server/modules/discovery/schemas.py server/modules/registry/service.py src/infinitas_skill/install/service.py tests/integration/test_agent_preset_install_variants.py
git commit -m "feat: expose memory-aware preset install variants"
```

### Task 7: Add Agent Code Support With Immutable External Import

**Files:**
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_codes/__init__.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_codes/models.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_codes/schemas.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_codes/service.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/agent_codes/router.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/release/materializer.py`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_agent_code_import.py`

**Step 1: Write the failing external-import test**

Add tests for:
- create `agent_code` draft from immutable GitHub-like ref
- seal and release it
- verify the hosted platform emits its own complete bundle

Run: `uv run pytest -q tests/integration/test_agent_code_import.py`
Expected: FAIL because the agent-code module and import workflow do not exist.

**Step 2: Implement the agent-code extension model**

Store:
- runtime family
- language
- entrypoint
- external source metadata

Expected: Lightweight runnable agents become first-class publishable objects.

**Step 3: Implement immutable-import materialization**

At seal or release time:
- verify the external ref is immutable
- stage the upstream content
- convert it into a hosted bundle

Expected: Downstream installs rely on platform-owned artifacts, not live upstream state.

**Step 4: Re-run the import integration test**

Run: `uv run pytest -q tests/integration/test_agent_code_import.py`
Expected: PASS

**Step 5: Commit**

```bash
git add server/modules/agent_codes server/modules/release/materializer.py tests/integration/test_agent_code_import.py
git commit -m "feat: add agent code publishing and immutable import"
```

### Task 8: Rebuild Registry, CLI, And Verification Surfaces

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/src/infinitas_skill/registry/cli.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/src/infinitas_skill/install/planning.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/registry/router.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/registry/service.py`
- Modify: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/scripts/build-catalog.sh`
- Create: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration/test_multi_object_registry_surfaces.py`

**Step 1: Write the failing multi-object registry test**

Add assertions that registry and discovery surfaces can list:
- skills
- agent presets
- agent code

Run: `uv run pytest -q tests/integration/test_multi_object_registry_surfaces.py`
Expected: FAIL because registry projections are still skill-shaped.

**Step 2: Extend the registry/discovery payload model**

Include:
- `kind`
- object-specific install metadata
- dependency summaries
- preset memory variant summaries

Expected: Catalog and hosted registry become multi-object aware.

**Step 3: Extend maintained CLI install planning**

Allow install planning by object kind and variant-aware preset installs.

Expected: The maintained CLI can plan installs for all supported object types.

**Step 4: Re-run the registry test**

Run: `uv run pytest -q tests/integration/test_multi_object_registry_surfaces.py`
Expected: PASS

**Step 5: Commit**

```bash
git add src/infinitas_skill/registry/cli.py src/infinitas_skill/install/planning.py server/modules/registry/router.py server/modules/registry/service.py scripts/build-catalog.sh tests/integration/test_multi_object_registry_surfaces.py
git commit -m "feat: project multi-object registry and install surfaces"
```

### Task 9: Run The Verification Matrix And Close The Slice

**Files:**
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/integration`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/tests/unit`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/plans/2026-04-19-multi-object-agent-distribution-design.md`
- Review: `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/plans/2026-04-19-multi-object-agent-distribution-implementation-plan.md`

**Step 1: Run the focused new-feature matrix**

Run:

```bash
uv run pytest -q \
  tests/integration/test_authoring_content_storage.py \
  tests/integration/test_private_registry_release_materialization.py \
  tests/integration/test_agent_preset_api.py \
  tests/integration/test_agent_preset_install_variants.py \
  tests/integration/test_agent_code_import.py \
  tests/integration/test_multi_object_registry_surfaces.py
```

Expected: PASS

**Step 2: Run maintained lint**

Run: `make lint-maintained`
Expected: PASS

**Step 3: Run maintained fast gate**

Run: `make test-fast`
Expected: PASS

**Step 4: Run release/distribution regression spot checks**

Run:

```bash
uv run python scripts/test-release-invariants.py
uv run python scripts/test-distribution-install.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add docs tests server src scripts
git commit -m "feat: ship multi-object agent distribution foundations"
```
