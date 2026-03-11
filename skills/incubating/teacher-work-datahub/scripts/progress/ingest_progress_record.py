#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from parse_progress_markdown_table import parse_markdown_table_text
from progress_query_utils import load_json, normalize_grade_scope, normalize_semester

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[4]
DATAHUB_ROOT = WORKSPACE_ROOT / "data/teacher-work-datahub"

ARCHIVE_DIR = DATAHUB_ROOT / "archive/teaching-progress/inbound"
EXTRACTED_DIR = DATAHUB_ROOT / "curated/teaching-progress/extracted"
REPORTS_DIR = DATAHUB_ROOT / "outputs/teaching-progress/reports"
REVIEW_DIR = DATAHUB_ROOT / "outputs/teaching-progress/review"
CATALOG_PATH = DATAHUB_ROOT / "catalog/sources.json"
CONTEXT_PATH = DATAHUB_ROOT / "curated/indexes/semester_context.json"

GRADE_SCOPE_LABELS = {
    "highschool": "高中",
    "junior": "初中",
    "primary": "小学",
}


def norm(value: str) -> str:
    return (value or "").strip()


def grade_scope_label(value: str) -> str:
    return GRADE_SCOPE_LABELS.get(value, value)


def ensure_dirs() -> None:
    for path in [ARCHIVE_DIR, EXTRACTED_DIR, REPORTS_DIR, REVIEW_DIR, CATALOG_PATH.parent, CONTEXT_PATH.parent]:
        path.mkdir(parents=True, exist_ok=True)


def timestamp_slug(ts: datetime | None = None) -> str:
    return (ts or datetime.now()).strftime("%Y%m%d-%H%M")


def archive_name(city: str, academic_year: str, semester: str, grade_scope: str, source_path: Path) -> str:
    ext = source_path.suffix.lower() or ".dat"
    return f"{city}-{academic_year}-{semester}-{grade_scope_label(grade_scope)}-{timestamp_slug()}{ext}"


def build_paths(city: str, academic_year: str, semester: str, grade_scope: str, source_path: Path) -> dict:
    archive_filename = archive_name(city, academic_year, semester, grade_scope, source_path)
    return {
        "archive_path": ARCHIVE_DIR / archive_filename,
        "extracted_path": EXTRACTED_DIR / f"{city}-{academic_year}-{semester}-{grade_scope_label(grade_scope)}.json",
        "report_path": REPORTS_DIR / f"{city}-{academic_year}-{semester}-{grade_scope_label(grade_scope)}.md",
    }


