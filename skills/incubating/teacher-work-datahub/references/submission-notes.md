# Submission Notes

## Recommended registry positioning
- status: `incubating`
- visibility: `private` (or internal-first)
- release positioning: workspace-scoped, not zero-config public

## Suggested short summary
`teacher-work-datahub` is a workspace-scoped teacher-work datahub skill for teacher allocation, timetable, and teaching-progress workflows. It supports traceable source catalogs, active-source arbitration, indexes, delivery receipts, health checks, and reviewer-safe fixture validation.

## Suggested review note
This skill is intended for private/incubating distribution rather than zero-config public installation. It assumes a teacher-work data layout, but now includes:
- explicit runtime dependency documentation
- root-aware execution for key entrypoints
- minimal synthetic fixtures
- reviewer-safe selfcheck validation path
- documented demo run
- a fresh-agent quick path for first-run validation

## Data storage and install expectations
Operational data is primarily stored in the workspace `data/` and `config/` hierarchy rather than inside the skill folder itself.

That means:
- some directories and output files can be created automatically at runtime
- core business data does **not** appear automatically after installation
- usable state is established through one of these paths:
  - ingesting real teacher-work files
  - running bootstrap / rebuild flows
  - loading synthetic fixtures for reviewer-safe validation

So this skill should be reviewed as a **workspace-scoped skill with guided initialization**, not as a fully self-contained zero-config package.

## Fresh agent quick path
For a fresh agent in a new environment, do not assume real production data already exists.

```bash
pip install -r skills/teacher-work-datahub/requirements.txt
export TEACHER_WORK_DATAHUB_FIXTURE=minimal-datahub
python3 skills/teacher-work-datahub/scripts/tests/load_minimal_fixture.py --workspace-root /tmp/twd-reviewer-demo
python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py --workspace-root /tmp/twd-reviewer-demo
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core --workspace-root /tmp/twd-reviewer-demo
```

## Suggested reviewer commands
```bash
export TEACHER_WORK_DATAHUB_FIXTURE=minimal-datahub
python3 skills/teacher-work-datahub/scripts/tests/load_minimal_fixture.py --workspace-root /tmp/twd-reviewer-demo
python3 skills/teacher-work-datahub/scripts/registry/bootstrap_report.py --json --workspace-root /tmp/twd-reviewer-demo
python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py --workspace-root /tmp/twd-reviewer-demo
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core --workspace-root /tmp/twd-reviewer-demo
```

## What is strong now
- release packaging layer exists
- metadata/changelog/smoke are present
- core healthcheck path is documented
- synthetic reviewer demo passes selfcheck-all (7/7)
- workspace-root support exists on core reviewer entrypoints

## What remains intentionally true
- this is still a workspace-scoped skill
- public portability is improved but not the primary positioning
- production baseline checks and fixture baseline checks are separate validation lenses

## Risk signals to disclose honestly
- medium risk due to workflow breadth and optional integrations
- still coupled to teacher-work directory conventions
- Feishu/OCR integrations are optional and environment-dependent

## Recommended release sentence
> Suitable for incubating/private registry submission now. Prefer to present it as a workspace-scoped teacher-work datahub skill with reviewer-safe synthetic validation, not as a zero-config public utility.
