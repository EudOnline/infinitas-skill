#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from catalog_utils import datahub_root, read_json  # noqa: E402


def norm(v: str) -> str:
    return (v or "").strip()


def slug_ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def default_out_dir() -> Path:
    return datahub_root() / "outputs" / "reports" / "teaching-progress" / "review-checklists"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", required=True)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--semester", required=True)
    parser.add_argument("--grade-scope", required=True)
    parser.add_argument("--validation-json", required=True)
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    validation = read_json(Path(args.validation_json), default={}) or {}
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"复核清单-{args.city}-{args.academic_year}-{args.semester}-{slug_ts()}.md"

    issues = validation.get("issues") or []
    suggestions = validation.get("suggestions") or []
    counts = validation.get("counts") or {}

    lines = [
        f"# 复核清单：{args.city} {args.academic_year} {args.semester} {args.grade_scope}",
        "",
        "## 当前判定",
        f"- pass：{validation.get('pass')}",
        f"- risk_level：{validation.get('risk_level', '')}",
        "",
        "## 统计",
        f"- entries：{counts.get('entries', 0)}",
        f"- grades：{counts.get('grades', 0)}",
        f"- subjects：{counts.get('subjects', 0)}",
        f"- explicit_midterm：{counts.get('explicit_midterm', 0)}",
        f"- explicit_final：{counts.get('explicit_final', 0)}",
        f"- missing_final_ratio：{counts.get('missing_final_ratio', 0)}",
        "",
        "## 需人工复核项",
    ]
    if issues:
        for item in issues:
            lines.append(f"- {item}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 建议动作"])
    if suggestions:
        for item in suggestions:
            lines.append(f"- {item}")
    else:
        lines.extend([
            "- 检查缺失学科/年级是否为原表确实不存在",
            "- 若为 OCR 漏识别，尝试切换后备模型后重跑",
            "- 确认无误后再转 active",
        ])

    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
