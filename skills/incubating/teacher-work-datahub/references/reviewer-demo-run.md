# Reviewer Demo Run

## Purpose
Record the current reviewer-safe demo attempt using a copied workspace plus minimal synthetic fixtures.

## Demo environment
- demo root: `/tmp/twd-reviewer-demo`
- source workspace copied from the main teacher-work workspace
- fixture mode env:
  - `TEACHER_WORK_DATAHUB_FIXTURE=minimal-datahub`

## Commands run

### 1) Load fixtures
```bash
TEACHER_WORK_DATAHUB_FIXTURE=minimal-datahub \
python3 skills/teacher-work-datahub/scripts/tests/load_minimal_fixture.py \
  --workspace-root /tmp/twd-reviewer-demo
```

Result:
- success
- copied synthetic fixture files into demo workspace

### 2) Run selfcheck chain in fixture mode
```bash
TEACHER_WORK_DATAHUB_FIXTURE=minimal-datahub \
python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py \
  --workspace-root /tmp/twd-reviewer-demo
```

## Final result
- total = 7
- passed = 7
- failed = 0

Passed checks:
- `teacher_context`
- `active_sources`
- `teaching_progress`
- `source_trace_lineage`
- `receipt_outputs`
- `query_source_trace`
- `query_progress_scope`

## What changed to make this pass
The reviewer-safe path now depends on two layers:

### 1) Root-aware plumbing
Implemented across:
- fixture loader
- bootstrap report
- healthcheck entrypoint
- selfcheck entrypoints
- shared workspace path helpers

### 2) Fixture-aware semantics
Implemented for selfchecks that previously assumed production-only facts, including:
- real teacher names
- S2-only assumptions
- production record IDs
- large lineage counts
- production teaching-progress assertions

## Accurate current claim
This is now true:

> Reviewer can load synthetic fixtures into an isolated workspace and run the full selfcheck chain successfully in fixture mode.

## Remaining boundary
This does **not** mean the synthetic demo reproduces all production behaviors. It means:
- portable reviewer validation is now available
- production/private baseline checks still exist
- fixture mode and production mode are intentionally separate validation lenses

## Suggested reviewer flow
```bash
export TEACHER_WORK_DATAHUB_FIXTURE=minimal-datahub
python3 skills/teacher-work-datahub/scripts/tests/load_minimal_fixture.py --workspace-root /tmp/twd-reviewer-demo
python3 skills/teacher-work-datahub/scripts/registry/bootstrap_report.py --json --workspace-root /tmp/twd-reviewer-demo
python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py --workspace-root /tmp/twd-reviewer-demo
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core --workspace-root /tmp/twd-reviewer-demo
```

## Release-readiness impact
This materially improves incubating/private release readiness because the skill now has:
- minimal fixtures
- root-aware execution
- reviewer-safe selfcheck validation
- documented demo flow
