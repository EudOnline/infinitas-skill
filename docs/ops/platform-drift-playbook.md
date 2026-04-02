---
audience: operators and release maintainers
owner: repository maintainers
source_of_truth: platform drift playbook
last_reviewed: 2026-03-30
status: maintained
---

# Platform Drift Playbook

Codex, Claude Code, and OpenClaw will keep changing their runtime assumptions, export formats, and recommended repository layouts. This playbook is the maintenance loop for keeping `infinitas-skill` aligned with those upstream shifts without letting stale claims leak into discovery or release output.

## 1. Verify upstream docs first

Before editing any local contract or compatibility metadata:

1. Read the current upstream docs, release notes, or official migration pages for the platform you are checking.
2. Confirm whether the change is a stable contract change, a volatile runtime behavior change, or only an implementation detail.
3. Record the official URLs you used so they can be copied into `docs/platform-contracts/<platform>.md`.
4. Capture the verification date you are using as the new `Last verified` marker.

If the upstream change is unclear, do not guess. Keep the existing contract as-is and open a follow-up investigation instead of publishing speculative compatibility claims.

## 2. Update `docs/platform-contracts/*.md`

For the affected platform contract document:

1. Refresh `Stable assumptions` only when the upstream platform now treats that behavior as durable.
2. Refresh `Volatile assumptions` when a behavior is still real but likely to shift again.
3. Replace `Official sources` with the exact upstream links used for the review.
4. Set `Last verified` to the date of the current upstream review.

Then run:

```bash
uv run infinitas compatibility check-platform-contracts --max-age-days 30 --stale-policy fail
```

That command now fails if a platform contract is too old or if the machine-readable profile mirror has drifted.

## 3. Sync `profiles/*.json`

Each file under `profiles/` is the machine-readable mirror of the corresponding contract doc.

After updating a contract doc:

1. Copy the refreshed `Official sources` list into `profiles/<platform>.json -> contract.sources`.
2. Copy the refreshed `Last verified` date into `profiles/<platform>.json -> contract.last_verified`.
3. Keep the runtime/export configuration aligned only if the upstream change actually affected those fields.

Then rerun:

```bash
uv run python3 scripts/test-canonical-contracts.py
uv run infinitas compatibility check-platform-contracts --max-age-days 30 --stale-policy fail
```

## 4. Refresh verified platform evidence

If the platform change could affect whether a skill still works, refresh verified support evidence for the impacted skills:

```bash
uv run python3 scripts/record-verified-support.py <skill> --platform codex --platform claude --platform openclaw --build-catalog
```

You do not need to refresh every platform every time, but you do need fresh evidence for every platform the skill still declares in `_meta.json.agent_compatible` before a stable release can pass `preflight` or `stable-release`.

## 5. Interpret stale evidence in discovery and release flows

The repository now treats compatibility freshness as a first-class signal:

- `freshness_state = fresh`: evidence is recent enough and not older than the current platform contract review.
- `freshness_state = stale`: evidence exists, but it is too old or predates a newer platform contract update.
- `freshness_state = unknown`: the skill declares support, but no verified evidence is recorded yet.

Operational meaning:

- Discovery and recommendation surfaces can still show stale evidence, but they rank fresh verified support higher than stale or declared-only claims.
- Release readiness blocks when a declared platform is `stale`, `unknown`, `blocked`, `broken`, or `unsupported`.
- `uv run infinitas release check-state <name> --mode preflight --json` exposes the blocking details in `release.platform_compatibility`.

## 6. Steady-state maintenance loop

Use this loop whenever upstream platform behavior changes or when release readiness reports stale platform support:

1. Refresh the upstream platform contract review.
2. Update `docs/platform-contracts/*.md`.
3. Sync `profiles/*.json`.
4. Rerun `python3 scripts/record-verified-support.py <skill> --platform ... --build-catalog` for impacted skills.
5. Run `uv run bash scripts/check-all.sh`.
6. Ship only after `uv run infinitas release check-state <skill> --mode preflight` is clean.