def copy_to_archive(source_path: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() == archive_path.resolve():
        return
    shutil.copy2(source_path, archive_path)


def infer_doc_type(subjects: list[str]) -> str:
    unique_subjects = {norm(s) for s in subjects if norm(s)}
    return "teaching_progress_subject_table" if len(unique_subjects) == 1 else "teaching_progress_total_table"


def infer_semantic_type(text: str) -> str:
    t = norm(text)
    if not t:
        return "unknown"
    if t.startswith("建议"):
        return "advice"
    if "各校" in t or "自主安排" in t or "自行安排" in t:
        return "school_defined"
    if "复习" in t or "一轮" in t or "二轮" in t:
        return "review_plan"
    return "exam_scope"


def normalize_scope_text(text: str) -> str:
    t = norm(text)
    if not t:
        return ""
    t = t.replace("；", ";").replace("，", "；").replace(";", "；")
    return t


def split_chapters(text: str) -> list[str]:
    t = normalize_scope_text(text)
    if not t or infer_semantic_type(t) != "exam_scope":
        return []
    return [seg.strip() for seg in t.split("；") if seg.strip()]


def empty_scope_node() -> dict:
    return {
        "status": "missing",
        "semantic_type": "unknown",
        "raw_text": "",
        "normalized_text": "",
        "chapters": [],
        "confidence": None,
        "evidence": [],
    }


def make_scope_node(text: str) -> dict:
    raw = norm(text)
    if not raw or raw in {"未注明", "待确认", "暂无", "无", "—", "-", "/"}:
        return empty_scope_node()
    normalized = normalize_scope_text(raw)
    return {
        "status": "explicit",
        "semantic_type": infer_semantic_type(normalized),
        "raw_text": raw,
        "normalized_text": normalized,
        "chapters": split_chapters(normalized),
        "confidence": None,
        "evidence": [],
    }


def coerce_scope_input(value):
    if isinstance(value, dict):
        raw_text = norm(value.get("raw_text")) or norm(value.get("normalized_text"))
        if not raw_text:
            return empty_scope_node()
        normalized = norm(value.get("normalized_text")) or normalize_scope_text(raw_text)
        return {
            "status": norm(value.get("status")) or "explicit",
            "semantic_type": norm(value.get("semantic_type")) or infer_semantic_type(normalized),
            "raw_text": raw_text,
            "normalized_text": normalized,
            "chapters": value.get("chapters") or split_chapters(normalized),
            "confidence": value.get("confidence"),
            "evidence": value.get("evidence") or [],
        }
    return make_scope_node(str(value or ""))


def build_entries_from_json(payload: dict) -> list[dict]:
    entries = []
    for item in payload.get("entries") or []:
        entries.append(
            {
                "grade": norm(item.get("grade")),
                "grade_code": norm(item.get("grade_code")),
                "subject": norm(item.get("subject")),
                "subject_code": norm(item.get("subject_code")),
                "midterm": coerce_scope_input(item.get("midterm")),
                "final": coerce_scope_input(item.get("final")),
                "weekly_plan": item.get("weekly_plan") or [],
                "notes": item.get("notes") or [],
            }
        )
    return entries


def build_entries_from_simple_json(payload: dict) -> list[dict]:
    entries = []
    for item in payload.get("subjects") or []:
        scope = item.get("exam_scope") or {}
        subject_name = norm(item.get("subject_name"))
        if subject_name == "生物":
            subject_name = "生物学"
        entries.append(
            {
                "grade": norm(item.get("grade_level")),
                "grade_code": "",
                "subject": subject_name,
                "subject_code": "",
                "midterm": make_scope_node(scope.get("midterm", "")),
                "final": make_scope_node(scope.get("final", "")),
                "weekly_plan": [],
                "notes": [],
            }
        )
    return entries


def parse_seed_json(seed_json: Path) -> dict:
    payload = load_json(seed_json)
    entries = build_entries_from_json(payload)
    if not entries:
        entries = build_entries_from_simple_json(payload)
    subjects = [item.get("subject", "") for item in entries]
    return {
        "doc_type": norm(payload.get("doc_type")) or infer_doc_type(subjects),
        "entries": entries,
        "notes": payload.get("notes") or [],
        "warnings": payload.get("warnings") or [],
        "meta": {
            "city": norm(payload.get("city")),
            "academic_year": norm(payload.get("academic_year")),
            "semester": norm(payload.get("semester")),
            "grade_scope": norm(payload.get("grade_scope")),
            "title": norm(payload.get("title")),
        },
    }


def parse_seed_markdown(seed_md: Path) -> dict:
    text = seed_md.read_text(encoding="utf-8")
    current_grade = ""
    current_subject = ""
    entries = []
    by_key = {}

    def ensure_entry(grade: str, subject: str):
        key = (grade, subject)
        if key not in by_key:
            by_key[key] = {
                "grade": grade,
                "grade_code": "",
                "subject": subject,
                "subject_code": "",
                "midterm": empty_scope_node(),
                "final": empty_scope_node(),
                "weekly_plan": [],
                "notes": [],
            }
            entries.append(by_key[key])
        return by_key[key]

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m_grade = re.match(r"^##\s+(高一|高二|高三|初一|初二|初三)$", line)
        if m_grade:
            current_grade = m_grade.group(1)
            current_subject = ""
            continue
        m_subject = re.match(r"^###\s+(.+)$", line)
        if m_subject and current_grade:
            current_subject = m_subject.group(1).strip()
            continue
        if not current_grade or not current_subject:
            continue
        if line.startswith("- 期中："):
            ensure_entry(current_grade, current_subject)["midterm"] = make_scope_node(line.replace("- 期中：", "", 1).strip())
        elif line.startswith("- 期末："):
            ensure_entry(current_grade, current_subject)["final"] = make_scope_node(line.replace("- 期末：", "", 1).strip())

    subjects = [item.get("subject", "") for item in entries]
    return {
        "doc_type": infer_doc_type(subjects),
        "entries": entries,
        "notes": [],
        "warnings": [],
        "meta": {},
    }


def parse_seed(seed_path: Path) -> dict:
    if seed_path.suffix.lower() == ".json":
        return parse_seed_json(seed_path)
    if seed_path.suffix.lower() in {".md", ".markdown"}:
        return parse_seed_markdown(seed_path)
    raise ValueError(f"unsupported seed file: {seed_path}")


def run_ocr_to_json(source_file: Path) -> dict:
    prompt = (
        '请识别这张教学进度总表，并只输出一个 JSON 对象，不要 markdown、不加解释。'
        'JSON 结构为：'
        '{"city":"","academic_year":"","semester":"S1或S2","grade_scope":"highschool/junior/primary",'
        '"doc_type":"teaching_progress_total_table","notes":[],"warnings":[],'
        '"entries":[{"grade":"高一/高二/高三","subject":"","midterm":"","final":""}]}'
        '。要求：1）尽量完整提取；2）未注明填空字符串；3）不要猜测；4）若图中是复习安排或建议，也原样填入 midterm/final 文本；5）生物统一写为生物学。'
    )
    cmd = ["bash", str(WORKSPACE_ROOT / "tools/scripts/ocr-manager.sh"), "ocr", str(source_file), prompt]
    proc = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), check=True, text=True, capture_output=True)
    stdout = (proc.stdout or "").strip()
    match = re.search(r"\{.*\}", stdout, flags=re.S)
    if not match:
        raise RuntimeError(f"OCR did not return JSON: {stdout[:200]}")
    try:
        return json.loads(match.group(0))
    except Exception as exc:
        raise RuntimeError(f"OCR JSON parse failed: {exc}; raw={stdout[:200]}") from exc


