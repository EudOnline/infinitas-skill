# Memory Operating Model

## Goal

This repository now supports an optional long-term memory layer for AI-facing discovery flows.

Memo0 is used only for cognitive memory:

- user or task preference memory
- recent task context memory
- experience memory captured from lifecycle events

It is not used as the registry source of truth.

## Source Of Truth Boundary

These remain authoritative locally:

- `skills`, `skill_drafts`, `skill_versions`
- `releases`, `artifacts`
- `exposures`, `review_cases`, `review_decisions`
- `access_grants`, `credentials`
- `audit_events`, `jobs`

Memory stays advisory only.

- recommendation may use memory to break close ties
- inspect may show memory hints about likely pitfalls or successful patterns
- lifecycle hooks may write experience summaries after successful core transactions
- memory cannot auto-approve, auto-publish, auto-activate, or auto-install anything
- memory cannot override compatibility, access control, review policy, or immutable release rules

## Data Types

`user_preference`

- small preference memories such as stability bias, target-agent preference, or private-first bias

`task_context`

- short-lived task or workflow context such as install intent, inspect intent, or a repeated operator goal

`experience`

- reusable lessons captured from lifecycle events such as draft creation, draft sealing, release readiness, exposure activation, and review outcomes

`audit_events`

- durable server-side trace of what happened, including whether memory writeback was `stored`, `skipped`, `disabled`, `failed`, or `deduped`

`release and review state`

- still lives in the local database and release artifacts, not in Memo0

## Lifecycle Policy Defaults

Lifecycle writeback now applies explicit policy defaults before storing memory:

- `task.authoring.create_draft`
  - `memory_type=task_context`
  - lower confidence
  - short TTL
- `task.authoring.seal_draft`
  - `memory_type=experience`
  - medium confidence
  - medium TTL
- `task.release.ready`
  - `memory_type=experience`
  - high confidence
  - long TTL
- `task.review.approve`
  - `memory_type=experience`
  - high confidence
  - medium-long TTL
- `task.review.reject`
  - `memory_type=experience`
  - high confidence
  - shorter TTL so stale negative outcomes decay faster

This keeps ephemeral workflow context separate from reusable operational lessons.

## Environment Flags

Memory is disabled by default.

```bash
INFINITAS_MEMORY_BACKEND=disabled
INFINITAS_MEMORY_CONTEXT_ENABLED=0
INFINITAS_MEMORY_WRITE_ENABLED=0
```

Supported configuration:

- `INFINITAS_MEMORY_BACKEND`
  - `disabled` by default
  - `memo0` to enable the Memo0 adapter
- `INFINITAS_MEMORY_CONTEXT_ENABLED`
  - enables memory reads for recommend and inspect
- `INFINITAS_MEMORY_WRITE_ENABLED`
  - enables lifecycle writeback attempts
- `INFINITAS_MEMORY_NAMESPACE`
  - logical namespace sent to the provider
- `INFINITAS_MEMORY_TOP_K`
  - retrieval fanout for advisory reads
- `INFINITAS_MEMORY_MEM0_BASE_URL`
  - optional self-hosted Memo0 endpoint
- `INFINITAS_MEMORY_MEM0_API_KEY_ENV`
  - env var name that contains the Memo0 API key
- `MEM0_API_KEY`
  - default key env when `INFINITAS_MEMORY_MEM0_API_KEY_ENV` is not overridden

Example:

```bash
export INFINITAS_MEMORY_BACKEND=memo0
export INFINITAS_MEMORY_CONTEXT_ENABLED=1
export INFINITAS_MEMORY_WRITE_ENABLED=1
export INFINITAS_MEMORY_NAMESPACE=infinitas
export INFINITAS_MEMORY_TOP_K=5
export INFINITAS_MEMORY_MEM0_BASE_URL=http://127.0.0.1:8002
export MEM0_API_KEY=local-dev-token
```

