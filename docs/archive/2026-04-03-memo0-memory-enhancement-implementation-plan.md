# Memo0 Memory Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add true long-term memory to the current agent system by layering Memo0-backed user or task memory plus experience memory on top of the existing private-first registry, without replacing the current auditable release, review, access, or install state.

**Architecture:** Keep the current database, registry projections, and audit surfaces as the source of truth. Add a feature-flagged memory layer with a provider abstraction, a default no-op backend, and a Memo0 adapter that is only used for cognitive memory. Read memory before recommendation and inspect flows to improve ranking and guidance, then write memory after meaningful lifecycle events so successful or failed work becomes reusable experience. Memory must remain advisory: it can influence explanations and soft ranking, but it must never bypass compatibility checks, access control, review policy, or immutable release rules.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, existing `src/infinitas_skill.discovery` decision chain, existing server lifecycle services, environment-driven settings, `pytest`, maintained script regressions, and optional `mem0ai` integration via `pip install mem0ai`.

---

## Preconditions

- Work in the current repository state; do not reset unrelated files.
- Default behavior must stay unchanged when memory is disabled or Memo0 is not installed.
- Treat Memo0 as additive cognitive memory only. Do not move release state, review state, access state, or install state out of the local database and immutable artifacts.
- Keep all memory effects soft and explainable. Hard allow or deny decisions must still come from current policy, compatibility, and access code paths.

## Scope Decisions

- Recommended backend for v1: self-hosted Memo0 behind a provider abstraction.
- Required memory types for v1:
  - user or task memory: preferences, recent goals, preferred target agent, stability bias, private-first bias
  - experience memory: successful workflow patterns, repeated failure modes, review friction, install pitfalls
- Required read paths for v1:
  - `src/infinitas_skill/discovery/recommendation.py`
  - `src/infinitas_skill/discovery/inspect.py`
- Required write paths for v1:
  - authoring or release lifecycle
  - exposure or review lifecycle
  - memory-specific audit events for traceability
- Non-goals for v1:
  - replacing the existing DB with Memo0
  - changing access control behavior
  - letting memory auto-publish, auto-approve, or auto-install anything
  - broad UI product work beyond minimal explainability fields or debug coverage

### Task 1: Add the feature-flagged memory provider layer

**Files:**
- Create: `src/infinitas_skill/memory/__init__.py`
- Create: `src/infinitas_skill/memory/config.py`
- Create: `src/infinitas_skill/memory/contracts.py`
- Create: `src/infinitas_skill/memory/provider.py`
- Create: `src/infinitas_skill/memory/memo0_provider.py`
- Create: `tests/unit/memory/test_provider.py`
- Modify: `pyproject.toml`
- Modify: `server/settings.py`

**Step 1: Write the failing provider and settings tests**

Create `tests/unit/memory/test_provider.py` with coverage for:

```python
def test_disabled_backend_returns_noop_provider(monkeypatch):
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "disabled")
    provider = build_memory_provider()
    assert provider.backend_name == "noop"


def test_memo0_backend_without_sdk_falls_back_to_noop(monkeypatch):
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "memo0")
    provider = build_memory_provider(importer=lambda: (_ for _ in ()).throw(ImportError()))
    assert provider.backend_name == "noop"
    assert provider.capabilities["write"] is False


def test_settings_read_memory_flags(monkeypatch):
    monkeypatch.setenv("INFINITAS_MEMORY_BACKEND", "memo0")
    monkeypatch.setenv("INFINITAS_MEMORY_CONTEXT_ENABLED", "1")
    monkeypatch.setenv("INFINITAS_MEMORY_WRITE_ENABLED", "1")
    settings = get_settings()
    assert settings.memory_backend == "memo0"
    assert settings.memory_context_enabled is True
    assert settings.memory_write_enabled is True
```

**Step 2: Run the unit tests to verify RED**

Run:

