# Supply-Chain Transparency And Reproducible Release Metadata Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Strengthen stable-release trust by extending signed release artifacts with deterministic full-file manifests and reproducible build metadata, then publish those attestations to an external transparency log in an additive, policy-driven way.

**Architecture:** Keep the release path Git-native and offline-verifiable by extending existing provenance and distribution manifests rather than inventing a parallel artifact format. First make the signed attestation commit to a richer released-file inventory and normalized build context, then add transparency-log publication as an optional or enforceable second trust layer whose proofs are recorded back into repo-managed artifacts.

**Tech Stack:** Existing Bash and Python 3.11 CLI tooling, JSON schemas and policy files, `scripts/release-skill.sh`, `scripts/generate-provenance.py`, `scripts/provenance_payload_lib.py`, `scripts/distribution_lib.py`, `scripts/attestation_lib.py`, and Markdown operator docs.

---

### Task 1: Define failing reproducibility tests and extend the signed artifact contract

**Files:**
- Create: `scripts/test-release-reproducibility.py`
- Modify: `schemas/provenance.schema.json`
- Modify: `schemas/distribution-manifest.schema.json`
- Modify: `scripts/provenance_payload_lib.py`
- Modify: `scripts/distribution_lib.py`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/release-strategy.md`

**Step 1: Write the failing test**

Create `scripts/test-release-reproducibility.py` with fixture scenarios that:

- release one active fixture skill into a temp repo using the existing release helper path
- assert the generated provenance and distribution manifest now expose:
  - a deterministic `file_manifest` or equivalent released-file inventory
  - per-file relative paths and SHA-256 digests
  - normalized build metadata such as archive format, archive timestamp normalization, and builder/tool summary
- assert verification fails when one archived file is changed after the file manifest was generated

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-release-reproducibility.py
```

Expected: FAIL because current provenance and distribution artifacts do not yet include full-file inventory or reproducibility metadata.

**Step 3: Implement the minimal signed metadata contract**

Extend the existing provenance and distribution payload builders so they can:

- collect a deterministic list of released files from the archived skill tree
- record path, digest, and stable archive metadata for each file
- capture normalized build metadata that matters for reproducibility without leaking noisy local state
- validate the new additive fields through the existing JSON schemas

Keep the first pass additive so old consumers can ignore the new fields while new verification logic can start relying on them.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-release-reproducibility.py
python3 scripts/test-release-invariants.py
```

Expected: PASS.

### Task 2: Enforce the new reproducibility metadata in release and distribution verification

**Files:**
- Modify: `scripts/test-release-reproducibility.py`
- Modify: `scripts/generate-provenance.py`
- Modify: `scripts/release-skill.sh`
- Modify: `scripts/verify-attestation.py`
- Modify: `scripts/attestation_lib.py`
- Modify: `scripts/distribution_lib.py`
- Modify: `scripts/check-release-state.py`
- Modify: `scripts/build-catalog.sh`
- Modify: `scripts/release_lib.py`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/release-strategy.md`

**Step 1: Extend the failing test**

Add scenarios that:

- assert `scripts/verify-attestation.py --json` exposes the new reproducibility metadata
- assert `python3 scripts/check-release-state.py <skill> --json` reports whether the richer signed artifact set is present and internally consistent
- assert catalog or release exports preserve the additive reproducibility summary for downstream audit tooling

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-release-reproducibility.py
```

Expected: FAIL because verification and reporting surfaces do not yet consume the new metadata.

**Step 3: Implement verification and reporting**

Update the existing verification path so it:

- checks bundle contents against the signed file manifest, not only top-level bundle digest
- reports reproducibility metadata through attestation verification and release-state JSON
- keeps catalog or audit summaries additive and machine-readable

Do not introduce a second verification stack; extend the current attestation and distribution verification path instead.

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-release-reproducibility.py
python3 scripts/test-attestation-verification.py
python3 scripts/test-release-invariants.py
```

Expected: PASS.

### Task 3: Add failing transparency-log publication tests and policy contract

**Files:**
- Create: `scripts/test-transparency-log.py`
- Create: `scripts/transparency_log_lib.py`
- Create: `schemas/transparency-log-entry.schema.json`
- Modify: `schemas/signing.schema.json`
- Modify: `config/signing.json`
- Modify: `scripts/attestation_lib.py`
- Modify: `docs/signing-operations.md`
- Modify: `docs/release-strategy.md`