def run_qwen_markdown_ocr(source_file: Path, model: str) -> str:
    prompt = "请识别图片中的所有文字，尽量保持原始段落、换行和表格结构。不要总结。"
    config = load_json(WORKSPACE_ROOT / "config/ocr.json")
    api_key = os.getenv("SILICONFLOW_API_KEY") or config.get("api_key", "")
    if not api_key:
        raise RuntimeError("missing api key")
    out_dir = WORKSPACE_ROOT / "data/reports/ocr" / "tp-qwen-auto"
    out_dir.mkdir(parents=True, exist_ok=True)
    compare_script = WORKSPACE_ROOT / "tools/scripts/ocr-compare.py"
    cmd = [
        "python3",
        str(compare_script),
        "--image",
        str(source_file),
        "--prompt",
        prompt,
        "--models",
        model,
        "--out-dir",
        str(out_dir),
        "--api-key",
        api_key,
    ]
    proc = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), check=True, text=True, capture_output=True)
    data = json.loads(proc.stdout)
    item = data.get(model) or {}
    if not item.get("ok"):
        raise RuntimeError(item.get("error") or f"qwen model failed: {model}")
    return Path(item["path"]).read_text(encoding="utf-8")


def try_qwen_table_extraction(source_file: Path, primary_model: str, fallback_model: str) -> tuple[dict | None, dict]:
    attempts = []
    models = [primary_model]
    if fallback_model and fallback_model != primary_model:
        models.append(fallback_model)

    score_script = SCRIPT_DIR / "score_progress_ocr_quality.py"

    for model in models:
        try:
            markdown = run_qwen_markdown_ocr(source_file, model)
            temp_md = WORKSPACE_ROOT / "data/reports/ocr" / "tp-qwen-auto" / f"score-{model.replace('/', '_')}.md"
            temp_md.parent.mkdir(parents=True, exist_ok=True)
            temp_md.write_text(markdown, encoding="utf-8")
            score_proc = subprocess.run(
                ["python3", str(score_script), "--markdown", str(temp_md), "--grade-scope", "highschool"],
                cwd=str(WORKSPACE_ROOT),
                check=True,
                text=True,
                capture_output=True,
            )
            quality = json.loads(score_proc.stdout)

            payload = parse_markdown_table_text(markdown)
            stats = payload.get("stats") or {}
            attempts.append(
                {
                    "model": model,
                    "ok": True,
                    "entry_count": stats.get("entry_count", 0),
                    "subject_count": stats.get("subject_count", 0),
                    "grade_count": stats.get("grade_count", 0),
                    "quality": quality,
                }
            )
            if quality.get("risk_level") == "high":
                continue
            if stats.get("entry_count", 0) > 0 and stats.get("subject_count", 0) > 0:
                normalized_entries = []
                for item in payload.get("entries") or []:
                    normalized_entries.append(
                        {
                            "grade": norm(item.get("grade")),
                            "grade_code": "",
                            "subject": norm(item.get("subject")),
                            "subject_code": "",
                            "midterm": make_scope_node(item.get("midterm", "")),
                            "final": make_scope_node(item.get("final", "")),
                            "weekly_plan": [],
                            "notes": [],
                        }
                    )
                payload["entries"] = normalized_entries
                payload["meta"] = {
                    "city": norm(payload.get("city")),
                    "academic_year": norm(payload.get("academic_year")),
                    "semester": norm(payload.get("semester")),
                    "grade_scope": norm(payload.get("grade_scope")),
                    "title": norm(payload.get("title")),
                }
                payload["quality"] = quality
                return payload, {
                    "attempted": True,
                    "succeeded": True,
                    "model_used": model,
                    "attempts": attempts,
                    "error": "",
                    "quality": quality,
                }
        except Exception as exc:
            attempts.append({"model": model, "ok": False, "error": str(exc)})

    error = "all qwen models failed"
    if attempts:
        last = attempts[-1]
        if not last.get("ok"):
            error = last.get("error", error)
    return None, {
        "attempted": True,
        "succeeded": False,
        "model_used": "",
        "attempts": attempts,
        "error": error,
        "quality": {},
    }


