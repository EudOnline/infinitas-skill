# Federation Operations Guide

This guide explains how to reason about federation trust boundaries, what common failure states look like, and which recovery order to follow when a registry, provenance bundle, or export artifact looks suspicious.

## Authoritative surfaces

Treat each surface according to its role. Do not assume every JSON file or registry view is equally authoritative.

| Surface | What it is authoritative for | What it is **not** authoritative for |
|---------|-------------------------------|--------------------------------------|
| `config/registry-sources.json` plus active policy packs | Effective registry trust, pinning, update policy, federation mode, publisher allowlist, namespace mapping | Release attestation state, live install state, historical release audit decisions |
| `self` registry | Writable source-of-truth for local development and promotion | Federation source, backup mirror, immutable published release evidence |
| `federation.mode = "federated"` registry | Read-only upstream namespace input that may satisfy normal resolution when policy allows | Local source-of-truth, mutable tracked working tree, silent bypass around release verification |
| `federation.mode = "mirror"` registry | Operator visibility, backup inventory, comparison surface | Default resolver candidate, authoritative install source, proof that an artifact is trusted |
| `catalog/inventory-export.json` | Current committed inventory summary for registries, skills, release/installability, and federation visibility | Immutable audit evidence, live release readiness, debug policy reasoning |
| `catalog/audit-export.json` | Committed release audit evidence derived from provenance and distributions | Current mutable worktree state, uncommitted review or release readiness |
| `catalog/provenance/*.json` plus signatures | Immutable release evidence for one released version | Global inventory, current registry policy, moving-branch status |
| `policy_trace` and live `check-release-state --json` output | Operator debugging and current decision explanation | Long-term stable external integration contract |

## Boundary rules

### Writable versus read-only

- `self` is the only writable source-of-truth in the normal repo workflow.
- Federated and mirror registries are read-only inputs.
- Hosted registries are immutable artifact sources, not editable working trees.

### Resolution versus visibility

- `resolver_candidate = true` means a registry may satisfy normal resolution under the current policy.
- `resolver_candidate = false` means the registry may still appear in operator or export views, but should not silently win installs or pull flows.
- Mirror visibility is intentional. It exists so operators can compare, inspect, or back up state without promoting that registry to an authoritative install source.

### Inventory versus audit

- `inventory-export.json` answers: "What do we currently expose and from which registry view?"
- `audit-export.json` answers: "What immutable release evidence do we have for this version?"
- When the two disagree, treat audit evidence as authoritative for released artifacts and inventory as authoritative for current committed exposure.

### Namespace mapping

- Mapped local publisher names do not erase upstream identity.
- If a federated registry maps `partner -> partner-labs`, the mapped local name is an operator convenience and policy boundary, not proof that the source originated locally.
- Operator-facing output should preserve both the mapped local namespace and the upstream publisher identity whenever available.

## Common failure modes

### 1. Stale mirror data

Symptoms:

- `catalog/registries.json` shows a mirror registry, but the newest released version is missing from normal resolution.
- Operators see a skill in mirror-derived exports, but install or pull cannot resolve it.

Interpretation:

- The mirror may simply be behind, and that is expected.
- Mirror visibility does not make the mirror authoritative.

Recovery:

1. Run `python3 scripts/list-registry-sources.py` and inspect `federation=` plus `resolver=` output.
2. Confirm whether the registry is `mirror` or `federated`.
3. If the registry is `mirror`, do not treat absence from normal resolution as a bug by itself.
4. Refresh or inspect the authoritative federated or hosted source instead of promoting the mirror.

### 2. Policy drift changes effective federation behavior

Symptoms:

- A publisher that resolved yesterday now fails today.
- `partner-labs/demo` no longer resolves even though the upstream still serves `partner/demo`.

Interpretation:

- The active `registry_sources` policy, pack ordering, `allowed_publishers`, or `publisher_map` may have changed.

Recovery:

