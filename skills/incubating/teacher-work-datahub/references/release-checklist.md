# Release Checklist

## Recommended release position
Publish `teacher-work-datahub` as:
- `incubating`
- `private` or internal-first
- workspace-scoped
- not zero-config public

## Current release recommendation
Use this wording in registry review:

> `teacher-work-datahub` is a workspace-scoped teacher-work datahub skill for teacher allocation, timetable, and teaching-progress workflows. It is intended for private/incubating distribution and assumes an existing teacher-work data layout. Optional integrations include Feishu delivery and OCR-assisted progress ingestion.

## Pre-submit checklist

### A. Metadata and packaging
- [x] folder name is `teacher-work-datahub`
- [x] `SKILL.md` exists and `name` matches folder
- [x] `_meta.json` exists
- [x] `CHANGELOG.md` exists
- [x] `tests/smoke.md` exists
- [x] `requirements.txt` exists
- [ ] run target registry validation (`check-skill.sh` / `check-all.sh`) if that repository provides them
- [ ] confirm `_meta.json` fields exactly match target registry schema

### B. Positioning clarity
- [x] mark as workspace-scoped
- [x] mark as private/incubating preferred
- [x] explicitly state not zero-config public
- [ ] if publishing externally, add a short portability note in release description

### C. Runtime validation
- [x] `python3 skills/teacher-work-datahub/scripts/registry/bootstrap_report.py --json`
- [x] `python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core`
- [x] `python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode extended`
- [x] confirm healthcheck outputs are generated
- [ ] run one representative real task after final metadata edits

### D. Dependency clarity
- [x] document Python/package dependencies
- [x] separate core-only vs full-workflow expectations
- [x] document optional Feishu/OCR integrations
- [ ] if target registry expects lockfiles or install script, add them

### E. Portability and reviewer experience
- [x] add minimal sample/fixtures dataset
- [x] add one reviewer command path that works without real school private data
- [x] document current reviewer demo outcome and remaining semantic blockers
- [ ] reduce hard-coded default paths or document them more explicitly
- [x] consider `workspace-root` or env-based root override
- [ ] make selfchecks fixture-aware so the full synthetic demo path can pass

### F. Risk review
- [x] no obvious secrets committed inside skill folder
- [x] skill is traceability-oriented and testable
- [ ] review whether Feishu adapter should remain bundled or be split out

## Release blockers vs non-blockers

### Blockers for an incubating/private submission
- missing registry-required metadata
- broken bootstrap/selfcheck/healthcheck
- undocumented runtime dependencies
- accidental secret exposure

### Non-blockers for an incubating/private submission
- strong workspace coupling
- lack of generic public sample UX
- optional adapter split not yet completed

## Recommended next milestone after submission
1. add minimal fixtures
2. add root override support
3. separate core datahub vs Feishu adapter boundary more cleanly
4. prepare a public-safe demo path if you later want broader distribution
