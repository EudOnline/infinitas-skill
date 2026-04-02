# Discovery Chain And Scorecard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the next highest-value maintainability cleanup by moving the discovery/recommend/install-explanation chain into `src/infinitas_skill`, then publish a final release-readiness scorecard backed by fresh verification evidence.

**Architecture:** Treat the long release tests as now proven green and stop spending the next cycle on more release orchestration churn. The remaining structural debt is concentrated in the discovery-facing script libraries, so migrate that chain into a package-native `infinitas_skill.discovery` area, leave thin wrappers under `scripts/`, guard those wrappers with integration tests, and only then write the final scorecard from a fresh verification matrix.

**Tech Stack:** Python 3.11 package modules under `src/infinitas_skill`, existing `scripts/test-*.py` regression flows, `pytest` integration guards in `tests/integration`, Bash CLI wrappers, and Markdown docs under `docs/reference` and `docs/ops`.

---

## Preconditions

- Work in the current dirty repository state; do not reset unrelated files.
- Preserve the hard-cut posture: no legacy shim restoration, no new business logic added back into deleted script entrypoints.
- Use `@superpowers:test-driven-development` before each behavior change.
- Use `@superpowers:verification-before-completion` before each completion claim or commit.
- Keep the release/test changes from the current cycle intact while doing this migration.

### Task 1: Add failing thin-wrapper guards for the discovery chain

**Files:**
- Modify: `tests/integration/test_dev_workflow.py`
- Test: `tests/integration/test_dev_workflow.py`

**Step 1: Write the failing wrapper guard**

Extend `tests/integration/test_dev_workflow.py` with a new guard that proves these script libs must become thin wrappers:

- `scripts/ai_index_lib.py`
- `scripts/discovery_index_lib.py`
- `scripts/discovery_resolver_lib.py`
- `scripts/recommend_skill_lib.py`
- `scripts/explain_install_lib.py`

Use the same structural style as the existing installed-integrity wrapper guard.

Example shape:

```python
def test_discovery_script_libs_stay_thin_wrappers() -> None:
    expected_wrappers = {
        "scripts/ai_index_lib.py": "from infinitas_skill.discovery.ai_index import *",
        "scripts/discovery_index_lib.py": "from infinitas_skill.discovery.index import *",
        "scripts/discovery_resolver_lib.py": "from infinitas_skill.discovery.resolver import *",
        "scripts/recommend_skill_lib.py": "from infinitas_skill.discovery.recommendation import *",
        "scripts/explain_install_lib.py": "from infinitas_skill.discovery.install_explanation import *",
    }
```

Also add a few forbidden markers that would catch duplicated implementation staying behind.

**Step 2: Run the guard to verify it fails**

Run:

```bash
uv run python3 -m pytest tests/integration/test_dev_workflow.py -q
```

Expected: FAIL because the five script libs still contain real implementation.

**Step 3: Commit**

```bash
git add tests/integration/test_dev_workflow.py
git commit -m "test: guard discovery script wrappers"
```

### Task 2: Move AI index and discovery index logic into the package

**Files:**
- Create: `src/infinitas_skill/discovery/__init__.py`
- Create: `src/infinitas_skill/discovery/ai_index.py`
- Create: `src/infinitas_skill/discovery/index.py`
- Modify: `scripts/ai_index_lib.py`
- Modify: `scripts/discovery_index_lib.py`
- Modify: `scripts/test-ai-index.py`
- Modify: `scripts/test-discovery-index.py`
- Test: `tests/integration/test_dev_workflow.py`