## Fallback Behavior

The core registry must still work when Memo0 is absent or unhealthy.

- if the backend is `disabled`, reads are reported as disabled and writes are skipped
- if `mem0ai` is not installed, provider construction falls back to the noop provider
- if the provider has no read capability, recommendation and inspect return `unavailable`
- if memory retrieval raises an error, recommendation and inspect return an advisory error field and continue
- if lifecycle writeback fails, the main authoring, release, exposure, or review workflow still succeeds and a sanitized audit event is recorded

## Read Paths

Recommendation reads:

- `src/infinitas_skill/discovery/recommendation.py`
- memory types: `user_preference`, `task_context`, `experience`
- effect: bounded soft boost after compatibility gating
- ordering: provider score, policy confidence, memory type, and TTL now combine into one advisory quality score
- retrieval-time curation now suppresses duplicate and very low-signal short-lived memories before ranking

Inspect reads:

- `src/infinitas_skill/discovery/inspect.py`
- memory types: `task_context`, `experience`
- effect: compact advisory hints only
- ordering: hints are trimmed and sorted by the same advisory quality score as recommendation
- the payload now includes a `curation_summary` block so operators and tests can see how many memories were kept or suppressed

## Evaluation Matrix

Memory behavior is now regression-tested with fixture-backed evaluation cases under:

- `tests/fixtures/memory_eval/recommendation_cases.json`
- `tests/fixtures/memory_eval/inspect_cases.json`
- `tests/fixtures/memory_eval/usefulness_cases.json`
- `tests/integration/test_memory_evaluation_matrix.py`

Replay the maintained matrix with:

```bash
uv run pytest tests/integration/test_memory_evaluation_matrix.py -q
```

This matrix is intended to lock in advisory behaviors such as:

- baseline winner without memory
- close-tie winner changes when memory is relevant
- duplicate noisy memories do not swamp a stronger relevant memory
- incompatible candidates never bypass compatibility gating
- negative experience memory does not create positive recommendation lift
- inspect trust state remains authoritative when memory is present
- higher-quality experience memory outranks weaker short-lived hints
- retrieval curation reports how many records were kept versus suppressed
- provider-backed memory never becomes release, review, compatibility, or access truth

The evaluation layer now also computes deterministic usefulness summary metrics from those fixtures:

- beneficial use, where memory helps produce the intended recommendation or inspect hint
- correct restraint, where memory is present but correctly does not take over the decision
- quality success, which combines the two so we do not reward over-aggressive memory use

## Write Paths

Lifecycle writeback is best-effort and post-commit.

- draft created
- draft sealed
- release materialized and marked ready
- exposure created
- exposure activated
- review approved or rejected

Writeback emits `memory_writeback` audit events so operators can see what happened even when the provider is disabled or failing.

Operators can inspect recent writeback health with:

```bash
uv run infinitas server memory-health \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --limit 20 \
  --json
```

This command is deliberately backed by local audit history rather than Memo0 state. It answers "what did the registry attempt and record?" instead of "what does the provider currently believe?".

Operators can inspect or execute guarded curation workflows with:

```bash
uv run infinitas server memory-curation \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --action plan \
  --limit 50 \
  --json
```

This command uses local audit history plus lifecycle memory policy to surface:

- duplicate writeback groups that likely produce redundant memories
- writebacks whose policy TTL has already expired and are good archive or pruning candidates
- lifecycle events most likely to benefit from future curation work

Execution modes:

- `--action plan` is the default and stays read-only
- `--action archive --apply` records local `memory_curation` audit events for selected candidates but does not delete provider-side memory
- `--action prune --apply` attempts provider-side deletion only for guarded candidates that came from `stored` writebacks with a non-empty `memory_id`
- `--max-actions` bounds how many actionable candidates are touched in one execution
- `--enqueue` stores the requested curation action in the hosted `jobs` queue so the worker can execute it asynchronously
- `--use-server-policy` loads scheduled curation defaults from server environment settings instead of CLI flags

