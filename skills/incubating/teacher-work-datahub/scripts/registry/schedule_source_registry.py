#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课表/教师配备表源文件归档与台账维护

职责：
1) 将 inbound 目录中的“课表/教师配备一览表”复制到工作区归档目录。
2) 生成结构化台账 data/schedules/catalog/sources.json。
3) 执行默认版本策略：同类型+同学期默认“替换”（仅最新版本 active）。
4) 固化分析优先级：
   - 优先：带自习的年级课表
   - 回退：全校（无自习）课表（当主课表缺失目标班级/教师时）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def detect_kind(name: str) -> str:
    n = name.replace("＋", "+")

    if "配备一览表" in n or "班主任_任课教师配备" in n:
        return "teacher_allocation"

    if "课表" in n:
        if "自习" in n:
            return "grade_schedule_with_selfstudy"
        if "全校" in n or "学年高中课表" in n or "总课表" in n:
            return "school_schedule_no_selfstudy"
        return "class_schedule_unknown"

    return "other"


def detect_semester(name: str) -> str:
    # 用户规则：9月=第一学期；春季=第二学期
    if "第一学期" in name:
        return "S1"
    if "第二学期" in name:
        return "S2"

    if "9月" in name:
        return "S1"

    if "春" in name:
        return "S2"

    # 仅作温和推断；无法确定则返回 unknown，避免猜测
    for m in ["2月", "3月", "4月", "5月", "6月"]:
        if m in name:
            return "S2"

    if "高二上" in name or "上学期" in name:
        return "S1"
    if "高二下" in name or "下学期" in name:
        return "S2"

    return "unknown"


def make_record_id(name: str) -> str:
    h = hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]
    return f"src-{h}"


def load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def ensure_semantic_records(records: List[Dict], old_records: Dict[str, Dict], workspace: Path, now: str) -> None:
    """补齐语义归档课表到台账（解决 active_index 缺口）。"""
    semantic_candidates = [
        {
            "source_name": "semantic::2025-2026-S2-grade10cohort2024-grade11-complete.json",
            "kind": "grade_schedule_with_selfstudy",
            "semester": "S2",
            "path": workspace / "data/schedules/2025-2026-S2-grade10cohort2024-grade11-complete.json",
            "notes": "语义归档课表（带自习，优先用于高二分析）",
        }
    ]

    for item in semantic_candidates:
        p = item["path"]
        if not p.exists():
            continue

        src_name = item["source_name"]
        prev = old_records.get(src_name, {})
        ts = p.stat().st_mtime

        rec = {
            "record_id": prev.get("record_id") or make_record_id(src_name),
            "source_name": src_name,
            "kind": item["kind"],
            "semester": item["semester"],
            "archived_path": str(p.relative_to(workspace)),
            "source_mtime": iso(ts),
            "source_mtime_epoch": int(ts),
            "size_bytes": p.stat().st_size,
            "first_seen": prev.get("first_seen") or iso(ts),
            "last_synced": now,
            "status": "active",
            "superseded_by": None,
            "notes": item["notes"],
            "source_origin": "semantic_archive",
        }

        records.append(rec)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parents[4]),
        help="工作区根目录",
    )
    parser.add_argument(
        "--inbound-dir",
        default=str(Path(__file__).resolve().parents[4].parent / "media" / "inbound"),
        help="OpenClaw inbound 文件目录",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    inbound_dir = Path(args.inbound_dir).resolve()
    archive_dir = workspace / "data/schedules/archive/inbound"
    catalog_path = workspace / "data/schedules/catalog/sources.json"

    archive_dir.mkdir(parents=True, exist_ok=True)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) 归档：复制候选文件（存在则跳过）
    if inbound_dir.exists():
        for p in sorted(inbound_dir.iterdir()):
            if not p.is_file():
                continue
            name = p.name
            if ("课表" not in name) and ("配备一览表" not in name) and ("班主任_任课教师配备" not in name):
                continue
            dst = archive_dir / name
            if not dst.exists():
                shutil.copy2(p, dst)

    old = load_json(catalog_path)
    old_records = {
        r.get("source_name"): r
        for r in old.get("records", [])
        if isinstance(r, dict) and r.get("source_name")
    }

    # 2) 生成 records
    records: List[Dict] = []
    now = datetime.now().isoformat(timespec="seconds")

    # 2.0) 先补齐语义归档记录（非 inbound，但应进入 active_index）
    ensure_semantic_records(records, old_records, workspace, now)

    for p in sorted(archive_dir.iterdir()):
        if not p.is_file():
            continue

        name = p.name
        kind = detect_kind(name)
        if kind == "other":
            continue

        inbound_p = inbound_dir / name
        source_ts = inbound_p.stat().st_mtime if inbound_p.exists() else p.stat().st_mtime

        prev = old_records.get(name, {})

        rec = {
            "record_id": prev.get("record_id") or make_record_id(name),
            "source_name": name,
            "kind": kind,
            "semester": detect_semester(name),
            "archived_path": str(p.relative_to(workspace)),
            "source_mtime": iso(source_ts),
            "source_mtime_epoch": int(source_ts),
            "size_bytes": p.stat().st_size,
            "first_seen": prev.get("first_seen") or iso(p.stat().st_mtime),
            "last_synced": now,
            "status": "active",
            "superseded_by": None,
            "notes": "",
        }
        records.append(rec)

    # 3) 默认替换策略（同 kind + semester 只保留最新 active）
    # 语义归档（source_origin=semantic_archive）优先级高于 inbound 同类源。
    groups: Dict[tuple, List[Dict]] = defaultdict(list)
    for r in records:
        groups[(r["kind"], r["semester"])].append(r)

    for _, lst in groups.items():
        def rank(x: Dict) -> tuple:
            origin_priority = 1 if x.get("source_origin") == "semantic_archive" else 0
            return (origin_priority, x["source_mtime_epoch"], x["source_name"])

        lst.sort(key=rank)
        latest = lst[-1]
        for r in lst:
            if r["record_id"] == latest["record_id"]:
                r["status"] = "active"
                r["superseded_by"] = None
            else:
                r["status"] = "archived"
                r["superseded_by"] = latest["record_id"]
                if r.get("source_origin") == "semantic_archive":
                    r["notes"] = "语义归档被更新版本替代（保留归档）。"
                else:
                    r["notes"] = "同类型同学期旧版本（默认替换策略保留归档，不作为当前生效版本）。"

    # 4) 去掉内部字段并生成 active 索引
    active_index: Dict[str, Dict[str, str]] = defaultdict(dict)
    for r in records:
        if r["status"] == "active":
            active_index[r["semester"]][r["kind"]] = r["record_id"]
        r.pop("source_mtime_epoch", None)

    catalog = {
        "version": "1.2",
        "updated_at": now,
        "policy": {
            "semester_rule": {
                "S1": "9月（第一学期）",
                "S2": "春季（第二学期）",
            },
            "version_strategy_default": "replace_previous",
            "multi_version_behavior": "同类型+同学期保留历史归档，自动切换到最新版本为 active",
            "class_schedule_analysis_priority": [
                "grade_schedule_with_selfstudy",
                "school_schedule_no_selfstudy",
            ],
            "fallback_condition": "目标班级/教师不在带自习年级课表中时，回退使用全校无自习课表",
            "no_guessing": True,
        },
        "active_index": dict(active_index),
        "records": sorted(
            records,
            key=lambda x: (x["kind"], x["semester"], x["source_mtime"], x["source_name"]),
        ),
    }

    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(catalog_path))
    print(f"records={len(records)}")


if __name__ == "__main__":
    main()
