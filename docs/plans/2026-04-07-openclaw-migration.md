# OpenClaw Runtime Canonicalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the repository's current compatibility-first agent model with an OpenClaw-native runtime model while keeping the existing registry, release, artifact, and audit backends as the durable control plane.

**Architecture:** Move OpenClaw from "export target" to "canonical runtime contract". The registry remains the system of record for drafts, versions, releases, exposures, review, access, and artifacts, but skill/runtime semantics, workspace assumptions, sub-agent behavior, background task behavior, and plugin capability contracts are redefined around the latest OpenClaw design. Existing Claude/Codex/OpenClaw triple-compatibility abstractions become legacy migration inputs, not the maintained model.

**Tech Stack:** Python 3.11, argparse CLI, FastAPI control plane, SQLAlchemy, JSON Schema draft 2020-12, pytest, ruff, uv, OpenClaw runtime contracts documented at `docs.openclaw.ai`

---

## Migration Baseline

Latest official OpenClaw design must be treated as the source of truth for runtime semantics during this migration:

- [OpenClaw docs](https://docs.openclaw.ai/)
- [OpenClaw start guide](https://docs.openclaw.ai/start/openclaw)
- [Skills](https://docs.openclaw.ai/tools/skills)
- [Sub-Agents](https://docs.openclaw.ai/tools/subagents)
- [Plugins](https://docs.openclaw.ai/tools/plugins)
- [Background Tasks](https://docs.openclaw.ai/tools/background-tasks)
- [Cron Jobs](https://docs.openclaw.ai/tools/cron-jobs)
- [ClawHub](https://docs.openclaw.ai/tools/clawhub)

## Migration Decisions

1. Keep the current registry and hosted control plane as the durable backend.
2. Stop treating OpenClaw as one platform among several equal compatibility targets.
3. Stop using `agent_compatible` as the maintained source of runtime truth.
4. Replace renderer/bridge-centered OpenClaw support with OpenClaw-native runtime contracts.
5. Keep compatibility import/export only as explicit migration tooling until all maintained flows use the new model.

## Non-Goals

- Do not redesign the hosted UI visual language during this migration.
- Do not replace the release/artifact/audit database model in phase 1.
- Do not preserve triple-agent parity as a success criterion.
- Do not add new top-level `scripts/` unless architecture approval becomes unavoidable.

### Task 1: Freeze The New Architecture Contract

**Files:**
- Create: `docs/adr/0003-openclaw-runtime-canonical.md`
- Create: `docs/reference/openclaw-runtime-contract.md`
- Modify: `README.md`
- Modify: `docs/reference/compatibility-contract.md`
- Modify: `docs/reference/compatibility-matrix.md`

**Step 1: Write the failing docs expectation**

Add a focused integration assertion in a new or existing docs governance test that checks:
- `README.md` describes OpenClaw as the canonical runtime model
- `docs/reference/compatibility-contract.md` marks `agent_compatible` as legacy migration metadata
- `docs/reference/compatibility-matrix.md` no longer presents triple-agent compatibility as the repository center of gravity

Suggested test target:

```bash
uv run pytest tests/integration/test_cli_reference_docs.py -q
```

Expected:
- FAIL because the current docs still describe a compatibility-first model

**Step 2: Write ADR 0003**

Document:
- why the compatibility-first model is being retired
- why the registry backend remains
- which OpenClaw concepts are now first-class: workspace skills, sub-agents, plugins, background tasks, cron tasks
- which concepts become legacy: `agent_compatible`, platform render overlays, evidence-backed triple-runtime claims

**Step 3: Write the runtime contract reference**

Create `docs/reference/openclaw-runtime-contract.md` covering:
- canonical skill directory and workspace assumptions
- OpenClaw-native runtime fields
- sub-agent and background task expectations
- plugin capability expectations
- which backend records remain authoritative locally

**Step 4: Update top-level entry docs**

Update `README.md` and compatibility references so they clearly say:
- the project still owns registry/release/install backend logic
- OpenClaw is now the canonical agent runtime
- compatibility terminology is legacy and transitional

**Step 5: Re-run docs validation**

Run:

```bash
uv run pytest tests/integration/test_cli_reference_docs.py -q
make doctor
```

Expected:
- docs tests pass
- doc governance passes

**Step 6: Commit**

```bash
git add docs/adr/0003-openclaw-runtime-canonical.md docs/reference/openclaw-runtime-contract.md README.md docs/reference/compatibility-contract.md docs/reference/compatibility-matrix.md
git commit -m "docs: declare openclaw runtime canonical"
```

### Task 2: Introduce A Package-Native OpenClaw Runtime Model

**Files:**
- Create: `src/infinitas_skill/openclaw/__init__.py`
- Create: `src/infinitas_skill/openclaw/contracts.py`
- Create: `src/infinitas_skill/openclaw/runtime_model.py`
- Create: `src/infinitas_skill/openclaw/workspace.py`
- Create: `src/infinitas_skill/openclaw/plugins.py`
- Create: `tests/unit/openclaw/test_runtime_model.py`
- Create: `tests/unit/openclaw/test_workspace.py`
- Create: `tests/unit/openclaw/test_plugins.py`
- Modify: `profiles/openclaw.json`

**Step 1: Write failing unit tests for the new canonical model**

Cover:
- OpenClaw profile declares sub-agents and background tasks as native capabilities when supported by the latest contract
- runtime model normalizes workspace skill directories and agent-local state assumptions
- plugin capability parsing produces a stable internal contract

Example shape:

```python
def test_openclaw_profile_exposes_native_runtime_capabilities():
    profile = load_openclaw_runtime_profile(ROOT)
    assert profile["capabilities"]["supports_subagents"] is True
```

**Step 2: Run the new tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/openclaw/test_runtime_model.py tests/unit/openclaw/test_workspace.py tests/unit/openclaw/test_plugins.py -q
```

Expected:
- FAIL because the new package and contract helpers do not exist yet

**Step 3: Create the runtime contract layer**

Implement package-owned helpers for:
- loading and validating the canonical OpenClaw profile
- representing runtime capabilities
- resolving workspace and global skill directories
- capturing plugin capability declarations

Do not route this through `src/infinitas_skill/skills/render.py`.

**Step 4: Update `profiles/openclaw.json` to the new contract**

Replace export-era assumptions such as:
- `supports_subagents: false`
- export-only wording

With current OpenClaw-native capability and contract fields shaped for runtime use.

**Step 5: Re-run unit tests**

Run:

```bash
uv run pytest tests/unit/openclaw/test_runtime_model.py tests/unit/openclaw/test_workspace.py tests/unit/openclaw/test_plugins.py -q
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add src/infinitas_skill/openclaw profiles/openclaw.json tests/unit/openclaw/test_runtime_model.py tests/unit/openclaw/test_workspace.py tests/unit/openclaw/test_plugins.py
git commit -m "feat: add openclaw runtime contract layer"
```

### Task 3: Replace The Bridge-Centered Skill Model

**Files:**
- Modify: `src/infinitas_skill/skills/canonical.py`
- Modify: `src/infinitas_skill/skills/openclaw.py`
- Modify: `src/infinitas_skill/skills/render.py`
- Create: `src/infinitas_skill/openclaw/skill_contract.py`
- Create: `tests/unit/openclaw/test_skill_contract.py`
- Modify: `tests/integration/test_dev_workflow.py`

**Step 1: Write the failing contract test**

Cover:
- canonical skill loading produces OpenClaw-native runtime requirements
- OpenClaw skill handling no longer depends on a compatibility renderer as the source of truth
- migration helpers can still import legacy `SKILL.md` directories, but they mark them as legacy inputs

Example shape:

```python
def test_legacy_openclaw_import_is_marked_as_migration_only(tmp_path):
    payload = load_openclaw_skill_contract(tmp_path / "legacy-skill")
    assert payload["source_mode"] == "legacy-migration"
```

**Step 2: Run the test and confirm failure**

Run:

```bash
uv run pytest tests/unit/openclaw/test_skill_contract.py -q
```

Expected:
- FAIL because the new contract loader does not exist yet

**Step 3: Add `skill_contract.py`**

Implement:
- OpenClaw-native skill contract loader
- explicit legacy import mode for existing bridge flows
- canonical runtime requirement extraction
- deprecation markers for renderer-generated OpenClaw metadata

**Step 4: Refactor existing skill helpers**

Update:
- `src/infinitas_skill/skills/canonical.py` so canonical skill payloads can expose OpenClaw-native runtime fields
- `src/infinitas_skill/skills/openclaw.py` so it becomes migration tooling and validation helpers, not the canonical runtime owner
- `src/infinitas_skill/skills/render.py` so OpenClaw rendering is clearly downgraded to migration/export support

**Step 5: Re-run focused verification**

Run:

```bash
uv run pytest tests/unit/openclaw/test_skill_contract.py tests/integration/test_dev_workflow.py -q
```

Expected:
- PASS
- any dev workflow assertions are updated to treat renderer-based OpenClaw export as legacy support only

**Step 6: Commit**

```bash
git add src/infinitas_skill/skills/canonical.py src/infinitas_skill/skills/openclaw.py src/infinitas_skill/skills/render.py src/infinitas_skill/openclaw/skill_contract.py tests/unit/openclaw/test_skill_contract.py tests/integration/test_dev_workflow.py
git commit -m "refactor: demote openclaw bridge to migration tooling"
```

### Task 4: Rebuild Discovery And Install Around The OpenClaw Runtime

**Files:**
- Modify: `schemas/ai-index.schema.json`
- Modify: `src/infinitas_skill/discovery/ai_index.py`
- Modify: `src/infinitas_skill/discovery/ai_index_builder.py`
- Modify: `src/infinitas_skill/discovery/index.py`
- Modify: `src/infinitas_skill/discovery/inspect.py`
- Modify: `src/infinitas_skill/discovery/recommendation.py`
- Modify: `src/infinitas_skill/install/planning.py`
- Modify: `src/infinitas_skill/install/service.py`
- Modify: `src/infinitas_skill/install/target_validation.py`
- Create: `tests/integration/test_openclaw_runtime_index.py`
- Create: `tests/integration/test_openclaw_install_planning.py`

**Step 1: Write the failing integration coverage**

Cover:
- AI index exposes OpenClaw-native runtime fields instead of compatibility-first declarations
- install planning resolves to OpenClaw workspace/global skill targets
- inspect and recommendation speak in terms of runtime readiness, workspace fit, plugin needs, and background task support

Example assertions:

```python
assert skill["runtime"]["platform"] == "openclaw"
assert "agent_compatible" not in skill["runtime"]
```

**Step 2: Run the new integration tests**

Run:

```bash
uv run pytest tests/integration/test_openclaw_runtime_index.py tests/integration/test_openclaw_install_planning.py -q
```

Expected:
- FAIL because the index and install model are still compatibility-era

**Step 3: Reshape the AI index schema**

Replace maintained fields that center on multi-agent compatibility with OpenClaw-native runtime fields such as:
- workspace targets
- plugin capabilities
- background task requirements
- runtime readiness

If legacy fields must survive temporarily, mark them deprecated and generated-only.

**Step 4: Update discovery and install services**

Refactor discovery/install logic so maintained decision-making uses:
- OpenClaw runtime readiness
- local workspace target fit
- required plugin and task capabilities
- release/install truth from the existing backend

Do not use `agent_compatible` as a maintained decision gate.

**Step 5: Re-run focused integration tests**

Run:

```bash
uv run pytest tests/integration/test_openclaw_runtime_index.py tests/integration/test_openclaw_install_planning.py tests/integration/test_cli_install_planning.py -q
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add schemas/ai-index.schema.json src/infinitas_skill/discovery/ai_index.py src/infinitas_skill/discovery/ai_index_builder.py src/infinitas_skill/discovery/index.py src/infinitas_skill/discovery/inspect.py src/infinitas_skill/discovery/recommendation.py src/infinitas_skill/install/planning.py src/infinitas_skill/install/service.py src/infinitas_skill/install/target_validation.py tests/integration/test_openclaw_runtime_index.py tests/integration/test_openclaw_install_planning.py
git commit -m "refactor: make discovery and install openclaw-native"
```

### Task 5: Add A Maintained OpenClaw Runtime CLI Surface

**Files:**
- Create: `src/infinitas_skill/openclaw/cli.py`
- Create: `tests/integration/test_cli_openclaw_runtime.py`
- Modify: `src/infinitas_skill/cli/main.py`
- Modify: `docs/reference/cli-reference.md`

**Step 1: Write the failing CLI test**

Cover:
- `infinitas openclaw profile`
- `infinitas openclaw workspace resolve`
- `infinitas openclaw skill validate`
- `infinitas openclaw plugin inspect`

Example shape:

```python
def test_infinitas_openclaw_profile_outputs_canonical_runtime_contract():
    result = run_cli("openclaw", "profile", "--json")
    assert result["platform"] == "openclaw"
```

**Step 2: Run the test and confirm failure**

Run:

```bash
uv run pytest tests/integration/test_cli_openclaw_runtime.py -q
```

Expected:
- FAIL because the CLI surface does not exist yet

**Step 3: Implement `src/infinitas_skill/openclaw/cli.py`**

Add maintained commands for:
- profile inspection
- workspace target resolution
- skill contract validation
- plugin capability inspection

These commands should read package-owned runtime helpers instead of shelling out to legacy scripts.

**Step 4: Wire the top-level CLI**

Update `src/infinitas_skill/cli/main.py` so `infinitas openclaw ...` becomes a first-class maintained command group.

**Step 5: Update CLI docs and re-run tests**

Run:

```bash
uv run pytest tests/integration/test_cli_openclaw_runtime.py tests/integration/test_cli_reference_docs.py -q
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add src/infinitas_skill/openclaw/cli.py src/infinitas_skill/cli/main.py tests/integration/test_cli_openclaw_runtime.py docs/reference/cli-reference.md
git commit -m "feat: add maintained openclaw runtime cli"
```

### Task 6: Reframe Memory And Scheduled Work Around Agent Runtime State

**Files:**
- Modify: `docs/ai/memory.md`
- Modify: `src/infinitas_skill/memory/context.py`
- Modify: `src/infinitas_skill/discovery/recommendation_memory.py`
- Modify: `src/infinitas_skill/discovery/inspect_memory.py`
- Modify: `src/infinitas_skill/server/systemd.py`
- Create: `tests/unit/memory/test_openclaw_runtime_context.py`
- Modify: `tests/integration/test_memory_evaluation_matrix.py`

**Step 1: Write the failing memory-context test**

Cover:
- memory scopes capture OpenClaw runtime context as workspace/session/task capability context
- recommendation memory cannot override release/install truth
- scheduled memory maintenance aligns with runtime background-task semantics where relevant

**Step 2: Run the tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/memory/test_openclaw_runtime_context.py tests/integration/test_memory_evaluation_matrix.py -q
```

Expected:
- FAIL because memory context is still framed as generic advisory agent metadata

**Step 3: Update memory context and docs**

Refactor memory inputs so maintained language references:
- OpenClaw workspace and task context
- runtime capability hints
- advisory-only boundaries against release, review, access, and install truth

**Step 4: Update scheduled operation framing**

Adjust `src/infinitas_skill/server/systemd.py` and docs so background or scheduled maintenance language fits the new OpenClaw-native runtime vocabulary without making the control plane dependent on OpenClaw execution.

**Step 5: Re-run tests**

Run:

```bash
uv run pytest tests/unit/memory/test_openclaw_runtime_context.py tests/integration/test_memory_evaluation_matrix.py -q
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add docs/ai/memory.md src/infinitas_skill/memory/context.py src/infinitas_skill/discovery/recommendation_memory.py src/infinitas_skill/discovery/inspect_memory.py src/infinitas_skill/server/systemd.py tests/unit/memory/test_openclaw_runtime_context.py tests/integration/test_memory_evaluation_matrix.py
git commit -m "refactor: align memory context with openclaw runtime"
```

### Task 7: Retire Compatibility-First Platform State As A Maintained Gate

**Files:**
- Modify: `src/infinitas_skill/release/platform_state.py`
- Modify: `src/infinitas_skill/compatibility/evidence.py`
- Modify: `src/infinitas_skill/compatibility/checks.py`
- Modify: `tests/integration/test_cli_release_state.py`
- Modify: `tests/helpers/signing_bootstrap.py`

**Step 1: Write the failing release-state expectation**

Cover:
- release readiness no longer blocks on stale multi-platform compatibility evidence
- OpenClaw runtime contract freshness is checked as a single canonical runtime source
- legacy compatibility evidence remains readable for historical releases only

**Step 2: Run the release-state tests**

Run:

```bash
uv run pytest tests/integration/test_cli_release_state.py -q
```

Expected:
- FAIL because release state still treats compatibility evidence as an active maintained gate

**Step 3: Refactor release/platform checks**

Update maintained logic so:
- OpenClaw runtime contract freshness is first-class
- legacy evidence can appear in output as historical context
- release gating remains tied to release/artifact/backend truth, not triple-runtime parity

**Step 4: Re-run release-state verification**

Run:

```bash
uv run pytest tests/integration/test_cli_release_state.py -q
```

Expected:
- PASS

**Step 5: Commit**

```bash
git add src/infinitas_skill/release/platform_state.py src/infinitas_skill/compatibility/evidence.py src/infinitas_skill/compatibility/checks.py tests/integration/test_cli_release_state.py tests/helpers/signing_bootstrap.py
git commit -m "refactor: retire compatibility-first release gating"
```

### Task 8: Run The Full Migration Verification Pass

**Files:**
- Modify: `README.md`
- Modify: `docs/reference/testing.md`
- Modify: `docs/ops/platform-drift-playbook.md`
- Modify: `docs/ops/release-checklist.md`

**Step 1: Update verification docs**

Replace compatibility-era recommended checks with the new maintained OpenClaw runtime checks and clearly separate:
- maintained runtime verification
- legacy compatibility regression coverage
- backend release/install truth checks

**Step 2: Run the maintained fast path**

Run:

```bash
make lint-maintained
make test-fast
```

Expected:
- PASS

**Step 3: Run the migration-focused matrix**

Run:

```bash
uv run pytest tests/unit/openclaw tests/integration/test_openclaw_runtime_index.py tests/integration/test_openclaw_install_planning.py tests/integration/test_cli_openclaw_runtime.py tests/integration/test_cli_release_state.py tests/integration/test_memory_evaluation_matrix.py -q
```

Expected:
- PASS

**Step 4: Run the broader release verification**

Run:

```bash
./scripts/check-all.sh focused-integration
```

Expected:
- PASS

**Step 5: Commit**

```bash
git add README.md docs/reference/testing.md docs/ops/platform-drift-playbook.md docs/ops/release-checklist.md
git commit -m "docs: finalize openclaw runtime migration verification"
```

## Sequencing Notes

1. Land Tasks 1-3 before changing discovery/install outputs.
2. Land Task 4 before adding the public CLI surface in Task 5 so the CLI reads the correct runtime model.
3. Land Task 6 after the runtime model exists, otherwise memory terminology will drift again.
4. Land Task 7 after discovery/install have stopped using compatibility-era concepts.
5. Keep legacy OpenClaw bridge tests only until the maintained OpenClaw runtime path is fully green.

## Success Criteria

- OpenClaw is documented and implemented as the canonical runtime model.
- Registry/release/install backend truth remains intact.
- Maintained CLI includes an `infinitas openclaw ...` surface.
- Discovery/install/index logic no longer uses triple-agent compatibility as the primary model.
- Compatibility evidence remains historical or transitional, not the center of release gating.
- The hosted UI remains visually consistent while backend/runtime semantics are migrated.
