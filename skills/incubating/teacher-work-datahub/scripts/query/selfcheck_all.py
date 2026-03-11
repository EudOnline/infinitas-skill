#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[4]
PYTHON = sys.executable


def get_paths(root: Path) -> tuple[Path, list[tuple[str, Path]]]:
    out_dir = root / "data" / "teacher-work-datahub" / "outputs" / "selfchecks"
    skill_query_dir = root / "skills" / "teacher-work-datahub" / "scripts" / "query"
    checks = [
        ("teacher_context", skill_query_dir / "selfcheck_teacher_context.py"),
        ("active_sources", skill_query_dir / "selfcheck_active_sources.py"),
        ("teaching_progress", skill_query_dir / "selfcheck_teaching_progress.py"),
        ("source_trace_lineage", skill_query_dir / "selfcheck_source_trace_lineage.py"),
        ("receipt_outputs", skill_query_dir / "selfcheck_receipt_outputs.py"),
        ("query_source_trace", skill_query_dir / "selfcheck_query_source_trace.py"),
        ("query_progress_scope", skill_query_dir / "selfcheck_query_progress_scope.py"),
    ]
    return out_dir, checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default="", help="工作区根目录；默认当前教师工作区")
    args = parser.parse_args()

    root = Path(args.workspace_root).expanduser().resolve() if args.workspace_root else DEFAULT_ROOT
    os.environ["TEACHER_WORK_DATAHUB_ROOT"] = str(root)
    out_dir, checks = get_paths(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for name, script in checks:
        p = subprocess.run([PYTHON, str(script), "--workspace-root", str(root)], cwd=root, capture_output=True, text=True)
        if p.returncode == 0:
            payload = json.loads(p.stdout)
            cases.append(
                {
                    "check": name,
                    "status": "passed",
                    "counts": payload.get("counts", {}),
                    "report": payload.get("report", ""),
                }
            )
        else:
            cases.append(
                {
                    "check": name,
                    "status": "failed",
                    "returncode": p.returncode,
                    "stdout": p.stdout,
                    "stderr": p.stderr,
                }
            )

    passed = sum(1 for c in cases if c["status"] == "passed")
    failed = sum(1 for c in cases if c["status"] == "failed")
    report = {
        "report": "teacher-work-datahub-selfcheck-all",
        "workspace_root": str(root),
        "counts": {"total": len(cases), "passed": passed, "failed": failed},
        "checks": cases,
    }
    out = out_dir / "selfcheck-all.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
