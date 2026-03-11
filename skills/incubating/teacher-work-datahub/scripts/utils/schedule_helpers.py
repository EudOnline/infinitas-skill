#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课表通用辅助函数：
- 科目别名匹配（含单双周 A/B）
- 作息时间读取（config/semester_schedule.json）
- 课表/配备表读取与教师推断
- 数据源追溯
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


def norm(s: str) -> str:
    if s is None:
        return ""
    return str(s).strip()


def normalize_subject_name(subject: str) -> str:
    return norm(subject).replace("／", "/").replace(" ", "")


def aliases_map() -> Dict[str, set[str]]:
    english = {"英语", "外语", "英"}
    info = {"信息", "信息技术", "信"}
    general_tech = {"通用", "通用技术", "通"}
    return {
        "物理": {"物理", "物"},
        "化学": {"化学", "化"},
        "生物": {"生物", "生"},
        "政治": {"政治", "政"},
        "语文": {"语文", "语"},
        "数学": {"数学", "数"},
        "英语": english,
        "外语": english,
        "历史": {"历史", "史"},
        "地理": {"地理", "地"},
        "实验": {"实验", "实"},
        "信息": info,
        "信息技术": info,
        "通用": general_tech,
        "通用技术": general_tech,
        "体育": {"体育", "体"},
        "美术": {"美术", "美"},
        "音乐": {"音乐", "音"},
        "心理": {"心理", "心"},
    }


def has_subject(value: str, subject: str, week_parity: str) -> bool:
    """week_parity: single|double|all"""
    if not value:
        return False

    t = normalize_subject_name(value)
    subject = normalize_subject_name(subject)

    target = aliases_map().get(subject, {subject})

    candidates = [t]
    if "/" in t:
        parts = [x.strip() for x in t.split("/") if x.strip()]
        if week_parity == "single":
            candidates = [parts[0]] if len(parts) >= 1 else []
        elif week_parity == "double":
            candidates = [parts[1]] if len(parts) >= 2 else []
        else:
            candidates = parts

    for c in candidates:
        if c in target:
            return True
        if any(len(x) > 1 and x in c for x in target):
            return True
    return False


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_slot_time_map(config_path: Path) -> Dict[str, str]:
    """从 config/semester_schedule.json 读取标准作息。"""
    cfg = load_json(config_path)

    mapping = {}

    # morning/afternoon
    for item in cfg.get("daily_schedule", {}).get("morning", []):
        name = norm(item.get("name"))
        t = norm(item.get("time"))
        if name.startswith("第一节课"):
            mapping["1"] = t
        elif name.startswith("第二节课"):
            mapping["2"] = t
        elif name.startswith("第三节课"):
            mapping["3"] = t
        elif name.startswith("第四节课"):
            mapping["4"] = t

    for item in cfg.get("daily_schedule", {}).get("afternoon", []):
        name = norm(item.get("name"))
        t = norm(item.get("time"))
        if name.startswith("第五节课"):
            mapping["5"] = t
        elif name.startswith("第六节课"):
            mapping["6"] = t
        elif name.startswith("第七节课"):
            mapping["7"] = t

    # evening self-study
    for item in cfg.get("daily_schedule", {}).get("evening", []):
        name = norm(item.get("name"))
        t = norm(item.get("time"))
        if name == "自习1":
            mapping["晚1"] = t
        elif name == "自习2":
            mapping["晚2"] = t
        elif name == "自习3":
            mapping["晚3"] = t
        elif name == "自习4":
            mapping["晚4"] = t

    # ensure required keys (strict, but allow empty string for unknown)
    required = ["1", "2", "3", "4", "5", "6", "7", "晚1", "晚2", "晚3", "晚4"]
    for k in required:
        mapping.setdefault(k, "")

    return mapping


def collect_classes(schedule_json: dict) -> List[str]:
    classes = set()
    for sh in schedule_json.get("sheets", []):
        for c in sh.get("classes", []):
            cls = c.get("class")
            if cls:
                classes.add(cls)
    return sorted(classes)


def schedule_has_class(schedule_json: dict, class_name: str) -> bool:
    return class_name in set(collect_classes(schedule_json))


def schedule_has_evening_slots(schedule_json: dict) -> bool:
    evening_slots = {"晚1", "晚2", "晚3", "晚4"}
    for sh in schedule_json.get("sheets", []):
        for c in sh.get("classes", []):
            schedule = c.get("schedule", {})
            if not isinstance(schedule, dict):
                continue
            if evening_slots.intersection(schedule.keys()):
                return True
    return False


