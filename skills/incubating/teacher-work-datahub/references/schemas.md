# Schemas

## 1. `catalog/sources.json`

```json
{
  "schema_version": "teacher-work-datahub.sources.v1",
  "records": []
}
```

Each record should include at least:

```json
{
  "record_id": "src-xxxx",
  "domain": "teacher_allocation",
  "kind": "teacher_allocation",
  "academic_year": "2025-2026",
  "semester": "S2",
  "status": "active",
  "source_name": "2026年3月班主任、任课教师配备一览表.xls",
  "raw_path": "data/teacher-work-datahub/raw/teacher-allocation/S2/...",
  "curated_path": "data/teacher-work-datahub/curated/teacher-allocation/S2/...",
  "report_paths": [],
  "source_mtime": "2026-03-06T08:15:06+08:00",
  "ingested_at": "2026-03-10T08:00:00+08:00",
  "parsed_at": "2026-03-10T08:01:00+08:00",
  "fingerprint": "sha256:...",
  "superseded_by": null,
  "notes": "",
  "metadata": {}
}
```

## 2. `curated/indexes/active_sources.json`

```json
{
  "schema_version": "teacher-work-datahub.active-sources.v1",
  "by_semester": {
    "S2": {
      "teacher_allocation": {
        "record_id": "src-xxxx",
        "source_name": "...",
        "raw_path": "...",
        "curated_path": "...",
        "academic_year": "2025-2026",
        "kind": "teacher_allocation",
        "domain": "teacher_allocation"
      }
    }
  }
}
```

## 3. `curated/indexes/teacher_index.json`

```json
{
  "schema_version": "teacher-work-datahub.teacher-index.v1",
  "teachers": {
    "吕晓瑞": {
      "academic_year": "2025-2026",
      "semester": "S2",
      "subjects": ["物理"],
      "classes": ["2403班", "2404班"],
      "grades": ["高二"],
      "active_source": {
        "record_id": "src-xxxx",
        "kind": "teacher_allocation"
      },
      "evidence": []
    }
  }
}
```

## 4. `curated/indexes/class_index.json`

```json
{
  "schema_version": "teacher-work-datahub.class-index.v1",
  "classes": {
    "2404班": {
      "academic_year": "2025-2026",
      "semester": "S2",
      "grade": "高二",
      "subjects": {
        "物理": ["吕晓瑞"]
      },
      "active_source": {
        "record_id": "src-xxxx",
        "kind": "teacher_allocation"
      },
      "evidence": []
    }
  }
}
```

## 5. `curated/indexes/semester_context.json`

```json
{
  "schema_version": "teacher-work-datahub.semester-context.v1",
  "current": {
    "academic_year": "2025-2026",
    "semester": "S2",
    "grade_scope": "highschool",
    "city": "太原市"
  },
  "source_priority": [
    "teacher_allocation",
    "grade_schedule_with_selfstudy",
    "school_schedule_no_selfstudy",
    "teaching_progress"
  ]
}
```
