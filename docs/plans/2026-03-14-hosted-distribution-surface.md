# Hosted Distribution Surface Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose a real hosted distribution surface from the running server so another machine can discover and install immutable skills over HTTP without cloning the repository or depending on a separate ad hoc static file server.

**Architecture:** Keep the existing immutable-artifact and signed-manifest flow unchanged. Extend `server/artifact_ops.py` so each publish sync materializes a protocol-shaped artifact root with top-level indexes plus canonical `skills/` and `provenance/` paths, while preserving the existing `catalog/` mirror. Then mount that artifact root read-only from `server.app` under `/registry`, and switch the no-clone end-to-end coverage to install through the real hosted app instead of a throwaway `http.server` fixture.

**Tech Stack:** Python 3.11+, FastAPI/Starlette `StaticFiles`, existing hosted install/distribution helpers, existing worker publish flow, stdlib `tempfile`, `subprocess`, `urllib.request`, and script-style regression tests.

**Execution Notes:** Before implementation, create a dedicated worktree/branch such as `codex/hosted-distribution-surface` with @superpowers:using-git-worktrees. Follow @superpowers:test-driven-development for each behavior change, and use @superpowers:verification-before-completion before any “done/passing” claim.

---

### Task 1: Add failing artifact-layout coverage

**Files:**
- Create: `scripts/test-hosted-artifact-layout.py`
- Reference: `server/artifact_ops.py:7`
- Reference: `docs/ai/hosted-registry.md:26`

**Step 1: Write the failing test**

Create `scripts/test-hosted-artifact-layout.py` with one focused scenario that:

- creates a temp artifact root
- calls `sync_catalog_artifacts(ROOT, artifact_root)`
- asserts all of these exist after sync:
  - `artifact_root / 'ai-index.json'`
  - `artifact_root / 'distributions.json'`
  - `artifact_root / 'compatibility.json'`
  - `artifact_root / 'catalog' / ...` (existing mirror still present)
  - `artifact_root / 'skills' / 'lvxiaoer' / 'operate-infinitas-skill' / '0.1.1' / 'manifest.json'`
  - `artifact_root / 'skills' / 'lvxiaoer' / 'operate-infinitas-skill' / '0.1.1' / 'skill.tar.gz'`
  - `artifact_root / 'provenance' / 'operate-infinitas-skill-0.1.1.json'`
  - `artifact_root / 'provenance' / 'operate-infinitas-skill-0.1.1.json.ssig'`
- optionally parses the copied `ai-index.json` and verifies it still contains `lvxiaoer/operate-infinitas-skill`

Use a simple script-style assertion pattern consistent with the existing hosted tests:

```python
sync_catalog_artifacts(ROOT, artifact_root)
required = [
    artifact_root / 'distributions.json',
    artifact_root / 'compatibility.json',
    artifact_root / 'skills' / 'lvxiaoer' / 'operate-infinitas-skill' / '0.1.1' / 'manifest.json',
]
for path in required:
    if not path.exists():
        fail(f'missing hosted artifact surface file: {path}')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-artifact-layout.py
```

Expected: FAIL because `sync_catalog_artifacts()` currently copies only `catalog/`, `ai-index.json`, and `discovery-index.json`.

**Step 3: Commit**

```bash
git add scripts/test-hosted-artifact-layout.py
git commit -m "test: add hosted artifact layout coverage"
```

### Task 2: Materialize the hosted distribution root

**Files:**
- Modify: `server/artifact_ops.py:7`
- Modify: `scripts/test-hosted-artifact-layout.py`
- Reference: `catalog/distributions/`
- Reference: `catalog/provenance/`

**Step 1: Write the minimal implementation**

Extend `sync_catalog_artifacts()` so it still mirrors `catalog/`, but also materializes the protocol-facing root layout:

- copy root indexes:
  - `catalog/ai-index.json` → `artifact_root/ai-index.json`
  - `catalog/distributions.json` → `artifact_root/distributions.json`
  - `catalog/compatibility.json` → `artifact_root/compatibility.json`
  - keep `catalog/discovery-index.json` → `artifact_root/discovery-index.json` when present
- create a clean `artifact_root/skills/` tree from `catalog/distributions/<publisher>/<skill>/<version>/`
- create a clean `artifact_root/provenance/` tree from `catalog/provenance/`
- ensure the sync is deterministic and removes stale protocol-surface files before recopying

Keep it file-first and boring. Do not redesign manifest generation; only reshape already-generated immutable artifacts into a served layout.

The helper can stay in one file with small private functions, for example:

```python
def _copy_if_exists(source: Path, target: Path):
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
```

**Step 2: Run the focused test to verify it passes**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-artifact-layout.py
```

Expected: PASS.

**Step 3: Commit**

```bash
git add server/artifact_ops.py scripts/test-hosted-artifact-layout.py
git commit -m "feat: materialize hosted artifact surface"
```

### Task 3: Add failing app-served distribution coverage

**Files:**
- Modify: `scripts/test-hosted-api.py:15`
- Modify: `scripts/test-hosted-registry-e2e.py:192`
- Reference: `server/app.py:22`
- Reference: `docs/ai/hosted-registry.md:26`

**Step 1: Extend the hosted API smoke test**

Update `scripts/test-hosted-api.py` so it:

- creates a temp artifact root
- populates it with `sync_catalog_artifacts(ROOT, artifact_root)`
- sets `INFINITAS_SERVER_ARTIFACT_PATH`
- asserts these routes return `200` from the app:
  - `GET /registry/ai-index.json`
  - `GET /registry/distributions.json`
  - `GET /registry/compatibility.json`
  - `GET /registry/skills/lvxiaoer/operate-infinitas-skill/0.1.1/manifest.json`

The JSON endpoint assertion can stay minimal:

```python
response = client.get('/registry/ai-index.json')
if response.status_code != 200:
    fail(f'/registry/ai-index.json returned {response.status_code}: {response.text}')