def extract_schedule_map(schedule_json: dict, classes: List[str]) -> Dict[str, dict]:
    out = {}
    target = set(classes)
    for sh in schedule_json.get("sheets", []):
        for c in sh.get("classes", []):
            cls = c.get("class")
            if cls in target:
                out[cls] = c.get("schedule", {})
    return out


def clean_teacher_name(s: str) -> str:
    # 与旧版教师配备解析清洗口径保持一致
    return norm(s).replace(" ", "").replace("\u3000", "").replace("—", "").replace("→", "").replace("-", "")


@dataclass
class TeacherInference:
    requested_teacher: str
    matched_teacher: str
    teacher_fallback_used: bool
    teacher_fallback_note: str
    subjects: List[str]
    classes: List[str]
    grade_labels: List[str]
    evidence: List[dict]
    sheet_scope: str
    sheet_scope_note: str
    ambiguity_detected: bool
    ambiguity_note: str
    ambiguity_options: List[dict]
    disambiguation_used: bool
    disambiguation_note: str


def normalize_sheet_name(sheet_name: str) -> str:
    return norm(sheet_name).replace(" ", "")


def is_current_named_sheet(sheet_name: str) -> bool:
    s = normalize_sheet_name(sheet_name)
    return bool(re.fullmatch(r"\d{4}\.\d{1,2}", s))


def summarize_teacher_option(clean_name: str, evidence: List[dict]) -> dict:
    classes = sorted({f"{norm(x.get('class'))}班" for x in evidence if norm(x.get("class"))})
    subjects = sorted(
        {
            norm(x.get("subject"))
            for x in evidence
            if norm(x.get("subject")) and norm(x.get("subject")) != "班主任"
        }
    )
    sheets = sorted({normalize_sheet_name(x.get("sheet")) for x in evidence if normalize_sheet_name(x.get("sheet"))})
    return {
        "matched_teacher": clean_name,
        "classes": classes,
        "subjects": subjects,
        "sheets": sheets,
        "evidence_count": len(evidence),
    }


def normalize_class_name(class_name: str) -> str:
    txt = norm(class_name).replace(" ", "")
    if not txt:
        return ""
    if txt.endswith("班"):
        return txt
    return f"{txt}班"


def parse_hint_list(raw: str, *, kind: str) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"[，,、/；;\s]+", raw)
    out = []
    for item in parts:
        v = norm(item)
        if not v:
            continue
        if kind == "class":
            v = normalize_class_name(v)
        out.append(v)
    return sorted(set(out))


def candidate_match_score(option: dict, class_hints: List[str], subject_hints: List[str]) -> tuple[int, int, int]:
    option_classes = set(option.get("classes") or [])
    option_subjects = set(option.get("subjects") or [])
    class_hit = len(option_classes.intersection(class_hints)) if class_hints else 0
    subject_hit = len(option_subjects.intersection(subject_hints)) if subject_hints else 0
    # 分数优先级：班级命中 > 学科命中 > 候选更精确（证据更少）
    return (class_hit, subject_hit, -int(option.get("evidence_count") or 0))


def extract_class_hints_from_text(text: str) -> List[str]:
    if not text:
        return []
    matches = re.findall(r"(?<!\d)(\d{4})(?:班)?", text)
    return sorted({f"{m}班" for m in matches})


def extract_subject_hints_from_text(text: str) -> List[str]:
    if not text:
        return []
    normalized = normalize_subject_name(text)
    canonical_order = [
        "语文",
        "数学",
        "英语",
        "外语",
        "物理",
        "化学",
        "生物",
        "政治",
        "历史",
        "地理",
        "实验",
        "信息",
        "信息技术",
        "通用",
        "通用技术",
        "体育",
        "美术",
        "音乐",
        "心理",
    ]
    out = []
    amap = aliases_map()
    for canonical in canonical_order:
        aliases = sorted([x for x in amap.get(canonical, {canonical}) if len(x) >= 2], key=len, reverse=True)
        if any(alias in normalized for alias in aliases):
            out.append(canonical)
    return sorted(set(out))


