#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课表版本差异摘要（班级/节次/星期维度）。

输入：两个统一结构的课表 JSON（均含 sheets/classes/schedule）。
输出：JSON 摘要，包含新增/移除班级、变更单元格统计与明细。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def norm(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def build_class_map(data: dict) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for sh in data.get("sheets", []):
        for c in sh.get("classes", []):
            cls = c.get("class")
            if not cls:
                continue
            # 后出现的覆盖前出现的
            out[cls] = c.get("schedule", {})
    return out


def iter_cells(schedule: dict) -> List[Tuple[str, str]]:
    keys = []
    for slot, day_map in schedule.items():
        if not isinstance(day_map, dict):
            continue
        for day in day_map.keys():
            keys.append((str(slot), str(day)))
    return sorted(set(keys))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-json", required=True)
    ap.add_argument("--new-json", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--old-label", default="old")
    ap.add_argument("--new-label", default="new")
    args = ap.parse_args()

    old_path = Path(args.old_json)
    new_path = Path(args.new_json)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    old_data = json.loads(old_path.read_text(encoding="utf-8"))
    new_data = json.loads(new_path.read_text(encoding="utf-8"))

    old_map = build_class_map(old_data)
    new_map = build_class_map(new_data)

    old_classes = set(old_map.keys())
    new_classes = set(new_map.keys())

    added_classes = sorted(new_classes - old_classes)
    removed_classes = sorted(old_classes - new_classes)
    common_classes = sorted(old_classes & new_classes)

    changed_cells: List[dict] = []
    changed_classes: Dict[str, int] = {}
    changed_slots: Dict[str, set] = {}

    for cls in common_classes:
        o = old_map.get(cls, {})
        n = new_map.get(cls, {})
        keys = sorted(set(iter_cells(o)) | set(iter_cells(n)))

        for slot, day in keys:
            ov = norm(o.get(slot, {}).get(day, "")) if isinstance(o.get(slot, {}), dict) else ""
            nv = norm(n.get(slot, {}).get(day, "")) if isinstance(n.get(slot, {}), dict) else ""
            if ov == nv:
                continue

            changed_cells.append(
                {
                    "class": cls,
                    "slot": slot,
                    "day": day,
                    "old": ov,
                    "new": nv,
                }
            )
            changed_classes[cls] = changed_classes.get(cls, 0) + 1
            changed_slots.setdefault(cls, set()).add(slot)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "old": {"label": args.old_label, "path": str(old_path)},
        "new": {"label": args.new_label, "path": str(new_path)},
        "stats": {
            "old_class_count": len(old_classes),
            "new_class_count": len(new_classes),
            "added_class_count": len(added_classes),
            "removed_class_count": len(removed_classes),
            "changed_class_count": len(changed_classes),
            "changed_cell_count": len(changed_cells),
            "changed_slot_count": sum(len(v) for v in changed_slots.values()),
        },
        "added_classes": added_classes,
        "removed_classes": removed_classes,
        "changed_classes": [
            {
                "class": cls,
                "changed_cells": changed_classes[cls],
                "changed_slots": sorted(changed_slots.get(cls, set())),
            }
            for cls in sorted(changed_classes.keys())
        ],
        "changed_cells": changed_cells,
    }

    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[OK] 输出: {out_path}")
    print(f"[INFO] 新增班级: {len(added_classes)}; 移除班级: {len(removed_classes)}")
    print(f"[INFO] 变更班级: {len(changed_classes)}; 变更单元格: {len(changed_cells)}")


if __name__ == "__main__":
    main()
