# Maintained Surface Hard Cut Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove legacy-maintenance entrypoints so the repository exposes one maintained CLI surface, one maintained docs IA, and no unsupported operator shims.

**Architecture:** Add package-owned discovery CLI commands under `infinitas`, re-point maintained documentation and skills to those commands, and delete operator scripts that maintained docs already classify as removed. Keep this slice narrowly focused on maintained-surface consolidation rather than preserving wrapper compatibility.

**Tech Stack:** Python 3.11, argparse CLI, pytest, repository markdown docs

---

### Task 1: Add failing integration coverage for maintained discovery CLI

**Files:**
- Create: `tests/integration/test_cli_discovery.py`
- Modify: `tests/integration/test_doc_governance.py`

**Step 1: Write the failing test**

Add integration coverage that runs:

```bash
python -m infinitas_skill.cli.main discovery search operate --json
python -m infinitas_skill.cli.main discovery recommend "Need repo operations" --target-agent codex --json
python -m infinitas_skill.cli.main discovery inspect lvxiaoer/operate-infinitas-skill --json
```

and asserts:

- the command returns `0`
- search emits a `results` list
- recommend emits ranked `results`
- inspect emits `runtime` and trust/distribution detail

Add a doc-governance expectation that `docs/README.md` no longer indexes `docs/ai/README.md`.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/integration/test_cli_discovery.py tests/integration/test_doc_governance.py -q
```

Expected: FAIL because `infinitas` has no `discovery` command and docs still index the legacy AI landing.

**Step 3: Write minimal implementation**

Implement a package-owned discovery CLI module and wire it into `src/infinitas_skill/cli/main.py`.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/integration/test_cli_discovery.py tests/integration/test_doc_governance.py -q
```

Expected: PASS

### Task 2: Cut maintained docs and skill entrypoints over to `infinitas`

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/cli-reference.md`
- Modify: `skills/active/consume-infinitas-skill/SKILL.md`
- Modify: `skills/active/consume-infinitas-skill/tests/smoke.md`
- Modify: `skills/active/federation-registry-ops/SKILL.md`
- Modify: `skills/active/federation-registry-ops/tests/smoke.md`
- Modify: `server/static/js/app.js`
- Modify: `scripts/test-doc-governance.py`
- Modify: `scripts/test-search-docs.py`
- Modify: `scripts/test-recommend-docs.py`

**Step 1: Write the failing test**

Update or add assertions so maintained docs/skills no longer advertise:

- `scripts/search-skills.sh`
- `scripts/recommend-skill.sh`
- `scripts/inspect-skill.sh`

and instead advertise:

- `uv run infinitas discovery search`
- `uv run infinitas discovery recommend`
- `uv run infinitas discovery inspect`

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/integration/test_doc_governance.py -q
python3 scripts/test-doc-governance.py
python3 scripts/test-search-docs.py
python3 scripts/test-recommend-docs.py
python3 scripts/test-infinitas-cli-reference-docs.py
```

Expected: FAIL before docs and generated CLI reference are updated.

**Step 3: Write minimal implementation**

Rewrite maintained docs and skill instructions to point only at the maintained CLI surface. Remove the AI legacy landing from the maintained docs map. Regenerate `docs/reference/cli-reference.md` from the argparse tree.

**Step 4: Run test to verify it passes**

Run the same commands and confirm they pass.

### Task 3: Delete unsupported operator shims and verify the maintained fast path

**Files:**
- Delete: `scripts/request-review.sh`
- Delete: `scripts/approve-skill.sh`

**Step 1: Write the failing test**

Add or update a governance assertion that these unsupported operator scripts do not exist.

**Step 2: Run test to verify it fails**

Run:

```bash
python3 scripts/test-doc-governance.py
```

Expected: FAIL while the deleted-shim assertion is present but the files still exist.

**Step 3: Write minimal implementation**

Delete the retired scripts and any maintained references to them.

**Step 4: Run test to verify it passes**

Run:

```bash
python3 scripts/test-doc-governance.py
make lint-maintained
uv run pytest tests/integration/test_cli_discovery.py tests/integration/test_doc_governance.py tests/integration/test_cli_install_planning.py -q
```

Expected: PASS, proving the maintained surface is narrower and still functional.
