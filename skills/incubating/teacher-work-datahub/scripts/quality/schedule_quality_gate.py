#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课表解析质量门禁：
- class_count > 0
- 目标班级命中（可选）
- 目标教师任教班级命中（可选，基于 teacher_allocation 结果）

失败则非0退出，阻断后续出图流程。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def collect_classes(schedule_json: dict) -> set[str]:
    classes = set()
    for sh in schedule_json.get("sheets", []):
        for c in sh.get("classes", []):
            cls = c.get("class")
            if cls:
                classes.add(cls)
    return classes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule-json", required=True)
    ap.add_argument("--expect-classes", default="", help="逗号分隔，如 2504班,2505班")
    ap.add_argument(
        "--teacher-allocation-json",
        default="",
        help="teacher_allocation 解析 JSON（可选）",
    )
    ap.add_argument(
        "--teacher",
        default="",
        help="教师名（可选，需配合 --teacher-allocation-json）",
    )
    args = ap.parse_args()

    schedule_path = Path(args.schedule_json)
    if not schedule_path.exists():
        print(f"[FAIL] schedule_json 不存在: {schedule_path}")
        sys.exit(2)

    sched = json.loads(schedule_path.read_text(encoding="utf-8"))
    classes = collect_classes(sched)

    if not classes:
        print("[FAIL] class_count=0，解析结果为空")
        sys.exit(3)

    expect = [x.strip() for x in args.expect_classes.split(",") if x.strip()]
    if expect:
        missing = [c for c in expect if c not in classes]
        if missing:
            print(f"[FAIL] 目标班级未命中: {missing}")
            print(f"[INFO] 当前解析班级数: {len(classes)}")
            sys.exit(4)

    if args.teacher and args.teacher_allocation_json:
        tp = Path(args.teacher_allocation_json)
        if not tp.exists():
            print(f"[FAIL] teacher_allocation_json 不存在: {tp}")
            sys.exit(5)
        tdata = json.loads(tp.read_text(encoding="utf-8"))
        tq = tdata.get("teacher_query", {})
        matches = tq.get("matches", []) if tq else []
        if not matches:
            # 兼容没有 --teacher 查询的文件
            idx = tdata.get("focus_grade_teacher_index", {})
            # 简单清洗匹配
            clean = args.teacher.replace(" ", "").replace("—", "").replace("→", "")
            matches = idx.get(clean, []) if isinstance(idx, dict) else []

        if not matches:
            print(f"[FAIL] 教师未命中: {args.teacher}")
            sys.exit(6)

    print(f"[PASS] class_count={len(classes)}")
    if expect:
        print(f"[PASS] expect_classes 命中: {expect}")
    if args.teacher:
        print(f"[PASS] teacher 命中: {args.teacher}")


if __name__ == "__main__":
    main()
