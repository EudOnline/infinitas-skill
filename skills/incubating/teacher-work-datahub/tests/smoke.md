# Smoke Test

## Goal
Verify that the teacher-work-datahub skill is healthy enough for incubating release by running the official healthcheck entrypoint and confirming the workspace baseline is green.

## Preconditions
- Run inside the teacher work workspace.
- `python3` is available.
- Existing workspace data has already been indexed.
- If parser / delivery / adapter paths are under review, install `skills/teacher-work-datahub/requirements.txt` first.

## Steps

### 1) Run bootstrap check first
```bash
python3 skills/teacher-work-datahub/scripts/registry/bootstrap_report.py --json
```

Expected:
- exit code = 0
- returns JSON
- contains `checks`
- contains `suggested_actions`
- if OCR key is missing, `suggested_actions` clearly tells the operator how to configure it

### 2) Run the official healthcheck in core mode
```bash
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core
```

Expected:
- exit code = 0
- summary says `总体状态：healthy`
- `selfcheck_all` shows all checks passing

### 3) Run the official healthcheck in extended mode
```bash
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode extended
```

Expected:
- exit code = 0
- summary says `总体状态：healthy`
- if Feishu adapter is present, extended integration check runs normally
- if Feishu adapter is absent, the optional integration check is reported as `skipped` rather than causing the whole check to fail

### 4) Verify generated outputs
Check these files exist after the run:
- `data/teacher-work-datahub/outputs/healthchecks/healthcheck-datahub.json`
- `data/teacher-work-datahub/outputs/healthchecks/healthcheck-datahub.txt`
- `data/teacher-work-datahub/outputs/selfchecks/selfcheck-all.json`
- `data/reports/teacher-semester-flow/p6/p6-report.json`

## 5) Optional reviewer-safe fixture path
If the reviewer should avoid real workspace data, load the minimal synthetic fixture set first:

```bash
python3 skills/teacher-work-datahub/scripts/tests/load_minimal_fixture.py
```

Expected:
- returns JSON
- copies only synthetic fixture files
- prepares a reviewer-safe minimal baseline for follow-up checks

## Human review notes
Reviewer should confirm:
- the skill behaves as a workspace-scoped private datahub skill, not a generic public skill
- no secrets are committed
- docs point users to `README.md`, `references/healthcheck.md`, `references/migration-status.md`, and `references/release-checklist.md`