def write_record(*, city: str, academic_year: str, semester: str, grade_scope: str, archive_path: Path, extracted_path: Path, doc_type: str, entries: list[dict], notes: list[str], warnings: list[str], status: str) -> None:
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    key = f"{city}::{academic_year}::{semester}::{grade_scope}"
    record = {
        "schema_version": "2.0",
        "doc_type": doc_type,
        "city": city,
        "academic_year": academic_year,
        "semester": semester,
        "grade_scope": grade_scope,
        "source": {
            "file": str(archive_path.relative_to(WORKSPACE_ROOT)),
            "filename": archive_path.name,
            "status": status,
            "version": datetime.now().strftime("%Y-%m-%d"),
            "updated_at": ts,
        },
        "catalog": {
            "record_id": "",
            "key": key,
        },
        "entries": entries,
        "warnings": warnings,
        "notes": notes,
        "stats": {
            "entry_count": len(entries),
        },
    }
    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def run_script(script_name: str, args: list[str]) -> subprocess.CompletedProcess:
    cmd = ["python3", str(SCRIPT_DIR / script_name), *args]
    return subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), check=True, text=True, capture_output=True)


def decide_record_status(requested_status: str, validation: dict) -> tuple[str, str]:
    requested = norm(requested_status) or "active"
    risk = norm(validation.get("risk_level")) or "low"
    if requested != "active":
        return requested, "manual_override"
    if risk == "high":
        return "draft", "auto_downgrade_high_risk"
    return "active", "normal"


