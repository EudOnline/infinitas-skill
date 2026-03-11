# Runtime Dependencies

## Positioning
`teacher-work-datahub` is a **workspace-scoped** skill for a teacher-work data layout. It is not a zero-config public utility.

## Python
- Recommended: `python3` 3.11+
- Minimum practical expectation: `python3` available in PATH

## Dependency layers

### Core-only operations
These usually work with Python standard library only:
- `scripts/registry/bootstrap_report.py`
- `scripts/query/selfcheck_all.py`
- `scripts/query/healthcheck_datahub.py`
- most index/query helpers against already-prepared JSON data

### Full datahub workflow
Install `requirements.txt` when you need parser / delivery / adapter capability:

```bash
pip install -r skills/teacher-work-datahub/requirements.txt
```

Included packages:
- `Pillow` — image generation for timetable outputs
- `openpyxl` — parse `.xlsx` school schedule files
- `xlrd` — parse legacy `.xls` teacher allocation files
- `requests` — Feishu OpenAPI media/message delivery

## Optional environment/integration expectations

### OCR
OCR-related teaching-progress ingestion may require:
- environment variable `SILICONFLOW_API_KEY`
- or `config/ocr.json` with `api_key`

If OCR is not configured, bootstrap should report actionable `suggested_actions` instead of failing hard.

### Feishu adapter
Feishu send/integration paths require a valid OpenClaw Feishu account configuration in the host environment.

## Recommended release note wording
When publishing, describe this skill as:
- workspace-scoped
- teacher-work datahub
- incubating/private preferred
- optional Feishu/OCR integrations
