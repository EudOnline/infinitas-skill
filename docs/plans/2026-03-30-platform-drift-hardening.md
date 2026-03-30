# Platform Drift Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make evolving Codex, Claude Code, and OpenClaw standards a first-class operational concern so stale platform assumptions fail early, stale compatibility evidence is visible to consumers, and stable releases cannot ship on expired platform claims.

**Architecture:** Reuse the current platform contracts, platform profiles, compatibility evidence, generated catalogs, and release policy traces. Add one shared platform-contract reader plus one repo-managed compatibility freshness policy, then thread freshness state through catalog build, discovery/recommendation, and release gating instead of treating any historical verification as permanently valid.

**Tech Stack:** Python 3 helper scripts, repo-managed JSON config, Bash catalog/release wrappers, generated `catalog/*.json`, existing compatibility and release regression tests.

---

### Task 1: Add a shared platform-contract reader and make stale docs fail in the real CI path

**Files:**
- Create: `scripts/platform_contract_lib.py`
- Modify: `scripts/check-platform-contracts.py`
- Modify: `scripts/test-platform-contracts.py`
- Modify: `scripts/check-all.sh`
- Test: `scripts/test-platform-contracts.py`

**Step 1: Write the failing test**

Extend `scripts/test-platform-contracts.py` with a stale-doc scenario that expects a non-zero exit when the checker is run with an explicit fail policy:

```python
result = run(
    [sys.executable, str(checker), "--max-age-days", "30", "--stale-policy", "fail"],
    cwd=stale_repo,
    expect=1,
)
```

Also keep the existing warning-only scenario so the checker proves both modes work.

**Step 2: Run test to verify it fails**

Run: `uv run python3 scripts/test-platform-contracts.py`
Expected: FAIL because `scripts/check-platform-contracts.py` does not yet accept `--stale-policy fail`.

**Step 3: Write the minimal implementation**

Create `scripts/platform_contract_lib.py` with helpers that:

- load `docs/platform-contracts/<platform>.md`
- parse `Stable assumptions`, `Volatile assumptions`, `Official sources`, and `Last verified`
- return normalized data for downstream checks

Update `scripts/check-platform-contracts.py` to:

- use the shared loader
- accept `--stale-policy warn|fail`
- convert stale docs into errors when `--stale-policy fail`

Update `scripts/check-all.sh` so the real registry verification path runs:

```bash
python3 scripts/check-platform-contracts.py --max-age-days 30 --stale-policy fail
```

instead of relying only on the test file.

**Step 4: Run test to verify it passes**

Run: `uv run python3 scripts/test-platform-contracts.py`
Expected: PASS with stale docs blocked only in fail mode.

Then run: `uv run bash scripts/check-all.sh`
Expected: PASS on a fresh repo, and a hard failure if any contract doc is older than 30 days.

**Step 5: Commit**

```bash
git add scripts/platform_contract_lib.py scripts/check-platform-contracts.py scripts/test-platform-contracts.py scripts/check-all.sh
git commit -m "feat: enforce fresh platform contract docs in ci"
```

### Task 2: Keep platform profile JSON and contract-watch docs synchronized

**Files:**
- Modify: `scripts/platform_contract_lib.py`
- Modify: `scripts/check-platform-contracts.py`
- Modify: `scripts/test-platform-contracts.py`
- Modify: `scripts/test-canonical-contracts.py`
- Modify: `profiles/codex.json`
- Modify: `profiles/claude.json`
- Modify: `profiles/openclaw.json`
- Test: `scripts/test-platform-contracts.py`
- Test: `scripts/test-canonical-contracts.py`

**Step 1: Write the failing test**

Add a mismatch case to `scripts/test-platform-contracts.py` that writes a contract doc with one `Last verified` date and a profile with a different `contract.last_verified`, then expects the checker to fail.

Add a canonical-contract assertion that profile `contract.sources` and `contract.last_verified` must stay parseable and non-empty.

