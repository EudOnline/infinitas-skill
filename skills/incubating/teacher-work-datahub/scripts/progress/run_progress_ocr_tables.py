#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
import subprocess
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
OCR_DIR = WORKSPACE / "data/reports/ocr"
PARSER = WORKSPACE / "skills/teacher-work-datahub/scripts/progress/parse_progress_ocr_tables.py"
OCR_SCRIPT = WORKSPACE / "tools/scripts/ocr-manager.sh"


def norm(v: str) -> str:
    return (v or "").strip()


def run_ocr(image: Path, prompt: str) -> Path | None:
    before = set(OCR_DIR.glob("ocr-*.txt"))
    cmd = ["bash", str(OCR_SCRIPT), "ocr", str(image), prompt]
    proc = subprocess.run(cmd, cwd=str(WORKSPACE), text=True, capture_output=True)
    after = set(OCR_DIR.glob("ocr-*.txt"))
    new_files = sorted(after - before)
    if new_files:
        return new_files[-1]
    m = re.search(r"\[已保存\]\s*(.+)", proc.stderr or "")
    if m:
        path = Path(m.group(1).strip())
        if path.exists():
            return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--city", required=True)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--semester", required=True)
    parser.add_argument("--grade-scope", default="highschool")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    source = Path(args.source_file).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"source not found: {source}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    default_out = WORKSPACE / f"data/teacher-work-datahub/outputs/teaching-progress/ocr-seeds/{norm(args.city)}-{norm(args.academic_year)}-{norm(args.semester)}-{stamp}.json"
    out = Path(args.out).expanduser().resolve() if norm(args.out) else default_out
    out.parent.mkdir(parents=True, exist_ok=True)

    prompt = "请优先按HTML table输出可见表格内容；若做不到，尽量完整输出原文。不要解释。"
    ocr_file = run_ocr(source, prompt)
    if not ocr_file:
        raise SystemExit("ocr output not found")

    cmd = [
        "python3", str(PARSER),
        "--ocr-file", str(ocr_file),
        "--city", args.city,
        "--academic-year", args.academic_year,
        "--semester", args.semester,
        "--grade-scope", args.grade_scope,
        "--out", str(out),
    ]
    subprocess.run(cmd, cwd=str(WORKSPACE), check=True)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