```bash
uv run pytest tests/unit/memory/test_provider.py -q
```

Expected: FAIL because the memory package, provider abstraction, and settings fields do not exist yet.

**Step 3: Implement the provider abstraction and settings**

Add:

- `src/infinitas_skill/memory/contracts.py`
  - `MemoryProvider` protocol
  - `MemorySearchResult`
  - `MemoryWriteResult`
  - `MemoryRecord`
- `src/infinitas_skill/memory/config.py`
  - parse and normalize memory env vars
- `src/infinitas_skill/memory/provider.py`
  - `NoopMemoryProvider`
  - `build_memory_provider(...)`
- `src/infinitas_skill/memory/memo0_provider.py`
  - lazy Memo0 import
  - adapter methods for `search` and `add`
  - normalized filter mapping for user, agent, run, and memory type scopes
- `server/settings.py`
  - add settings for:
    - `memory_backend`
    - `memory_context_enabled`
    - `memory_write_enabled`
    - `memory_namespace`
    - `memory_top_k`
    - `memory_mem0_base_url`
    - `memory_mem0_api_key_env`

Keep all imports lazy so the repo still boots and tests still run without `mem0ai` installed.

**Step 4: Re-run the focused tests**

Run:

```bash
uv run pytest tests/unit/memory/test_provider.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml server/settings.py src/infinitas_skill/memory/__init__.py src/infinitas_skill/memory/config.py src/infinitas_skill/memory/contracts.py src/infinitas_skill/memory/provider.py src/infinitas_skill/memory/memo0_provider.py tests/unit/memory/test_provider.py
git commit -m "feat: add feature-flagged memory provider layer"
```

### Task 2: Define canonical user or task memory and experience memory payload builders

**Files:**
- Create: `src/infinitas_skill/memory/scopes.py`
- Create: `src/infinitas_skill/memory/context.py`
- Create: `src/infinitas_skill/memory/experience.py`
- Create: `tests/unit/memory/test_context.py`
- Create: `tests/unit/memory/test_experience.py`

**Step 1: Write failing payload-builder tests**

Create `tests/unit/memory/test_context.py` with cases like:

```python
def test_build_recommendation_memory_query_prefers_user_and_agent_scopes():
    query = build_recommendation_memory_query(
        task="install released skill into openclaw runtime",
        target_agent="openclaw",
        user_ref="maintainer",
    )
    assert query.scope_refs == ["user:maintainer", "agent:openclaw", "task:install"]
    assert query.memory_types == ["user_preference", "task_context", "experience"]
```

Create `tests/unit/memory/test_experience.py` with cases like:

```python
def test_build_review_approval_experience_memory_is_traceable():
    memory = build_experience_memory(
        event_type="review.approved",
        aggregate_ref="review_case:12",
        payload={"qualified_name": "lvxiaoer/release-infinitas-skill", "audience_type": "public"},
    )
    assert memory.memory_type == "experience"
    assert memory.source_refs == ["review_case:12"]
    assert "public" in memory.content
```

**Step 2: Run the unit tests to verify RED**

Run:

```bash
uv run pytest tests/unit/memory/test_context.py tests/unit/memory/test_experience.py -q
```

Expected: FAIL because the scope and payload builder modules do not exist yet.

**Step 3: Implement the canonical builders**

Add:

- `src/infinitas_skill/memory/scopes.py`
  - canonical scope refs such as `user:<slug>`, `principal:<id>`, `agent:<name>`, `skill:<qualified_name>`, `task:<verb>`
- `src/infinitas_skill/memory/context.py`
  - functions to build retrieval queries for recommendation and inspect
  - dedupe and trim logic for retrieved memories
  - deterministic rendering of memory snippets into small advisory context blocks
- `src/infinitas_skill/memory/experience.py`
  - normalize lifecycle events into:
    - `user_preference`
    - `task_context`
    - `experience`
  - attach `source_refs`, `confidence`, `ttl`, and provider metadata