def validate_entries(entries: list[dict], grade_scope: str = "") -> dict:
    grades = sorted({norm(item.get("grade")) for item in entries if norm(item.get("grade"))})
    subjects = sorted({norm(item.get("subject")) for item in entries if norm(item.get("subject"))})
    explicit_mid = sum(1 for item in entries if ((item.get("midterm") or {}).get("status") == "explicit"))
    explicit_final = sum(1 for item in entries if ((item.get("final") or {}).get("status") == "explicit"))
    issues = []
    suggestions = []

    if not entries:
        issues.append("entries=0")
    if not grades:
        issues.append("grades=0")
    if not subjects:
        issues.append("subjects=0")
    if explicit_mid + explicit_final == 0:
        issues.append("exam_nodes=0")

    expected_grade_map = {
        "highschool": {"高一", "高二", "高三"},
        "junior": {"初一", "初二", "初三"},
    }
    expected_subject_map = {
        "highschool": {"语文", "数学", "英语", "政治", "历史", "物理", "化学", "生物学", "地理", "信息技术", "通用技术"},
    }

    if grade_scope in expected_grade_map:
        missing_grades = sorted(expected_grade_map[grade_scope] - set(grades))
        if missing_grades:
            issues.append(f"missing_grades:{','.join(missing_grades)}")
            suggestions.append("检查 OCR 输出是否丢失整段年级")

    if grade_scope in expected_subject_map:
        missing_subjects = sorted(expected_subject_map[grade_scope] - set(subjects))
        if missing_subjects:
            issues.append(f"missing_subjects:{','.join(missing_subjects)}")
            suggestions.append("检查模型输出或切换 Qwen 后备模型")

    by_subject_grade = {(norm(item.get('subject')), norm(item.get('grade'))): item for item in entries}
    if grade_scope == "highschool":
        for subject in expected_subject_map[grade_scope]:
            for grade in expected_grade_map[grade_scope]:
                if (subject, grade) not in by_subject_grade and subject in subjects:
                    issues.append(f"missing_entry:{subject}-{grade}")

    missing_final_ratio = 0.0
    if entries:
        missing_final_count = sum(1 for item in entries if ((item.get("final") or {}).get("status") != "explicit"))
        missing_final_ratio = missing_final_count / len(entries)
        if missing_final_ratio >= 0.6:
            issues.append("too_many_missing_final")
            suggestions.append("检查期末列是否整体错位或被截断")

    risk_level = "low"
    if any(i.startswith("missing_grades:") or i.startswith("missing_subjects:") or i == "entries=0" for i in issues):
        risk_level = "high"
    elif issues:
        risk_level = "medium"

    return {
        "pass": not any(i in {"entries=0", "grades=0", "subjects=0", "exam_nodes=0"} or i.startswith("missing_grades:") or i.startswith("missing_subjects:") for i in issues),
        "risk_level": risk_level,
        "issues": issues,
        "suggestions": suggestions,
        "counts": {
            "entries": len(entries),
            "grades": len(grades),
            "subjects": len(subjects),
            "explicit_midterm": explicit_mid,
            "explicit_final": explicit_final,
            "missing_final_ratio": round(missing_final_ratio, 3),
        },
    }


def merge_meta_warnings(parsed: dict, city: str, academic_year: str, semester: str, grade_scope: str) -> None:
    meta = parsed.get("meta") or {}
    warnings = parsed.setdefault("warnings", [])
    checks = [
        ("city", city),
        ("academic_year", academic_year),
        ("semester", semester),
        ("grade_scope", grade_scope),
    ]
    for key, expected in checks:
        actual = norm(meta.get(key))
        if actual and norm(expected) and actual != norm(expected):
            warnings.append(f"meta_mismatch:{key} detected={actual} expected={expected}")