```

**Step 2: Move the end-to-end hosted install test onto the real app**

Update `scripts/test-hosted-registry-e2e.py` so the final install no longer uses `HostedArtifactServer` with `http.server`.

Instead:

- add a small helper that starts the real hosted app via `uvicorn server.app:app --host 127.0.0.1 --port <free-port>`
- poll `/healthz` until ready
- configure the hosted registry source with `base_url = http://127.0.0.1:<port>/registry`
- keep the rest of the publish/install flow unchanged

This preserves the existing end-to-end publish path while proving that the real app exposes the hosted distribution surface.

**Step 3: Run the tests to verify they fail**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-api.py
python scripts/test-hosted-registry-e2e.py
```

Expected: FAIL with `404` or “missing AI index” errors because the app does not yet serve `/registry/*`.

**Step 4: Commit**

```bash
git add scripts/test-hosted-api.py scripts/test-hosted-registry-e2e.py
git commit -m "test: cover app-served hosted distribution"
```

### Task 4: Serve registry artifacts from the hosted app

**Files:**
- Modify: `server/app.py:3`
- Modify: `scripts/test-hosted-api.py`
- Modify: `scripts/test-hosted-registry-e2e.py`
- Optional: `server/settings.py:27` only if a small new setting is genuinely required

**Step 1: Write the minimal implementation**

Mount the artifact root read-only under `/registry` in `server.app` using `StaticFiles`.

Recommended minimal shape:

```python
from fastapi.staticfiles import StaticFiles

app.mount(
    '/registry',
    StaticFiles(directory=str(settings.artifact_path), check_dir=False),
    name='hosted-registry',
)
```

Guidelines:

- keep `/healthz`, `/`, `/login`, and `/api/v1/*` unchanged
- do not add mutable install behavior; this is read-only hosted distribution
- do not move artifact generation into request time; the served directory must stay publish-synced filesystem state
- avoid introducing extra auth knobs in this slice unless the tests truly require them

**Step 2: Run the focused tests to verify they pass**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-api.py
python scripts/test-hosted-registry-e2e.py
```

Expected: PASS.

**Step 3: Run adjacent hosted distribution checks**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-artifact-layout.py
python scripts/test-hosted-registry-source.py
python scripts/test-hosted-registry-install.py
```

Expected: PASS.

**Step 4: Commit**

```bash
git add server/app.py scripts/test-hosted-api.py scripts/test-hosted-registry-e2e.py scripts/test-hosted-artifact-layout.py
git commit -m "feat: serve hosted registry artifacts"
```

### Task 5: Document the served distribution surface and run final verification

**Files:**
- Modify: `docs/ai/hosted-registry.md:26`
- Modify: `docs/ai/server-api.md:1`
- Modify: `docs/ops/server-deployment.md:1`
- Modify: `README.md:218`

**Step 1: Update protocol and operator docs**

Document:

- that the hosted app serves immutable registry artifacts from `/registry`
- that registry clients should point `base_url` at that prefix, e.g. `https://skills.example.com/registry`
- that the served surface includes:
  - top-level indexes
  - canonical `skills/<publisher>/<skill>/<version>/...`
  - `provenance/<skill>-<version>.json(.ssig)`
- that the on-disk artifact root remains filesystem-backed and publish-synced

Also update operator-facing examples in `README.md` and `docs/ops/server-deployment.md` so reverse-proxy examples clearly preserve `/registry/*`.

**Step 2: Run the final verification bundle**

Run:

```bash
source /tmp/infinitas-hosted-registry-venv/bin/activate
python scripts/test-hosted-artifact-layout.py
python scripts/test-hosted-api.py
python scripts/test-hosted-registry-source.py
python scripts/test-hosted-registry-install.py
python scripts/test-hosted-registry-e2e.py
python scripts/test-worker-publish.py
python scripts/test-hosted-publish-hooks.py
git diff --check
git status --short
```

Expected: all checks pass and only intentional tracked changes remain.

If tests create `.state/`, clean it before the final `git status --short`.

**Step 3: Commit**

```bash
git add docs/ai/hosted-registry.md docs/ai/server-api.md docs/ops/server-deployment.md README.md
git commit -m "docs: describe hosted distribution surface"
```

### Task 6: Final batch commit

**Files:**
- Modify: none expected

**Step 1: Squash or keep the task commits**

If following the frequent-commit flow above, keep the commit history as-is unless the human asks for squashing.

If a single final commit is preferred instead, use:

```bash
git add server/app.py server/artifact_ops.py scripts/test-hosted-artifact-layout.py scripts/test-hosted-api.py scripts/test-hosted-registry-e2e.py docs/ai/hosted-registry.md docs/ai/server-api.md docs/ops/server-deployment.md README.md
git commit -m "feat: serve hosted distribution surface"
```

**Step 2: Hand off with evidence**

Before claiming success, include:

- the exact verification commands run
- the pass/fail outcome
- the new hosted base URL shape (`/registry`)
- any intentionally deferred work, especially artifact auth hardening or richer cache/proxy controls