Hard rules for these builders:

- never emit filesystem paths into memory content
- never store secrets or tokens
- never encode authorization grants as memory
- keep each memory item small and human-auditable

**Step 4: Re-run the focused tests**

Run:

```bash
uv run pytest tests/unit/memory/test_context.py tests/unit/memory/test_experience.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/infinitas_skill/memory/scopes.py src/infinitas_skill/memory/context.py src/infinitas_skill/memory/experience.py tests/unit/memory/test_context.py tests/unit/memory/test_experience.py
git commit -m "feat: add canonical memory context and experience builders"
```

### Task 3: Integrate memory retrieval into recommendation scoring and explanation

**Files:**
- Create: `tests/unit/discovery/test_memory_recommendation.py`
- Modify: `src/infinitas_skill/discovery/recommendation.py`
- Modify: `scripts/test-recommend-skill.py`
- Modify: `docs/ai/recommend.md`

**Step 1: Write failing unit and script regressions**

Create `tests/unit/discovery/test_memory_recommendation.py` with a fake provider:

```python
class FakeMemoryProvider:
    backend_name = "fake"
    capabilities = {"read": True, "write": True}

    def search(self, *, query, limit):
        return [
            {"memory": "User prefers stable OpenClaw install workflows.", "memory_type": "user_preference", "score": 0.96},
            {"memory": "Install failures often happen when release artifacts are not ready.", "memory_type": "experience", "score": 0.91},
        ]


def test_recommendation_applies_soft_memory_boost_without_bypassing_compatibility(tmp_path):
    payload = recommend_skills(
        tmp_path,
        task="install released skill into openclaw runtime",
        target_agent="openclaw",
        memory_provider=FakeMemoryProvider(),
        memory_scope={"user_ref": "maintainer"},
    )
    assert payload["results"][0]["qualified_name"] == "lvxiaoer/consume-infinitas-skill"
    assert payload["results"][0]["memory_signals"]["matched_memory_count"] == 2
```

Extend `scripts/test-recommend-skill.py` with a scenario that expects:

- memory-aware explanation fields
- top recommendation remains deterministic when memory is absent
- memory can break close ties, but cannot lift an incompatible skill above a compatible one

**Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/unit/discovery/test_memory_recommendation.py -q
python3 scripts/test-recommend-skill.py
```

Expected: FAIL because recommendation has no memory-aware inputs or output fields yet.

**Step 3: Implement memory-aware recommendation**

Modify `src/infinitas_skill/discovery/recommendation.py` to:

- accept optional `memory_provider` and `memory_scope`
- retrieve top-k relevant memories before scoring
- compute a bounded `memory_boost` that only applies after compatibility gating
- expose explainable fields such as:

```python
"memory_signals": {
    "matched_memory_count": 2,
    "applied_boost": 35,
    "memory_types": ["user_preference", "experience"],
}
```

- expose top-level explanation fields such as:

```python
"memory_summary": {
    "used": True,
    "backend": "memo0",
    "matched_count": 2,
    "advisory_only": True,
}
```

Guardrails:

- do not apply memory if `memory_context_enabled` is false
- do not let memory override incompatible, blocked, or unsupported candidates
- cap the boost so explicit metadata and verified support remain primary

**Step 4: Re-run the focused checks**

Run:

```bash
uv run pytest tests/unit/discovery/test_memory_recommendation.py -q
python3 scripts/test-recommend-skill.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/infinitas_skill/discovery/recommendation.py tests/unit/discovery/test_memory_recommendation.py scripts/test-recommend-skill.py docs/ai/recommend.md
git commit -m "feat: add memory-aware recommendation scoring"
```

### Task 4: Integrate experience memory into inspect output without changing trust semantics

**Files:**
- Create: `tests/unit/discovery/test_memory_inspect.py`
- Modify: `src/infinitas_skill/discovery/inspect.py`
- Modify: `scripts/test-search-inspect.py`
- Modify: `docs/ai/discovery.md`

**Step 1: Write failing inspect tests**

Create `tests/unit/discovery/test_memory_inspect.py` with a fake provider:

```python
def test_inspect_returns_experience_hints_as_advisory_context(tmp_path):
    payload = inspect_skill(
        tmp_path,
        name="lvxiaoer/consume-infinitas-skill",
        memory_provider=FakeMemoryProvider([
            {"memory": "OpenClaw installs usually succeed when the release is already materialized.", "memory_type": "experience", "score": 0.94}
        ]),
        memory_scope={"user_ref": "maintainer"},
    )
    assert payload["memory_hints"]["used"] is True
    assert payload["memory_hints"]["items"][0]["memory_type"] == "experience"