**Step 2: Run tests to verify they fail**

Run: `uv run python3 scripts/test-platform-contracts.py`
Expected: FAIL because the checker does not yet compare docs against `profiles/*.json`.

Run: `uv run python3 scripts/test-canonical-contracts.py`
Expected: PASS before the new assertion is added, then FAIL after the assertion is added.

**Step 3: Write the minimal implementation**

Extend the shared loader so it can also compare parsed doc metadata to `profiles/<platform>.json`:

- `contract.sources` must match the doc `Official sources`
- `contract.last_verified` must match the doc `Last verified`

Keep `profiles/*.json` as the machine-readable mirror of the docs, but make the checker fail when they drift.

**Step 4: Run tests to verify they pass**

Run: `uv run python3 scripts/test-platform-contracts.py`
Expected: PASS with matching docs and profiles.

Run: `uv run python3 scripts/test-canonical-contracts.py`
Expected: PASS with the synchronized profile metadata.

**Step 5: Commit**

```bash
git add scripts/platform_contract_lib.py scripts/check-platform-contracts.py scripts/test-platform-contracts.py scripts/test-canonical-contracts.py profiles/codex.json profiles/claude.json profiles/openclaw.json
git commit -m "feat: sync platform profiles with contract watch docs"
```

### Task 3: Add compatibility-evidence freshness policy and stale-state derivation

**Files:**
- Create: `config/compatibility-policy.json`
- Create: `scripts/compatibility_policy_lib.py`
- Modify: `scripts/compatibility_evidence_lib.py`
- Modify: `scripts/build-catalog.sh`
- Modify: `scripts/test-compatibility-evidence.py`
- Modify: `scripts/test-record-verified-support.py`
- Modify: `docs/compatibility-matrix.md`
- Modify: `docs/compatibility-contract.md`
- Test: `scripts/test-compatibility-evidence.py`
- Test: `scripts/test-record-verified-support.py`

**Step 1: Write the failing test**

Extend `scripts/test-compatibility-evidence.py` with at least two scenarios:

```python
if verified["codex"].get("freshness_state") != "stale":
    fail("expected codex evidence to become stale when contract.last_verified is newer than checked_at")
```

```python
if verified["openclaw"].get("freshness_state") != "fresh":
    fail("expected fresh evidence for recent openclaw verification")
```

Use one fixture where `checked_at` is older than the policy window or older than the platform contract `last_verified`.

**Step 2: Run tests to verify they fail**

Run: `uv run python3 scripts/test-compatibility-evidence.py`
Expected: FAIL because `verified_support` currently exposes only `state`, `checked_at`, `checker`, and `evidence_path`.

**Step 3: Write the minimal implementation**

Add `config/compatibility-policy.json` with a repo-managed freshness policy, for example:

```json
{
  "platform_contracts": {
    "max_age_days": 30,
    "stale_policy": "fail"
  },
  "verified_support": {
    "stale_after_days": 30,
    "contract_newer_than_evidence_policy": "stale",
    "missing_policy": "unknown"
  }
}
```

Create `scripts/compatibility_policy_lib.py` to load and validate that config.

Update `scripts/compatibility_evidence_lib.py` so `merge_declared_and_verified_support()` computes additive freshness metadata per platform:

- `freshness_state`: `fresh|stale|unknown`
- `freshness_reason`: `age-expired|contract-newer-than-evidence|missing-evidence|not-applicable`
- `contract_last_verified`
- `fresh_until` when derivable from policy

Do not overwrite the existing compatibility verdict in `state`; keep functional compatibility and freshness as separate fields.

Update `scripts/build-catalog.sh` to load the compatibility policy and feed it into the merge path.

**Step 4: Run tests to verify they pass**

Run: `uv run python3 scripts/test-compatibility-evidence.py`
Expected: PASS with `freshness_state` surfaced in `catalog/compatibility.json`.

