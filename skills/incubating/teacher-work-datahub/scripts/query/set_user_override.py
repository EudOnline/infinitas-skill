#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from override_utils import set_runtime_override, set_teacher_override  # noqa: E402


def split_csv(text: str) -> list[str]:
    return [x.strip() for x in (text or "").split(",") if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", default="")
    ap.add_argument("--classes", default="")
    ap.add_argument("--subjects", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--week-parity", default="")
    args = ap.parse_args()

    outputs = {}

    if args.teacher:
        outputs["teacher_override"] = set_teacher_override(
            args.teacher,
            classes=split_csv(args.classes),
            subjects=split_csv(args.subjects),
            note=args.note,
        )

    if args.week_parity:
        outputs["runtime_override"] = set_runtime_override("week_parity", args.week_parity)

    print(json.dumps({"success": True, **outputs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
