# Signer Bootstrap and Verified Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the stable release chain for `lvxiaoer/operate-infinitas-skill` actually usable by bootstrapping a trusted signer, unblocking the promotion gate for a solo-maintainer registry, and recording fresh compatibility evidence for Claude, Codex, and OpenClaw.

**Architecture:** Add one focused governance fallback for owner-authored skills when no distinct configured reviewer exists, add an evidence-recording helper that runs the real export/check pipeline per platform and writes `catalog/compatibility-evidence`, then use the existing review/publish/release scripts to produce a real immutable release and refresh generated catalogs.

**Tech Stack:** Bash release helpers, Python 3.11 governance/evidence scripts, SSH signing bootstrap, compatibility checkers, generated catalogs, and immutable distribution manifests under `catalog/distributions/`.

---

### Task 1: Lock the solo-maintainer review deadlock with a failing test

**Files:**
- Modify: `scripts/test-review-governance.py`
- Modify: `schemas/promotion-policy.schema.json`
- Modify: `policy/promotion-policy.json`

**Step 1: Write the failing test**

Add a scenario where:

- `reviews.reviewer_must_differ_from_owner` remains `true`
- `reviews.allow_owner_when_no_distinct_reviewer` is `true`
- the required reviewer group contains only the owner
- the owner requests review and approves the skill

Assert that `review-status.py <skill> --as-active --require-pass` succeeds only when the fallback is enabled.

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-review-governance.py
```

Expected: FAIL because the current governance logic always ignores owner reviews.

**Step 3: Implement the minimal policy fallback**

Update policy validation plus review evaluation so owner approvals are counted only when:

- `allow_owner_when_no_distinct_reviewer` is enabled
- the reviewer is the owner
- there is no configured non-owner reviewer available for the groups required by the evaluated stage/risk

Keep the existing stricter behavior for all other cases.

**Step 4: Re-run the test**

Run:

```bash
python3 scripts/test-review-governance.py
```

Expected: PASS.

### Task 2: Add a real compatibility-evidence recording command with a failing test

**Files:**
- Create: `scripts/record-verified-support.py`
- Create: `scripts/test-record-verified-support.py`
- Modify: `scripts/check-all.sh`

**Step 1: Write the failing integration test**

Create a temp-repo scenario that:

- scaffolds an active fixture skill
- bootstraps a real SSH signer inside the temp repo
- creates a signed immutable release
- runs a new `record-verified-support.py` command for `codex`, `claude`, and `openclaw`
- rebuilds the catalog

Assert:

- all three evidence files are created under `catalog/compatibility-evidence/`
- `catalog/compatibility.json` marks all three platforms as non-`unknown`
- `catalog/distributions.json` and `catalog/ai-index.json` contain the released skill

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-record-verified-support.py
```

Expected: FAIL because the command does not exist yet.

**Step 3: Implement the minimal recorder**

Implement `scripts/record-verified-support.py` so it:

- resolves the requested skill and version
- exports Codex and Claude bundles from the skill source into temp directories
- exports OpenClaw from the released immutable artifact
- runs `check-codex-compat.py`, `check-claude-compat.py`, and `check-openclaw-compat.py`
- writes evidence JSON with fresh timestamps and checker names
- optionally rebuilds the catalog

**Step 4: Re-run the test**

Run:

```bash
python3 scripts/test-record-verified-support.py
```

Expected: PASS.

### Task 3: Bootstrap the real signer and publish the real skill

**Files:**
- Modify: `config/allowed_signers`
- Modify: `skills/incubating/operate-infinitas-skill/reviews.json`
- Modify: generated release outputs under `catalog/`

**Step 1: Verify signer/bootstrap readiness**

Run:

```bash
python3 scripts/doctor-signing.py operate-infinitas-skill --identity lvxiaoer --json
```

Confirm the remaining blockers are exactly the missing trusted signer, missing signing key, and missing upstream/release artifacts.

**Step 2: Bootstrap the signer**

Run:

```bash
python3 scripts/bootstrap-signing.py init-key --identity lvxiaoer --output ~/.ssh/infinitas-skill-release-signing
python3 scripts/bootstrap-signing.py add-allowed-signer --identity lvxiaoer --key ~/.ssh/infinitas-skill-release-signing
python3 scripts/bootstrap-signing.py configure-git --key ~/.ssh/infinitas-skill-release-signing
python3 scripts/bootstrap-signing.py authorize-publisher --publisher lvxiaoer --signer lvxiaoer --releaser lvxiaoer
```

If the key already exists, skip `init-key` and reuse it.

**Step 3: Move the skill through the real promotion gate**

Run:

```bash
scripts/request-review.sh operate-infinitas-skill --note "Ready for stable release rehearsal"
scripts/approve-skill.sh operate-infinitas-skill --reviewer lvxiaoer --decision approved --note "Solo-maintainer fallback approval"
python3 scripts/review-status.py operate-infinitas-skill --as-active --require-pass
```

**Step 4: Create the actual immutable release**

Run:

```bash
git push -u origin codex/signer-bootstrap-evidence
scripts/publish-skill.sh operate-infinitas-skill
```

Expected:

- `skills/active/operate-infinitas-skill`
- `catalog/distributions/lvxiaoer/operate-infinitas-skill/0.1.0/manifest.json`
- `catalog/provenance/operate-infinitas-skill-0.1.0.json`
- non-empty `catalog/ai-index.json`

### Task 4: Record fresh verified support and re-verify the repo

**Files:**
- Create: `catalog/compatibility-evidence/codex/operate-infinitas-skill/0.1.0.json`
- Create: `catalog/compatibility-evidence/claude/operate-infinitas-skill/0.1.0.json`
- Create: `catalog/compatibility-evidence/openclaw/operate-infinitas-skill/0.1.0.json`
- Modify: `catalog/catalog.json`
- Modify: `catalog/compatibility.json`
- Modify: `catalog/distributions.json`
- Modify: `catalog/ai-index.json`

**Step 1: Run the real recorder on the published skill**

Run:

```bash
python3 scripts/record-verified-support.py operate-infinitas-skill --platform codex --platform claude --platform openclaw --build-catalog
```

**Step 2: Verify the compatibility catalog**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
catalog = json.loads(Path('catalog/compatibility.json').read_text(encoding='utf-8'))
entry = next(item for item in catalog['skills'] if item['name'] == 'operate-infinitas-skill')
assert entry['verified_support']['codex']['state'] != 'unknown'
assert entry['verified_support']['claude']['state'] != 'unknown'
assert entry['verified_support']['openclaw']['state'] != 'unknown'
PY
```

**Step 3: Run fresh verification before claiming completion**

Run:

```bash
./scripts/check-all.sh
python3 scripts/doctor-signing.py operate-infinitas-skill --identity lvxiaoer
```

Expected: full verification passes, and doctor output no longer reports signer/bootstrap blockers.