Run: `uv run python3 scripts/test-record-verified-support.py`
Expected: PASS with newly recorded evidence marked `fresh`.

**Step 5: Commit**

```bash
git add config/compatibility-policy.json scripts/compatibility_policy_lib.py scripts/compatibility_evidence_lib.py scripts/build-catalog.sh scripts/test-compatibility-evidence.py scripts/test-record-verified-support.py docs/compatibility-matrix.md docs/compatibility-contract.md
git commit -m "feat: add freshness policy for verified platform support"
```

### Task 4: Teach AI, discovery, search, and recommendation surfaces to consume freshness instead of any historical evidence

**Files:**
- Modify: `scripts/ai_index_lib.py`
- Modify: `scripts/discovery_index_lib.py`
- Modify: `scripts/recommend_skill_lib.py`
- Modify: `scripts/search_inspect_lib.py`
- Modify: `scripts/test-ai-index.py`
- Modify: `scripts/test-discovery-index.py`
- Modify: `scripts/test-recommend-skill.py`
- Modify: `scripts/test-search-docs.py`
- Test: `scripts/test-ai-index.py`
- Test: `scripts/test-discovery-index.py`
- Test: `scripts/test-recommend-skill.py`

**Step 1: Write the failing test**

Add a recommendation test where two skills both declare Codex support, but only one has fresh verified Codex evidence. The winner should be the fresh one.

Add an AI/discovery index assertion that freshness metadata is preserved end-to-end:

```python
if first["verified_support"]["codex"].get("freshness_state") != "fresh":
    fail("expected codex freshness_state to survive ai/discovery export")
```

**Step 2: Run tests to verify they fail**

Run: `uv run python3 scripts/test-ai-index.py`
Expected: FAIL because freshness fields are not yet part of the exported payload.

Run: `uv run python3 scripts/test-recommend-skill.py`
Expected: FAIL because recommendation still treats `agent_compatible` as the main compatibility signal.

**Step 3: Write the minimal implementation**

Update the consumers so they distinguish:

- fresh verified support
- stale verified support
- declared-only support
- explicit unsupported/broken support

Concrete changes:

- `scripts/ai_index_lib.py`: preserve freshness metadata and compute `last_verified_at` from fresh or stale evidence without discarding the reason fields
- `scripts/discovery_index_lib.py`: keep freshness metadata in the normalized skill view
- `scripts/search_inspect_lib.py`: expose both compatibility state and freshness summary in inspect/search responses
- `scripts/recommend_skill_lib.py`: rank fresh verified support above declared-only support, and stale verified support below fresh verified support

Keep the change additive so existing consumers that only read `verified_support.<platform>.state` still work.

**Step 4: Run tests to verify they pass**

Run: `uv run python3 scripts/test-ai-index.py`
Expected: PASS with freshness metadata in the AI index.

Run: `uv run python3 scripts/test-discovery-index.py`
Expected: PASS with freshness metadata preserved in discovery output.

Run: `uv run python3 scripts/test-recommend-skill.py`
Expected: PASS with fresh verified compatibility outranking stale or declared-only claims.

**Step 5: Commit**

```bash
git add scripts/ai_index_lib.py scripts/discovery_index_lib.py scripts/recommend_skill_lib.py scripts/search_inspect_lib.py scripts/test-ai-index.py scripts/test-discovery-index.py scripts/test-recommend-skill.py scripts/test-search-docs.py
git commit -m "feat: rank skills using fresh verified compatibility"
```

### Task 5: Block stable releases when required platform evidence is stale, unknown, or contradictory

**Files:**
- Modify: `scripts/release_lib.py`
- Modify: `scripts/check-release-state.py`
- Modify: `scripts/release-skill.sh`
- Modify: `scripts/test-release-invariants.py`
- Modify: `docs/release-checklist.md`
- Modify: `README.md`
- Test: `scripts/test-release-invariants.py`

**Step 1: Write the failing test**

Add a release fixture scenario where:

