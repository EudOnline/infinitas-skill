#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[4]


def build_copy_plan(root: Path) -> list[tuple[Path, Path]]:
    fixture_root = root / "skills" / "teacher-work-datahub" / "tests" / "fixtures" / "minimal-datahub"
    datahub_root = root / "data" / "teacher-work-datahub"
    schedule_root = root / "data" / "schedules"
    return [
        (fixture_root / "catalog" / "sources.json", datahub_root / "catalog" / "sources.json"),
        (fixture_root / "curated" / "indexes" / "semester_context.json", datahub_root / "curated" / "indexes" / "semester_context.json"),
        (fixture_root / "curated" / "indexes" / "active_sources.json", datahub_root / "curated" / "indexes" / "active_sources.json"),
        (fixture_root / "curated" / "indexes" / "teacher_index.json", datahub_root / "curated" / "indexes" / "teacher_index.json"),
        (fixture_root / "curated" / "indexes" / "class_index.json", datahub_root / "curated" / "indexes" / "class_index.json"),
        (fixture_root / "curated" / "lineage" / "source_lineage.json", datahub_root / "curated" / "lineage" / "source_lineage.json"),
        (fixture_root / "schedules" / "grade_schedule_minimal.json", schedule_root / "2025-2026-S2-grade10cohort2024-grade11-complete.json"),
        (fixture_root / "schedules" / "school_schedule_minimal.json", schedule_root / "school_schedule_2025_2026S2_latest.json"),
    ]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只显示将要复制的文件，不实际写入")
    parser.add_argument("--workspace-root", default="", help="目标工作区根目录；默认当前教师工作区")
    args = parser.parse_args()

    root = Path(args.workspace_root).expanduser().resolve() if args.workspace_root else DEFAULT_ROOT
    copy_plan = build_copy_plan(root)
    report = {"fixture": "minimal-datahub", "workspace_root": str(root), "copied": [], "dry_run": args.dry_run}

    for src, dst in copy_plan:
        if not src.exists():
            raise FileNotFoundError(f"fixture file missing: {src}")
        report["copied"].append({"from": str(src), "to": str(dst)})
        if not args.dry_run:
            ensure_parent(dst)
            shutil.copyfile(src, dst)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