def extract_teacher_from_request_text(teacher_allocation_json: dict, text: str, class_hints: List[str], subject_hints: List[str]) -> str:
    idx = teacher_allocation_json.get("focus_grade_teacher_index", {}) or {}
    single_names = [k for k in idx.keys() if not is_composite_teacher_key(k)]
    cleaned_text = clean_teacher_name(text)

    explicit = [k for k in single_names if k and k in cleaned_text]
    if explicit:
        explicit.sort(key=lambda x: (-len(x), x))
        return explicit[0]

    work = cleaned_text
    for cls in class_hints:
        work = work.replace(clean_teacher_name(cls), "")
        work = work.replace(clean_teacher_name(cls).replace("班", ""), "")
    for subj in subject_hints:
        work = work.replace(clean_teacher_name(subj), "")

    stop_phrases = [
        "给我",
        "发我",
        "帮我",
        "请",
        "生成",
        "制作",
        "导出",
        "出一份",
        "学期课表",
        "周课表",
        "个人课表",
        "课表",
        "课程表",
        "老师",
        "当前",
        "查询",
        "查一下",
        "查下",
        "看一下",
        "看下",
        "一下",
        "的",
    ]
    for phrase in stop_phrases:
        work = work.replace(clean_teacher_name(phrase), "")

    work = re.sub(r"[0-9]+", "", work)
    work = work.strip()
    return work


def detect_schedule_type_from_text(text: str) -> str:
    t = norm(text)
    if "周课表" in t or "单周" in t or "双周" in t:
        return "week"
    if "学期课表" in t:
        return "semester"
    return "semester"


def detect_week_parity_from_text(text: str) -> str:
    t = norm(text)
    if "单周" in t:
        return "single"
    if "双周" in t:
        return "double"
    return ""


def detect_output_format_from_text(text: str) -> str:
    t = norm(text).lower()
    if "pdf" in t or "PDF" in text:
        return "pdf"
    return "image"


def detect_send_from_text(text: str) -> bool:
    t = norm(text)
    keywords = ["发我", "发给我", "发送", "发到飞书", "发到群里", "直接发", "给我发"]
    return any(k in t for k in keywords)


def parse_teacher_request_text(teacher_allocation_json: dict, text: str) -> dict:
    class_hints = extract_class_hints_from_text(text)
    subject_hints = extract_subject_hints_from_text(text)
    teacher = extract_teacher_from_request_text(teacher_allocation_json, text, class_hints, subject_hints)
    return {
        "request_text": text,
        "teacher": teacher,
        "class_hints": class_hints,
        "subject_hints": subject_hints,
        "schedule_type": detect_schedule_type_from_text(text),
        "week_parity": detect_week_parity_from_text(text),
        "output_format": detect_output_format_from_text(text),
        "send_requested": detect_send_from_text(text),
        "auto_parse_used": bool(text),
    }


def find_teacher_candidates(idx: Dict[str, List[dict]], cleaned_target: str) -> List[str]:
    candidates = []
    for k in idx.keys():
        if cleaned_target and (cleaned_target in k or k in cleaned_target):
            candidates.append(k)
    # 优先更短、更接近的名字，保证稳定性
    candidates.sort(key=lambda x: (x != cleaned_target, abs(len(x) - len(cleaned_target)), len(x), x))
    return candidates


def is_composite_teacher_key(clean_name: str) -> bool:
    return any(sep in clean_name for sep in ["、", "，", ",", "/", "＋", "+", "和", "与"])


def teacher_evidence_currentness_score(item: dict) -> tuple[int, int, str]:
    sheet = normalize_sheet_name(item.get("sheet"))
    # 当前命名 sheet（如 2026.3）优先；其次按数字年月倒序；最后按原始名字兜底
    current_named = 1 if is_current_named_sheet(sheet) else 0
    m = re.fullmatch(r"(\d{4})\.(\d{1,2})", sheet)
    stamp = 0
    if m:
        stamp = int(m.group(1)) * 100 + int(m.group(2))
    return (current_named, stamp, sheet)


def select_preferred_teacher_evidence(evidence: List[dict]) -> tuple[List[dict], str, str]:
    if not evidence:
        return [], "", ""

    scored = [teacher_evidence_currentness_score(item) for item in evidence]
    best = max(scored)
    preferred_sheet = best[2]

    # 若存在当前命名 sheet，优先只取该 sheet；否则保留全部证据
    if best[0] == 1 and preferred_sheet:
        filtered = [item for item in evidence if normalize_sheet_name(item.get("sheet")) == preferred_sheet]
        # 仅在收敛后仍有至少一条任课学科（非班主任）时才启用收敛，避免把测试/补丁证据误裁掉
        has_teaching_subject = any(norm(item.get("subject")) and norm(item.get("subject")) != "班主任" for item in filtered)
        if filtered and has_teaching_subject:
            if len(filtered) < len(evidence):
                return filtered, preferred_sheet, f"已按当前配备表 sheet 收敛：仅使用 {preferred_sheet}，未并入历史/其他 sheet。"
            return filtered, preferred_sheet, ""

    # 无可用当前命名 sheet 任课证据时，回退保留全部证据

    return evidence, preferred_sheet, ""