- `_meta.json.agent_compatible` claims `["codex", "claude"]`
- Codex evidence is stale
- Claude evidence is missing

Then assert `check-release-state.py --mode preflight` fails with a blocking rule that mentions platform freshness.

Example assertion:

```python
assert_contains(combined, "platform verified support is stale or missing", "platform freshness release error")
```

**Step 2: Run test to verify it fails**

Run: `uv run python3 scripts/test-release-invariants.py`
Expected: FAIL because release readiness does not currently inspect compatibility evidence freshness.

**Step 3: Write the minimal implementation**

Update `scripts/release_lib.py` so `collect_release_state()`:

- loads the merged compatibility view for the target skill/version
- evaluates required platforms from `declared_support` first
- blocks `preflight` and `stable-release` when required platforms are `unknown`, `stale`, `blocked`, `broken`, or `unsupported`
- adds a `platform-verified-support` rule to `policy_trace`

Keep `scripts/check-release-state.py` as the thin CLI wrapper.

Update `scripts/release-skill.sh` only if the release summary needs to print the new policy block more clearly; do not duplicate the policy logic there.

**Step 4: Run test to verify it passes**

Run: `uv run python3 scripts/test-release-invariants.py`
Expected: PASS with release blocked for stale or missing platform evidence, and policy trace output showing which platform caused the denial.

**Step 5: Commit**

```bash
git add scripts/release_lib.py scripts/check-release-state.py scripts/release-skill.sh scripts/test-release-invariants.py docs/release-checklist.md README.md
git commit -m "feat: gate stable releases on fresh platform evidence"
```

### Task 6: Write the operator playbook for upstream platform drift

**Files:**
- Create: `docs/platform-drift-playbook.md`
- Modify: `README.md`
- Modify: `docs/compatibility-matrix.md`
- Modify: `docs/release-checklist.md`
- Test: `uv run bash scripts/check-all.sh`

**Step 1: Write the doc skeleton**

Create `docs/platform-drift-playbook.md` with these sections:

- how to verify upstream docs
- how to update `docs/platform-contracts/*.md`
- how to sync `profiles/*.json`
- how to rerun `scripts/record-verified-support.py`
- how to interpret stale evidence in discovery and release flows

**Step 2: Update entrypoint docs**

Add short links from:

- `README.md`
- `docs/compatibility-matrix.md`
- `docs/release-checklist.md`

so maintainers know the playbook exists.

**Step 3: Run the full verification pass**

Run: `uv run bash scripts/check-all.sh`
Expected: PASS with:

- direct platform contract freshness enforcement
- synchronized profile/doc metadata
- freshness-aware compatibility catalogs
- release invariant coverage for stale platform evidence

**Step 4: Record the expected maintenance loop**

Document the steady-state procedure as:

1. refresh upstream contract docs
2. sync `profiles/*.json`
3. rerun `python3 scripts/record-verified-support.py <skill> --platform ... --build-catalog`
4. run `uv run bash scripts/check-all.sh`
5. ship only after `check-release-state.py` is clean

**Step 5: Commit**

```bash
git add docs/platform-drift-playbook.md README.md docs/compatibility-matrix.md docs/release-checklist.md
git commit -m "docs: add platform drift response playbook"
```

## Final Verification

After all tasks land, run:

```bash
uv run python3 scripts/test-platform-contracts.py
uv run python3 scripts/test-canonical-contracts.py
uv run python3 scripts/test-compatibility-evidence.py
uv run python3 scripts/test-record-verified-support.py
uv run python3 scripts/test-ai-index.py
uv run python3 scripts/test-discovery-index.py
uv run python3 scripts/test-recommend-skill.py
uv run python3 scripts/test-release-invariants.py
uv run bash scripts/check-all.sh
```

Expected: all checks pass, stale platform docs fail in CI, stale evidence is visible in generated indexes, and stable release readiness fails when required platform verification is no longer fresh.