def resolve_preferred_value(cli_value: str, detected_value: str, *, field_name: str, warnings: list[str]) -> str:
    cli = norm(cli_value)
    detected = norm(detected_value)
    if cli and detected and cli != detected:
        warnings.append(f"meta_override:{field_name} cli={cli} detected={detected}")
        return cli
    return cli or detected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--city", default="")
    parser.add_argument("--academic-year", default="")
    parser.add_argument("--semester", default="")
    parser.add_argument("--grade-scope", default="")
    parser.add_argument("--seed-file", default="", help="Use prepared JSON/Markdown extraction as seed input")
    parser.add_argument("--ocr-seed-file", default="", help="Use OCR-table parser output JSON as seed input")
    parser.add_argument("--try-qwen-table", action="store_true", help="Try Qwen markdown-table OCR before other fallbacks")
    parser.add_argument("--qwen-model", default="Qwen/Qwen2.5-VL-32B-Instruct")
    parser.add_argument("--qwen-fallback-model", default="Qwen/Qwen2.5-VL-72B-Instruct")
    parser.add_argument("--try-ocr", action="store_true", help="Try legacy OCR JSON extraction when other seeds are unavailable")
    parser.add_argument("--status", default="active")
    parser.add_argument("--set-default-context", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    source_file = Path(args.source_file).expanduser().resolve()
    seed_file = Path(args.seed_file).expanduser().resolve() if norm(args.seed_file) else None
    ocr_seed_file = Path(args.ocr_seed_file).expanduser().resolve() if norm(args.ocr_seed_file) else None

    if not source_file.exists():
        raise SystemExit(f"source file not found: {source_file}")
    if seed_file and not seed_file.exists():
        raise SystemExit(f"seed file not found: {seed_file}")
    if ocr_seed_file and not ocr_seed_file.exists():
        raise SystemExit(f"ocr seed file not found: {ocr_seed_file}")
    if not any([seed_file, ocr_seed_file, args.try_qwen_table, args.try_ocr]):
        raise SystemExit("provide --seed-file / --ocr-seed-file or enable --try-qwen-table / --try-ocr")

    requested_city = norm(args.city)
    requested_academic_year = norm(args.academic_year)
    requested_semester = normalize_semester(args.semester) if norm(args.semester) else ""
    requested_grade_scope = normalize_grade_scope(args.grade_scope) if norm(args.grade_scope) else ""

    parsed = None
    seed_source = ""

    qwen_info = {
        "attempted": False,
        "succeeded": False,
        "model_used": "",
        "attempts": [],
        "error": "",
    }
    if args.try_qwen_table:
        parsed, qwen_info = try_qwen_table_extraction(source_file, args.qwen_model, args.qwen_fallback_model)
        if parsed is not None:
            seed_source = "qwen_table"

    ocr_info = {
        "attempted": False,
        "succeeded": False,
        "error": "",
    }
    if parsed is None and args.try_ocr:
        ocr_info["attempted"] = True
        try:
            payload = run_ocr_to_json(source_file)
            parsed = {
                "doc_type": norm(payload.get("doc_type")) or "teaching_progress_total_table",
                "entries": build_entries_from_json(payload),
                "notes": payload.get("notes") or [],
                "warnings": payload.get("warnings") or [],
                "meta": {
                    "city": norm(payload.get("city")),
                    "academic_year": norm(payload.get("academic_year")),
                    "semester": norm(payload.get("semester")),
                    "grade_scope": norm(payload.get("grade_scope")),
                    "title": "",
                },
            }
            ocr_info["succeeded"] = True
            seed_source = "ocr_json"
        except Exception as exc:
            ocr_info["error"] = str(exc)

    if parsed is None and ocr_seed_file:
        parsed = parse_seed_json(ocr_seed_file)
        seed_source = "ocr_seed_file"

    if parsed is None and seed_file:
        parsed = parse_seed(seed_file)
        seed_source = "seed_file"

    if parsed is None:
        raise SystemExit("no parsed payload available")

    meta = parsed.get("meta") or {}
    warning_list = parsed.setdefault("warnings", [])
    city = resolve_preferred_value(requested_city, meta.get("city", ""), field_name="city", warnings=warning_list)
    academic_year = resolve_preferred_value(requested_academic_year, meta.get("academic_year", ""), field_name="academic_year", warnings=warning_list)
    semester = resolve_preferred_value(requested_semester, normalize_semester(meta.get("semester", "")), field_name="semester", warnings=warning_list)
    grade_scope = resolve_preferred_value(requested_grade_scope, normalize_grade_scope(meta.get("grade_scope", "")), field_name="grade_scope", warnings=warning_list)

    missing_meta = []
    if not city:
        missing_meta.append("city")
    if not academic_year:
        missing_meta.append("academic_year")
    if not semester:
        missing_meta.append("semester")
    if not grade_scope:
        missing_meta.append("grade_scope")
    if missing_meta:
        raise SystemExit(f"missing metadata after auto-detection: {', '.join(missing_meta)}")

    paths = build_paths(city, academic_year, semester, grade_scope, source_file)
    copy_to_archive(source_file, paths["archive_path"])

    merge_meta_warnings(parsed, city, academic_year, semester, grade_scope)
    validation = validate_entries(parsed["entries"], grade_scope=grade_scope)
    if not validation["pass"]:
        raise SystemExit(json.dumps(validation, ensure_ascii=False, indent=2))

    final_status, status_reason = decide_record_status(args.status, validation)

    write_record(
        city=city,
        academic_year=academic_year,
        semester=semester,
        grade_scope=grade_scope,
        archive_path=paths["archive_path"],
        extracted_path=paths["extracted_path"],
        doc_type=parsed["doc_type"],
        entries=parsed["entries"],
        notes=parsed.get("notes") or [],
        warnings=parsed.get("warnings") or [],
        status=final_status,
    )

    upsert = run_script(
        "upsert_progress_record.py",
        [
            "--catalog",
            str(CATALOG_PATH.relative_to(WORKSPACE_ROOT)),
            "--city",
            city,
            "--academic-year",
            academic_year,
            "--semester",
            semester,
            "--grade-scope",
            grade_scope,
            "--source-path",
            str(paths["archive_path"].relative_to(WORKSPACE_ROOT)),
            "--source-name",
            paths["archive_path"].name,
            "--extracted-path",
            str(paths["extracted_path"].relative_to(WORKSPACE_ROOT)),
            "--report-path",
            str(paths["report_path"].relative_to(WORKSPACE_ROOT)),
            "--kind",
            parsed["doc_type"],
            "--status",
            final_status,
        ],
    )

    context_updated = False
    if args.set_default_context:
        run_script(
            "set_progress_context.py",
            [
                "--city",
                city,
                "--academic-year",
                academic_year,
                "--semester",
                semester,
                "--grade-scope",
                grade_scope,
                "--out",
                str(CONTEXT_PATH.relative_to(WORKSPACE_ROOT)),
            ],
        )
        context_updated = True

    review_checklist = {"generated": False, "path": "", "items": [], "actions": []}
    if final_status == "draft":
        validation_tmp = REVIEW_DIR / "_validation_tmp.json"
        validation_tmp.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
        review_proc = run_script(
            "generate_review_checklist.py",
            [
                "--city", city,
                "--academic-year", academic_year,
                "--semester", semester,
                "--grade-scope", grade_scope,
                "--validation-json", str(validation_tmp.relative_to(WORKSPACE_ROOT)),
                "--out-dir", str(REVIEW_DIR.relative_to(WORKSPACE_ROOT)),
            ],
        )
        review_path = review_proc.stdout.strip()
        review_items = list(validation.get("issues") or [])
        review_actions = list(validation.get("suggestions") or [])
        if not review_actions:
            review_actions = [
                "检查缺失学科/年级是否为原表确实不存在",
                "若为 OCR 漏识别，尝试切换后备模型后重跑",
                "确认无误后再转 active",
            ]
        review_checklist = {
            "generated": True,
            "path": review_path,
            "items": review_items,
            "actions": review_actions,
        }

    render_args = [
        "--json",
        str(paths["extracted_path"].relative_to(WORKSPACE_ROOT)),
        "--out",
        str(paths["report_path"].relative_to(WORKSPACE_ROOT)),
    ]
    if review_checklist.get("generated"):
        review_json_path = REVIEW_DIR / "_review_checklist_tmp.json"
        review_json_path.write_text(json.dumps(review_checklist, ensure_ascii=False, indent=2), encoding="utf-8")
        render_args.extend([
            "--review-json",
            str(review_json_path.relative_to(WORKSPACE_ROOT)),
        ])
    run_script("render_progress_summary.py", render_args)

    upsert_result = json.loads(upsert.stdout)
    result = {
        "status": "ok",
        "input": {
            "source_file": str(source_file),
            "ocr_seed_file": str(ocr_seed_file) if ocr_seed_file else "",
            "seed_file": str(seed_file) if seed_file else "",
        },
        "normalized": {
            "city": city,
            "academic_year": academic_year,
            "semester": semester,
            "grade_scope": grade_scope,
        },
        "paths": {
            "archive_path": str(paths["archive_path"].relative_to(WORKSPACE_ROOT)),
            "extracted_path": str(paths["extracted_path"].relative_to(WORKSPACE_ROOT)),
            "report_path": str(paths["report_path"].relative_to(WORKSPACE_ROOT)),
            "catalog_path": str(CATALOG_PATH.relative_to(WORKSPACE_ROOT)),
            "context_path": str(CONTEXT_PATH.relative_to(WORKSPACE_ROOT)),
        },
        "validation": validation,
        "decision": {
            "requested_status": norm(args.status) or "active",
            "final_status": final_status,
            "reason": status_reason,
        },
        "catalog": upsert_result,
        "review_checklist": review_checklist,
        "qwen": qwen_info,
        "ocr": ocr_info,
        "quality": parsed.get("quality") or qwen_info.get("quality") or {},
        "seed_source": seed_source,
        "context_updated": context_updated,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
