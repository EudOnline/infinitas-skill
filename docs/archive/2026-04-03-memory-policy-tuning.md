# Memory Policy Tuning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve Memo0-backed memory quality by adding explicit lifecycle memory policies and better advisory ranking for recommendation and inspect.

**Architecture:** Add a small memory policy layer that decides memory type, confidence, and TTL from lifecycle events. Use that metadata during retrieval to sort and trim memories more reliably before recommendation boosts or inspect hints are rendered. Keep all effects advisory-only and bounded.

**Tech Stack:** Python 3.11, existing `src/infinitas_skill/memory` package, discovery recommendation and inspect flows, `pytest`

---

### Task 1: Add explicit memory policy defaults for lifecycle events

**Files:**
- Create: `src/infinitas_skill/memory/policy.py`
- Modify: `src/infinitas_skill/memory/experience.py`
- Modify: `src/infinitas_skill/memory/__init__.py`
- Modify: `tests/unit/memory/test_experience.py`

**Step 1: Write failing tests**

Add tests for:

- `task.release.ready` classifies as `experience`
- `task.review.approve` and `task.review.reject` classify as `experience`
- `task.authoring.create_draft` remains `task_context`
- policy-backed confidence and TTL defaults are attached to the memory record

**Step 2: Run the focused test to verify RED**

Run:

```bash
uv run pytest tests/unit/memory/test_experience.py -q
```

**Step 3: Implement the policy layer**

Add a small policy resolver that maps event families to:

- `memory_type`
- `confidence`
- `ttl_seconds`

Use that resolver from `build_experience_memory(...)` when explicit values are not provided.

**Step 4: Re-run the focused test**

Run:

```bash
uv run pytest tests/unit/memory/test_experience.py -q
```

### Task 2: Make retrieval ranking quality-aware

**Files:**
- Modify: `src/infinitas_skill/memory/context.py`
- Modify: `src/infinitas_skill/discovery/recommendation.py`
- Modify: `src/infinitas_skill/discovery/inspect.py`
- Modify: `tests/unit/memory/test_context.py`
- Modify: `tests/unit/discovery/test_memory_recommendation.py`
- Modify: `tests/unit/discovery/test_memory_inspect.py`

**Step 1: Write failing tests**

Add tests for:

- trimming prefers higher effective memory quality, not just raw provider score
- recommendation prefers higher-confidence matched memory when ties are close
- inspect hint ordering prefers stronger experience memories

**Step 2: Run the focused tests to verify RED**

Run:

```bash
uv run pytest tests/unit/memory/test_context.py tests/unit/discovery/test_memory_recommendation.py tests/unit/discovery/test_memory_inspect.py -q
```

**Step 3: Implement quality-aware ranking**

Add a small effective score function using:

- provider score
- metadata confidence
- memory type weighting
- TTL weighting

Use it consistently in memory trimming and result ordering, while keeping recommendation boosts bounded and advisory-only.

**Step 4: Re-run the focused tests**

Run:

```bash
uv run pytest tests/unit/memory/test_context.py tests/unit/discovery/test_memory_recommendation.py tests/unit/discovery/test_memory_inspect.py -q
```

### Task 3: Refresh docs and verify the full memory slice

**Files:**
- Modify: `docs/ai/memory.md`
- Modify: `docs/ai/recommend.md`
- Modify: `docs/ai/discovery.md`

**Step 1: Update docs**

Document:

- lifecycle policy examples
- the difference between short-lived task context and reusable experience memory
- how confidence and TTL now influence advisory ranking

**Step 2: Run the verification matrix**

Run:

```bash
uv run pytest tests/unit/memory/test_provider.py tests/unit/memory/test_context.py tests/unit/memory/test_experience.py tests/unit/discovery/test_memory_recommendation.py tests/unit/discovery/test_memory_inspect.py tests/unit/server_memory/test_writeback.py tests/integration/test_private_registry_memory_flow.py -q
python3 scripts/test-recommend-skill.py
python3 scripts/test-search-inspect.py
uv run pytest tests/integration/test_private_registry_ui.py -q
make doctor
make ci-fast
```

**Step 3: Commit**

```bash
git add src/infinitas_skill/memory/policy.py src/infinitas_skill/memory/experience.py src/infinitas_skill/memory/context.py src/infinitas_skill/memory/__init__.py src/infinitas_skill/discovery/recommendation.py src/infinitas_skill/discovery/inspect.py tests/unit/memory/test_experience.py tests/unit/memory/test_context.py tests/unit/discovery/test_memory_recommendation.py tests/unit/discovery/test_memory_inspect.py docs/ai/memory.md docs/ai/recommend.md docs/ai/discovery.md docs/plans/2026-04-03-memory-policy-tuning.md
git commit -m "feat: tune memory policy and retrieval quality"
```