Examples:

```bash
uv run infinitas server memory-curation \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --action archive \
  --apply \
  --max-actions 10 \
  --json

uv run infinitas server memory-curation \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --action prune \
  --apply \
  --max-actions 5 \
  --json

uv run infinitas server memory-curation \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --action archive \
  --apply \
  --max-actions 10 \
  --enqueue \
  --json

uv run infinitas server memory-curation \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --use-server-policy \
  --enqueue \
  --json
```

Like `memory-health`, local audit remains the supported truth. Memo0 is advisory memory only, so cleanup decisions are selected from local history first and provider mutation is optional, explicit, and guarded.

When `--use-server-policy` is used, the command reads these server settings:

- `INFINITAS_SERVER_MEMORY_CURATION_ACTION`
- `INFINITAS_SERVER_MEMORY_CURATION_APPLY`
- `INFINITAS_SERVER_MEMORY_CURATION_LIMIT`
- `INFINITAS_SERVER_MEMORY_CURATION_MAX_ACTIONS`
- `INFINITAS_SERVER_MEMORY_CURATION_ACTOR_REF`

## Recommendation Example

```json
{
  "explanation": {
    "memory_summary": {
      "used": true,
      "backend": "memo0",
      "matched_count": 2,
      "advisory_only": true,
      "status": "matched"
    }
  },
  "results": [
    {
      "qualified_name": "lvxiaoer/consume-infinitas-skill",
      "memory_signals": {
        "matched_memory_count": 2,
        "applied_boost": 35,
      "memory_types": ["user_preference", "experience"]
      }
    }
  ]
}
```

Interpretation:

- memory helped rank already-compatible candidates
- the boost stayed bounded
- duplicate or low-signal retrieved memories were suppressed before ranking
- compatibility and trust still came from the normal discovery chain

## Inspect Example

```json
{
  "qualified_name": "lvxiaoer/consume-infinitas-skill",
  "trust_state": "verified",
  "memory_hints": {
    "used": true,
    "backend": "memo0",
    "matched_count": 1,
    "advisory_only": true,
    "status": "matched",
    "curation_summary": {
      "input_count": 2,
      "kept_count": 1,
      "suppressed_duplicates": 1,
      "suppressed_low_signal": 0
    },
    "items": [
      {
        "memory_type": "experience",
        "memory": "OpenClaw installs usually succeed when the release is already materialized.",
        "score": 0.94
      }
    ]
  }
}
```

Interpretation:

- trust remains `verified`
- memory adds context, not trust semantics
- curation keeps the strongest representative when retrieval returns duplicate hints

## Writeback Failure Example

Core workflow success and memory failure can coexist:

```json
{
  "aggregate_type": "memory_writeback",
  "event_type": "memory.writeback.failed",
  "payload": {
    "status": "failed",
    "backend": "memo0",
    "lifecycle_event": "task.review.approve",
    "aggregate_ref": "review_case:12",
    "dedupe_key": "mw:...",
    "payload": {
      "decision": "approve",
      "exposure_id": "7",
      "mode": "blocking",
      "state": "approved"
    },
    "error": "provider_write_failed"
  }
}
```

Interpretation:

- the review decision still committed
- sensitive values and raw paths were not written into memory or the audit payload
- operators still have a traceable failure record

For operations triage:

- `failed` means writeback attempted and fell back to an audit-only trace
- `disabled` means writes were off by configuration, so no provider truth was consulted
- the audit summary is the supported source for health checks because it is available even when Memo0 is absent

## Hard Guarantees

- Memory is disabled by default.
- Memory is never the release, review, exposure, or access source of truth.
- Memory retrieval is advisory and explainable.
- Memory writeback is best-effort and cannot break the core workflow.
- Sanitization removes secrets, grant material, and filesystem paths before memory or audit writeback.
