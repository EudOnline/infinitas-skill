# Sample Fixtures Plan

## Goal
Provide a reviewer-safe, public-safe, minimal dataset so `teacher-work-datahub` can demonstrate bootstrap, selfcheck, and one query flow without relying on real school data.

## Why this matters
Current skill quality is strong, but reviewer reproducibility is still limited by workspace-coupled private data. A minimal fixture set would improve:
- portability
- registry review confidence
- smoke-test reproducibility
- future public-safe demos

## Recommended fixture scope
Create a tiny synthetic dataset that includes only what the core checks need.

## Proposed layout

```text
skills/teacher-work-datahub/tests/fixtures/minimal-datahub/
├── catalog/
│   └── sources.json
├── curated/
│   ├── indexes/
│   │   ├── active_sources.json
│   │   ├── teacher_index.json
│   │   ├── class_index.json
│   │   └── semester_context.json
│   └── lineage/
│       └── source_lineage.json
└── schedules/
    ├── grade_schedule_minimal.json
    └── school_schedule_minimal.json
```

## Minimal content expectations

### 1) `sources.json`
Contains 2–3 synthetic records:
- one teacher allocation record
- one grade schedule with selfstudy record
- optional one teaching-progress record

### 2) `teacher_index.json`
Contains one synthetic teacher, for example:
- `测试教师A`
- classes: `9901班`, `9902班`
- subject: `物理`

### 3) `class_index.json`
Contains matching synthetic classes only.

### 4) `semester_context.json`
Contains one synthetic current semester, for example:
- academic_year: `2099-2100`
- semester: `S1`
- city: `测试市`

### 5) `grade_schedule_minimal.json`
Contains enough structure for one teacher timetable query and one active-source selection path.

### 6) `source_lineage.json`
Contains only a tiny lineage example so source-trace selfchecks can pass.

## Reviewer-safe rules
- use clearly fake names/classes/school labels
- avoid any real teacher, student, school, or city identifiers unless intentionally generic
- avoid embedding any real Feishu IDs, OCR keys, or org config

## Suggested validation path for fixtures
When fixtures are added, expose a documented command path such as:

```bash
python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py --fixture minimal-datahub
```

or

```bash
TEACHER_WORK_DATAHUB_FIXTURE=minimal-datahub python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core
```

## Implementation options

### Option A: fixture-aware CLI flags
Add optional CLI flags/env vars to point scripts at fixture roots.

Pros:
- clean reviewer experience
- reusable for CI

Cons:
- requires script changes

### Option B: temporary fixture bootstrap script
Create a helper such as:

```bash
python3 skills/teacher-work-datahub/scripts/tests/load_minimal_fixture.py
```

that copies fixture files into the expected workspace paths.

Pros:
- minimal code churn
- easiest short-term path

Cons:
- writes into workspace data paths

## Recommended order
1. start with Option B for speed
2. later evolve to Option A for cleaner portability

## Best next action
If prioritizing fast registry readiness, implement:
- `tests/fixtures/minimal-datahub/`
- `scripts/tests/load_minimal_fixture.py`
- one extra smoke section for fixture-based reviewer run