def infer_teacher_classes_subjects(
    teacher_allocation_json: dict,
    teacher: str,
    *,
    class_hint: str = "",
    subject_hint: str = "",
) -> TeacherInference:
    """
    从 teacher_allocation 的 focus_grade_teacher_index 推断：
    - 教师匹配（精确或容错）
    - 任教学科
    - 任教班级
    - 优先收敛到当前命名 sheet（如 2026.3），避免历史班级混入当前交付
    - 当简称命中多个老师时，优先用班级/学科提示消歧；仍无法唯一确定时再拦截
    """
    idx = teacher_allocation_json.get("focus_grade_teacher_index", {}) or {}

    cleaned_target = clean_teacher_name(teacher)
    matched_key = None
    ambiguity_detected = False
    ambiguity_note = ""
    ambiguity_options: List[dict] = []
    disambiguation_used = False
    disambiguation_note = ""

    class_hints = parse_hint_list(class_hint, kind="class")
    subject_hints = parse_hint_list(subject_hint, kind="subject")

    # 1) 精确命中（清洗后 key）
    if cleaned_target in idx:
        matched_key = cleaned_target
    else:
        candidates = find_teacher_candidates(idx, cleaned_target)
        # 优先单人教师名；若只剩一个单人候选，则可安全容错
        single_candidates = [k for k in candidates if not is_composite_teacher_key(k)]
        candidate_keys = single_candidates if single_candidates else candidates

        if len(candidate_keys) == 1:
            matched_key = candidate_keys[0]
        elif len(candidate_keys) > 1:
            options = [summarize_teacher_option(k, idx.get(k, [])) for k in candidate_keys[:8]]
            scored = [(candidate_match_score(opt, class_hints, subject_hints), opt) for opt in options]
            best_score = max(score for score, _ in scored)
            winners = [opt for score, opt in scored if score == best_score]

            if (best_score[0] > 0 or best_score[1] > 0) and len(winners) == 1:
                matched_key = winners[0]["matched_teacher"]
                disambiguation_used = True
                hint_parts = []
                if class_hints:
                    hint_parts.append(f"班级={','.join(class_hints)}")
                if subject_hints:
                    hint_parts.append(f"学科={','.join(subject_hints)}")
                disambiguation_note = f"已按提示条件自动消歧：{teacher} -> {matched_key}（{'；'.join(hint_parts)}）"
            else:
                ambiguity_detected = True
                ambiguity_options = options
                hint_note = ""
                if class_hints or subject_hints:
                    hint_bits = []
                    if class_hints:
                        hint_bits.append(f"班级={','.join(class_hints)}")
                    if subject_hints:
                        hint_bits.append(f"学科={','.join(subject_hints)}")
                    hint_note = f"（已尝试按{'；'.join(hint_bits)}消歧，仍不唯一）"
                ambiguity_note = (
                    f"教师名存在歧义：{teacher} 可匹配 {', '.join(x['matched_teacher'] for x in ambiguity_options)}；"
                    f"请提供更完整姓名或指定班级/学科。{hint_note}"
                )

    if not matched_key:
        return TeacherInference(
            requested_teacher=teacher,
            matched_teacher="",
            teacher_fallback_used=False,
            teacher_fallback_note=ambiguity_note,
            subjects=[],
            classes=[],
            grade_labels=[],
            evidence=[],
            sheet_scope="",
            sheet_scope_note="",
            ambiguity_detected=ambiguity_detected,
            ambiguity_note=ambiguity_note,
            ambiguity_options=ambiguity_options,
            disambiguation_used=disambiguation_used,
            disambiguation_note=disambiguation_note,
        )

    all_evidence = idx.get(matched_key, [])
    evidence, sheet_scope, sheet_scope_note = select_preferred_teacher_evidence(all_evidence)

    subjects = sorted(
        {
            norm(x.get("subject"))
            for x in evidence
            if norm(x.get("subject")) and norm(x.get("subject")) != "班主任"
        }
    )
    classes = sorted({f"{norm(x.get('class'))}班" for x in evidence if norm(x.get("class"))})

    # 年级标签来自 sections classes 映射
    class_to_grade = {}
    for sobj in teacher_allocation_json.get("sheets", {}).values():
        for section in sobj.get("sections", []):
            for c in section.get("classes", []):
                cls = norm(c.get("class"))
                grd = norm(c.get("grade"))
                if cls:
                    class_to_grade[cls] = grd

    grade_labels = sorted({class_to_grade.get(norm(x.get("class")), "") for x in evidence if norm(x.get("class"))})
    grade_labels = [g for g in grade_labels if g]

    teacher_fallback_used = matched_key != cleaned_target
    note_parts = []
    if teacher_fallback_used:
        note_parts.append(f"已按容错名处理：{teacher} -> {matched_key}")
    if disambiguation_note:
        note_parts.append(disambiguation_note)
    if sheet_scope_note:
        note_parts.append(sheet_scope_note)
    note = "；".join(note_parts)

    return TeacherInference(
        requested_teacher=teacher,
        matched_teacher=matched_key,
        teacher_fallback_used=teacher_fallback_used,
        teacher_fallback_note=note,
        subjects=subjects,
        classes=classes,
        grade_labels=grade_labels,
        evidence=evidence,
        sheet_scope=sheet_scope,
        sheet_scope_note=sheet_scope_note,
        ambiguity_detected=False,
        ambiguity_note="",
        ambiguity_options=[],
        disambiguation_used=disambiguation_used,
        disambiguation_note=disambiguation_note,
    )