```

Extend `scripts/test-search-inspect.py` so inspect output must include a `memory_hints` block when memory is available, and that trust fields remain unchanged.

**Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/unit/discovery/test_memory_inspect.py -q
python3 scripts/test-search-inspect.py
```

Expected: FAIL because inspect has no memory-aware inputs or advisory output block.

**Step 3: Implement advisory inspect memory**

Modify `src/infinitas_skill/discovery/inspect.py` to:

- accept optional `memory_provider` and `memory_scope`
- fetch only experience and task-context memories relevant to the inspected skill
- return a compact `memory_hints` block with:
  - whether memory was used
  - backend name
  - matched count
  - small sanitized hint items

Keep current trust derivation unchanged:

- `trust_state` still comes from provenance and artifact evidence
- memory can annotate likely pitfalls or successful patterns
- memory cannot mark a skill verified, trusted, or installable

**Step 4: Re-run the focused checks**

Run:

```bash
uv run pytest tests/unit/discovery/test_memory_inspect.py -q
python3 scripts/test-search-inspect.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/infinitas_skill/discovery/inspect.py tests/unit/discovery/test_memory_inspect.py scripts/test-search-inspect.py docs/ai/discovery.md
git commit -m "feat: add advisory memory hints to inspect flow"
```

### Task 5: Add auditable writeback hooks for lifecycle events and experience capture

**Files:**
- Create: `server/modules/audit/service.py`
- Create: `server/modules/memory/__init__.py`
- Create: `server/modules/memory/service.py`
- Create: `tests/unit/server_memory/test_writeback.py`
- Create: `tests/integration/test_private_registry_memory_flow.py`
- Modify: `server/modules/authoring/service.py`
- Modify: `server/modules/release/service.py`
- Modify: `server/modules/exposure/service.py`
- Modify: `server/modules/review/service.py`

**Step 1: Write failing writeback tests**

Create `tests/unit/server_memory/test_writeback.py` with cases like:

```python
def test_memory_writeback_is_best_effort_when_provider_is_disabled(session):
    result = record_experience_from_event(
        session,
        event_type="release.ready",
        aggregate_ref="release:7",
        payload={"qualified_name": "lvxiaoer/release-infinitas-skill"},
        provider=NoopMemoryProvider(),
    )
    assert result.status == "skipped"


def test_memory_writeback_emits_traceable_audit_event(session, fake_provider):
    result = record_experience_from_event(
        session,
        event_type="review.approved",
        aggregate_ref="review_case:12",
        payload={"qualified_name": "lvxiaoer/release-infinitas-skill"},
        provider=fake_provider,
    )
    assert result.status == "stored"
    assert result.audit_event_ref.startswith("audit_event:")
```

Create `tests/integration/test_private_registry_memory_flow.py` by reusing the same style as `tests/integration/test_private_registry_ui.py`:

- create skill
- create draft
- seal version
- create release
- create public exposure
- approve review
- assert memory write hooks were attempted
- assert memory-specific audit events were recorded

**Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/unit/server_memory/test_writeback.py tests/integration/test_private_registry_memory_flow.py -q
```

Expected: FAIL because there is no audit helper, no memory writeback service, and no lifecycle hooks yet.

**Step 3: Implement auditable writeback**

Add `server/modules/audit/service.py` with a helper like:

```python
def append_audit_event(db, *, aggregate_type, aggregate_id, event_type, actor_ref, payload):
    ...
```

Add `server/modules/memory/service.py` with:

- `record_user_task_memory(...)`
- `record_experience_memory(...)`
- `record_lifecycle_memory_event(...)`
- best-effort provider writes
- memory-specific audit event emission
- dedupe keys so one lifecycle event does not create duplicate memories repeatedly

Modify:

- `server/modules/authoring/service.py`
  - write task-context memory for draft and seal actions
- `server/modules/release/service.py`
  - write experience memory when a release becomes ready
- `server/modules/exposure/service.py`
  - write experience memory for exposure creation and activation
- `server/modules/review/service.py`
  - write experience memory for approve or reject outcomes

Hard rules:

- if provider write fails, do not fail the release or review transaction
- instead emit a failure audit event with sanitized error details
- do not write secrets, raw credentials, or grant tokens into memory payloads

**Step 4: Re-run the focused checks**

Run:

```bash
uv run pytest tests/unit/server_memory/test_writeback.py tests/integration/test_private_registry_memory_flow.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add server/modules/audit/service.py server/modules/memory/__init__.py server/modules/memory/service.py server/modules/authoring/service.py server/modules/release/service.py server/modules/exposure/service.py server/modules/review/service.py tests/unit/server_memory/test_writeback.py tests/integration/test_private_registry_memory_flow.py
git commit -m "feat: add auditable lifecycle memory writeback"
```

### Task 6: Document the operating model and run the final verification matrix

**Files:**
- Create: `docs/ai/memory.md`
- Modify: `README.md`
- Modify: `docs/ai/recommend.md`
- Modify: `docs/ai/discovery.md`
- Modify: `docs/guide/private-first-cutover.md`

**Step 1: Write the memory contract documentation**

Document:

- what Memo0 is used for in this repo
- what still remains the source of truth locally
- the difference between:
  - user or task memory
  - experience memory
  - audit events
  - release and review state
- required env vars
- feature-flag behavior when Memo0 is unavailable
- the hard guarantee that memory is advisory only

**Step 2: Add explicit docs examples**

Include examples for:

- recommendation result with `memory_summary`
- inspect result with `memory_hints`
- failure mode where memory writeback is skipped or logged but core workflow still succeeds

**Step 3: Run the full focused verification matrix**

Run:

```bash
uv run pytest tests/unit/memory/test_provider.py tests/unit/memory/test_context.py tests/unit/memory/test_experience.py tests/unit/discovery/test_memory_recommendation.py tests/unit/discovery/test_memory_inspect.py tests/unit/server_memory/test_writeback.py tests/integration/test_private_registry_memory_flow.py -q
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
uv run pytest tests/integration/test_private_registry_ui.py -q
make doctor
```

Expected:

- all new unit tests pass
- recommend and inspect script regressions pass
- private registry UI regression still passes
- docs governance still passes

**Step 4: Run the maintained fast baseline**

Run:

```bash
make ci-fast
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/ai/memory.md docs/ai/recommend.md docs/ai/discovery.md docs/guide/private-first-cutover.md
git commit -m "docs: add memory operating model and verification"
```

## Release Notes For This Slice

When this plan is complete, the repository should have:

- a disabled-by-default memory layer
- a Memo0 adapter behind a local abstraction
- user or task memory retrieval in recommendation
- experience memory retrieval in inspect
- auditable lifecycle writeback for experience capture
- docs that make the source-of-truth boundary explicit

The repository should not yet have:

- memory-driven automatic policy decisions
- public product claims that memory changes governance or access control
- any dependency on Memo0 for core registry operation when feature flags are off