1. Run `python3 scripts/check-policy-packs.py`.
2. Run `python3 scripts/check-registry-sources.py`.
3. Inspect the effective registry config with `python3 scripts/list-registry-sources.py`.
4. If the upstream should still federate, fix the policy file or pack override rather than patching exports by hand.
5. Rebuild committed artifacts with `bash scripts/build-catalog.sh` after policy is corrected.

### 3. Missing or invalid provenance

Symptoms:

- `audit-export.json` is missing a release that appears installable.
- `pull-skill` or distribution verification fails on manifest or attestation checks.
- A release exists in inventory, but the audit surface is empty or incomplete.

Interpretation:

- The artifact may not actually be a trusted release yet.
- The provenance bundle, signature, or distribution manifest may be missing, stale, or tampered with.

Recovery:

1. Verify the distribution manifest directly:
   `python3 scripts/verify-distribution-manifest.py <manifest.json>`
2. Verify the release attestation directly:
   `python3 scripts/verify-attestation.py <provenance.json>`
3. If verification fails, do not trust `audit-export.json` to be complete until the release artifacts are repaired and regenerated.
4. Regenerate catalog artifacts with `bash scripts/build-catalog.sh` only after provenance and manifest verification succeeds.

### 4. Export artifacts are older than the committed catalog state

Symptoms:

- `scripts/check-all.sh` reports that catalog contents changed.
- `inventory-export.json` or `audit-export.json` disagrees with `catalog.json`, `registries.json`, or committed provenance.

Interpretation:

- A code or metadata change happened without rebuilding the catalog exports.

Recovery:

1. Run `bash scripts/build-catalog.sh`.
2. Run `python3 scripts/check-catalog-exports.py`.
3. Review the resulting diff instead of editing export files manually.
4. Commit the regenerated artifacts once the diff matches the intended source change.

### 5. Registry trust no longer matches artifact reality

Symptoms:

- A registry still resolves, but operators discover it no longer serves immutable artifacts or no longer matches the pinned policy.
- A formerly trusted upstream needs to be demoted.

Interpretation:

- Registry policy is now too permissive for the source you actually have.

Recovery:

1. Decide whether the source should become `mirror`, `untrusted`, or be removed entirely.
2. Update `config/registry-sources.json` or the active policy pack accordingly.
3. Re-run:
   - `python3 scripts/check-registry-sources.py`
   - `python3 scripts/test-federated-registry-resolution.py`
   - `bash scripts/build-catalog.sh`
4. Verify the resulting exports and resolver behavior before merging the policy change.

## Recovery order

When you are unsure where the failure starts, use this order:

1. Validate policy:
   - `python3 scripts/check-policy-packs.py`
   - `python3 scripts/check-registry-sources.py`
2. Inspect registry visibility and authority:
   - `python3 scripts/list-registry-sources.py`
3. Rebuild and validate committed catalog artifacts:
   - `bash scripts/build-catalog.sh`
   - `python3 scripts/check-catalog-exports.py`
4. Verify immutable release evidence when releases are involved:
   - `python3 scripts/verify-distribution-manifest.py <manifest.json>`
   - `python3 scripts/verify-attestation.py <provenance.json>`
5. Re-run repo validation:
   - `scripts/check-all.sh`

Do not start by hand-editing export artifacts or downgrading a registry to "temporarily make resolution work." Fix policy or release evidence first, then regenerate.

## Safe operator heuristics

- Prefer demoting a questionable upstream to `mirror` over leaving it `federated` while you investigate.
- Prefer failing closed on provenance or signature verification rather than using inventory visibility as proof of trust.
- Prefer rebuilding exports from committed source artifacts over editing generated JSON directly.
- Prefer preserving upstream identity in operator communication even when local publisher mapping is active.

## Escalation triggers

Pause and involve a human reviewer when:

- a federated publisher mapping change would alter which local namespace wins resolution
- a trusted registry must be downgraded or removed
- provenance verification fails for a supposedly stable released artifact
- export artifacts disagree with policy after a clean rebuild
- a mirror appears to contain data that conflicts with the authoritative source-of-truth