**Step 1: Run the existing focused regressions first**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
```

Expected: PASS before refactor, so you have a baseline.

**Step 2: Move `ai_index` logic first**

Create `src/infinitas_skill/discovery/ai_index.py` and move the reusable logic from `scripts/ai_index_lib.py` there with minimal behavioral change.

Keep the script wrapper thin:

```python
from infinitas_skill.discovery.ai_index import *
```

Do not redesign the output schema during this step.

**Step 3: Move `discovery_index` logic next**

Create `src/infinitas_skill/discovery/index.py` and move the reusable logic from `scripts/discovery_index_lib.py` there.

Keep imports package-native; do not create new reverse dependencies from `src/` back into `scripts/`.

**Step 4: Re-run focused checks**

Run:

```bash
python3 scripts/test-ai-index.py
python3 scripts/test-discovery-index.py
uv run python3 -m pytest tests/integration/test_dev_workflow.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/infinitas_skill/discovery/__init__.py src/infinitas_skill/discovery/ai_index.py src/infinitas_skill/discovery/index.py scripts/ai_index_lib.py scripts/discovery_index_lib.py scripts/test-ai-index.py scripts/test-discovery-index.py tests/integration/test_dev_workflow.py
git commit -m "refactor: move discovery index builders into package"
```

### Task 3: Move resolver, recommendation, and install explanation into the package

**Files:**
- Create: `src/infinitas_skill/discovery/resolver.py`
- Create: `src/infinitas_skill/discovery/recommendation.py`
- Create: `src/infinitas_skill/discovery/install_explanation.py`
- Modify: `scripts/discovery_resolver_lib.py`
- Modify: `scripts/recommend_skill_lib.py`
- Modify: `scripts/explain_install_lib.py`
- Modify: `scripts/test-recommend-skill.py`
- Modify: `scripts/test-explain-install.py`
- Modify: `scripts/test-install-by-name.py`
- Modify: `scripts/test-skill-update.py`
- Test: `tests/integration/test_dev_workflow.py`

**Step 1: Baseline the current chain**

Run:

```bash
python3 scripts/test-recommend-skill.py
python3 scripts/test-explain-install.py
python3 scripts/test-install-by-name.py
python3 scripts/test-skill-update.py
```

Expected: PASS before refactor.

**Step 2: Move resolver logic**

Create `src/infinitas_skill/discovery/resolver.py` and move the reusable loader/selection logic from `scripts/discovery_resolver_lib.py`.

Keep the wrapper thin:

```python
from infinitas_skill.discovery.resolver import *
```

**Step 3: Move recommendation logic**

Create `src/infinitas_skill/discovery/recommendation.py` and move the scoring/reasoning helpers from `scripts/recommend_skill_lib.py`.

Keep ranking behavior stable; do not re-tune scores in this task unless a failing test proves it is necessary.

**Step 4: Move install explanation logic**

Create `src/infinitas_skill/discovery/install_explanation.py` and move the explanation helpers from `scripts/explain_install_lib.py`.

Keep the wrapper thin:

```python
from infinitas_skill.discovery.install_explanation import *
```

**Step 5: Re-run focused checks**

Run:

```bash
python3 scripts/test-recommend-skill.py
python3 scripts/test-explain-install.py
python3 scripts/test-install-by-name.py
python3 scripts/test-skill-update.py
uv run python3 -m pytest tests/integration/test_dev_workflow.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add src/infinitas_skill/discovery/resolver.py src/infinitas_skill/discovery/recommendation.py src/infinitas_skill/discovery/install_explanation.py scripts/discovery_resolver_lib.py scripts/recommend_skill_lib.py scripts/explain_install_lib.py scripts/test-recommend-skill.py scripts/test-explain-install.py scripts/test-install-by-name.py scripts/test-skill-update.py tests/integration/test_dev_workflow.py
git commit -m "refactor: move discovery recommendation chain into package"
```

### Task 4: Publish the final release-readiness scorecard

**Files:**
- Create: `docs/ops/2026-04-01-release-readiness-scorecard.md`
- Modify: `README.md`
- Modify: `docs/reference/testing.md`

**Step 1: Run the final verification matrix**

Run:

```bash
uv run python3 -m pytest tests/integration/test_dev_workflow.py tests/integration/test_cli_policy.py tests/integration/test_cli_release_state.py tests/integration/test_cli_install_planning.py -q
python3 scripts/test-transparency-log.py
python3 scripts/test-release-invariants.py
./scripts/check-all.sh release-long
python3 scripts/test-policy-pack-loading.py
python3 scripts/test-registry-refresh-policy.py
python3 scripts/test-registry-federation-rules.py
python3 scripts/test-hosted-registry-source.py
python3 scripts/test-installed-integrity-stale-guardrails.py
python3 scripts/test-installed-integrity-never-verified-guardrails.py
python3 scripts/test-installed-integrity-freshness.py
python3 scripts/test-installed-integrity-report.py
python3 scripts/test-installed-integrity-history-retention.py
make test-fast
```

Expected: PASS across the release-readiness matrix.

**Step 2: Write the scorecard**

Create `docs/ops/2026-04-01-release-readiness-scorecard.md` with:

- production-readiness score
- maintainability score
- cleanup-completion score
- exact evidence commands and status
- remaining non-blocking risks
- explicit go / no-go recommendation

Use a compact table like:

```markdown
| Category | Score | Evidence |
| --- | --- | --- |
| Release readiness | 9.6/10 | `python3 scripts/test-transparency-log.py`, `python3 scripts/test-release-invariants.py` |
```

**Step 3: Update entrypoint docs**

Update `README.md` and `docs/reference/testing.md` so maintainers can quickly find:

- canonical CLI
- `release-long` verification block
- scorecard location

**Step 4: Commit**

```bash
git add docs/ops/2026-04-01-release-readiness-scorecard.md README.md docs/reference/testing.md
git commit -m "docs: publish release readiness scorecard"
```

## Recommended execution order

1. Task 1
2. Task 2
3. Task 3
4. Task 4

## Definition of done

- The discovery/recommend/install-explanation chain lives in `src/infinitas_skill/discovery`.
- The corresponding `scripts/*_lib.py` files are thin wrappers only.
- `tests/integration/test_dev_workflow.py` guards those wrappers.
- The long release suite remains green after the migration.
- A fresh release-readiness scorecard is published with exact verification evidence.