def choose_primary_subject(subjects: List[str], preferred: str = "") -> str:
    if preferred and preferred in subjects:
        return preferred

    # 学科优先级（可按学校场景继续调整）
    priority = ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理", "实验"]
    for s in priority:
        if s in subjects:
            return s

    return subjects[0] if subjects else ""


def map_grade_label_to_title(grade_labels: List[str], default_title: str = "2025-2026第二学年") -> str:
    # 配备表里的年级标题常带大量空格，如“高  二  年   级”，先压缩空白再匹配。
    txt = "".join(norm(x).replace(" ", "").replace("\u3000", "") for x in grade_labels)
    if "高一" in txt:
        return f"{default_title}高一年级"
    if "高二" in txt:
        return f"{default_title}高二年级"
    if "高三" in txt:
        return f"{default_title}高三年级"
    return default_title


def resolve_source_trace(catalog: dict, semester: str, kind: str) -> dict:
    idx = catalog.get("active_index", {})
    rid = idx.get(semester, {}).get(kind)
    records = catalog.get("records", [])
    rec = next((r for r in records if r.get("record_id") == rid), None)
    if not rec:
        return {
            "semester": semester,
            "kind": kind,
            "record_id": "",
            "source_name": "",
            "archived_path": "",
            "status": "",
        }
    return {
        "semester": semester,
        "kind": kind,
        "record_id": rec.get("record_id", ""),
        "source_name": rec.get("source_name", ""),
        "archived_path": rec.get("archived_path", ""),
        "status": rec.get("status", ""),
    }


def compare_class_sets(schedule_json: dict, teacher_allocation_json: dict) -> dict:
    """
    增强项：课表班级集合 vs 配备表班级集合 对照告警。
    """
    sched = set(collect_classes(schedule_json))

    alloc = set()
    for sobj in teacher_allocation_json.get("sheets", {}).values():
        for section in sobj.get("sections", []):
            for c in section.get("classes", []):
                cls = norm(c.get("class"))
                if cls:
                    alloc.add(f"{cls}班")

    only_in_schedule = sorted(sched - alloc)
    only_in_allocation = sorted(alloc - sched)

    return {
        "schedule_class_count": len(sched),
        "allocation_class_count": len(alloc),
        "only_in_schedule": only_in_schedule,
        "only_in_allocation": only_in_allocation,
    }


def compute_subject_hit_count(schedule_map: Dict[str, dict], classes: List[str], subject: str, week_parity: str = "all") -> int:
    days = ["一", "二", "三", "四", "五"]
    slots = ["1", "2", "3", "4", "5", "6", "7", "晚1", "晚2", "晚3", "晚4"]
    cnt = 0
    parity = week_parity if week_parity in {"single", "double", "all"} else "all"
    for cls in classes:
        cls_map = schedule_map.get(cls, {})
        for slot in slots:
            dm = cls_map.get(slot, {})
            if not isinstance(dm, dict):
                continue
            for d in days:
                v = dm.get(d, "")
                if parity == "all":
                    if has_subject(v, subject, "single") or has_subject(v, subject, "double"):
                        cnt += 1
                else:
                    if has_subject(v, subject, parity):
                        cnt += 1
    return cnt