**Step 1: Write the failing test**

Create `scripts/test-transparency-log.py` with fixture scenarios that:

- start a local fake transparency-log HTTP endpoint
- assert one signed attestation can be submitted and returns a stable log-entry record
- assert policy can distinguish advisory from required transparency publication
- assert missing endpoint, malformed response, or proof mismatch fails clearly

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-transparency-log.py
```

Expected: FAIL because no transparency-log config, client, or proof-record contract exists yet.

**Step 3: Implement the minimal transparency policy and record contract**

Add a focused transparency helper that can:

- load transparency-log settings from the existing signing policy surface
- submit the attestation digest and signed payload metadata to a configured endpoint
- normalize the returned entry id, log index, integrated timestamp, and proof fields into a stable JSON record
- keep publication additive so offline release verification still works when transparency is advisory

**Step 4: Re-run focused verification**

Run:

```bash
python3 scripts/test-transparency-log.py
python3 scripts/test-attestation-verification.py
```

Expected: PASS.

### Task 4: Wire transparency publication into release flows, verification, and docs

**Files:**
- Modify: `scripts/test-transparency-log.py`
- Modify: `scripts/release-skill.sh`
- Modify: `scripts/generate-provenance.py`
- Modify: `scripts/provenance_payload_lib.py`
- Modify: `scripts/verify-attestation.py`
- Modify: `scripts/attestation_lib.py`
- Modify: `scripts/check-release-state.py`
- Modify: `scripts/release_lib.py`
- Modify: `scripts/build-catalog.sh`
- Modify: `docs/distribution-manifests.md`
- Modify: `docs/release-strategy.md`
- Modify: `docs/signing-operations.md`
- Modify: `docs/ai/agent-operations.md`

**Step 1: Extend the failing test**

Add scenarios that:

- release one fixture with transparency publication enabled and assert provenance records the transparency proof data
- assert `check-release-state --json`, catalog outputs, or other audit-facing surfaces preserve the proof summary
- assert required transparency mode blocks release output when submission or proof verification fails

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-transparency-log.py
```

Expected: FAIL because release flows do not yet call the transparency client or surface its proofs.

**Step 3: Implement additive publication and proof verification**

Thread transparency publication through the release path so operators can:

- write provenance
- optionally or mandatorily publish it to the configured transparency log
- persist the returned proof record in repo-managed artifacts
- verify those proofs later without replacing the current SSH and CI trust paths

Update docs so operators know when transparency is advisory, when it is required, and what to do if the external service is unavailable.

**Step 4: Re-run targeted verification**

Run:

```bash
python3 scripts/test-release-reproducibility.py
python3 scripts/test-transparency-log.py
python3 scripts/test-attestation-verification.py
python3 scripts/test-release-invariants.py
```

Expected: PASS.

### Task 5: Run full verification and capture the v15 planning start commit

**Files:**
- Modify: any files changed above

**Step 1: Run targeted checks**

Run:

```bash
python3 scripts/test-release-reproducibility.py
python3 scripts/test-transparency-log.py
python3 scripts/test-attestation-verification.py
python3 scripts/test-release-invariants.py
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
git add .planning/PROJECT.md .planning/REQUIREMENTS.md .planning/ROADMAP.md .planning/STATE.md docs/plans/2026-03-17-supply-chain-transparency-and-reproducible-release-metadata.md scripts/test-release-reproducibility.py scripts/test-transparency-log.py scripts/transparency_log_lib.py schemas/transparency-log-entry.schema.json schemas/provenance.schema.json schemas/distribution-manifest.schema.json schemas/signing.schema.json config/signing.json scripts/provenance_payload_lib.py scripts/distribution_lib.py scripts/generate-provenance.py scripts/release-skill.sh scripts/verify-attestation.py scripts/attestation_lib.py scripts/check-release-state.py scripts/release_lib.py scripts/build-catalog.sh docs/distribution-manifests.md docs/release-strategy.md docs/signing-operations.md docs/ai/agent-operations.md
git commit -m "docs: plan v15 supply-chain transparency"
```
