#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[4]
PYTHON = sys.executable


def get_paths(root: Path) -> dict[str, Path]:
    skill_dir = root / "skills" / "teacher-work-datahub"
    return {
        "ROOT": root,
        "OUT_DIR": root / "data" / "teacher-work-datahub" / "outputs" / "healthchecks",
        "SELFCHECK_ALL": skill_dir / "scripts" / "query" / "selfcheck_all.py",
        "FEISHU_ADAPTER_P6": skill_dir / "scripts" / "adapters" / "feishu" / "test_timetable_pipeline_p6.py",
    }


def run_json(cmd: list[str], *, cwd: Path) -> tuple[int, dict | None, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    payload = None
    if p.stdout.strip():
        try:
            payload = json.loads(p.stdout)
        except Exception:
            payload = None
    return p.returncode, payload, p.stdout, p.stderr


def classify_status(*, selfcheck_rc: int, adapter_enabled: bool, adapter_rc: int | None, adapter_skipped: bool) -> str:
    if selfcheck_rc != 0:
        return "unhealthy"
    if adapter_enabled and not adapter_skipped and adapter_rc not in (0, None):
        return "degraded"
    return "healthy"


def render_text(report: dict) -> str:
    lines = [
        "Teacher Work DataHub 健康检查摘要",
        f"生成时间：{report.get('generated_at', '')}",
        f"总体状态：{report.get('overall_status', '')}",
        f"selfcheck_all：rc={report.get('selfcheck_all', {}).get('returncode')} | passed={report.get('selfcheck_all', {}).get('counts', {}).get('passed', 0)}/{report.get('selfcheck_all', {}).get('counts', {}).get('total', 0)}",
    ]
    adapter = report.get("adapter_integration") or {}
    if adapter.get("enabled"):
        if adapter.get("skipped"):
            lines.append(f"Feishu adapter：skipped | reason={adapter.get('skip_reason', '')}")
        else:
            lines.append(f"Feishu adapter：rc={adapter.get('returncode')} | passed={adapter.get('counts', {}).get('passed', 0)}/{adapter.get('counts', {}).get('total', 0)}")
    else:
        lines.append("Feishu adapter：未执行")

    lines.append("")
    lines.append("## selfcheck_all 详情")
    for item in (report.get("selfcheck_all", {}).get("checks") or []):
        lines.append(f"- {item.get('check')}: {item.get('status')} ({item.get('counts', {}).get('passed', 0)}/{item.get('counts', {}).get('total', 0)})")

    if adapter.get("enabled"):
        lines.append("")
        lines.append("## Feishu adapter 集成详情")
        if adapter.get("skipped"):
            lines.append(f"- skipped: {adapter.get('skip_reason', '')}")
        else:
            for item in (adapter.get("cases") or []):
                lines.append(f"- {item.get('id')}: {item.get('status')}")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-p6", action="store_true", help="兼容旧参数：同时执行 Feishu adapter 集成回归")
    parser.add_argument("--mode", choices=["core", "extended"], default="core", help="core=仅 datahub 自检；extended=包含可选 Feishu adapter 集成检查")
    parser.add_argument("--workspace-root", default="", help="工作区根目录；默认当前教师工作区")
    args = parser.parse_args()

    root = Path(args.workspace_root).expanduser().resolve() if args.workspace_root else DEFAULT_ROOT
    paths = get_paths(root)
    out_dir = paths["OUT_DIR"]
    out_dir.mkdir(parents=True, exist_ok=True)

    run_adapter = args.with_p6 or args.mode == "extended"

    sc_rc, sc_payload, sc_stdout, sc_stderr = run_json([PYTHON, str(paths["SELFCHECK_ALL"]), "--workspace-root", str(root)], cwd=root)
    selfcheck_info = {
        "returncode": sc_rc,
        "counts": (sc_payload or {}).get("counts", {}),
        "checks": (sc_payload or {}).get("checks", []),
        "stdout": sc_stdout,
        "stderr": sc_stderr,
    }

    adapter_info = {
        "enabled": run_adapter,
        "mode": args.mode,
        "adapter": "feishu",
        "skipped": False,
        "skip_reason": "",
        "returncode": None,
        "counts": {},
        "cases": [],
        "stdout": "",
        "stderr": "",
    }
    if run_adapter:
        if not paths["FEISHU_ADAPTER_P6"].exists():
            adapter_info.update(
                {
                    "skipped": True,
                    "skip_reason": "optional Feishu adapter integration missing: skills/teacher-work-datahub/scripts/adapters/feishu/test_timetable_pipeline_p6.py",
                }
            )
        else:
            adapter_rc, adapter_payload, adapter_stdout, adapter_stderr = run_json([PYTHON, str(paths["FEISHU_ADAPTER_P6"])], cwd=root)
            adapter_info.update(
                {
                    "returncode": adapter_rc,
                    "counts": (adapter_payload or {}).get("counts", {}),
                    "cases": (adapter_payload or {}).get("cases", []),
                    "stdout": adapter_stdout,
                    "stderr": adapter_stderr,
                }
            )

    overall_status = classify_status(
        selfcheck_rc=sc_rc,
        adapter_enabled=run_adapter,
        adapter_rc=adapter_info.get("returncode"),
        adapter_skipped=bool(adapter_info.get("skipped")),
    )
    overall_ok = overall_status == "healthy"
    report = {
        "report": "teacher-work-datahub-healthcheck",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "workspace_root": str(root),
        "overall_status": overall_status,
        "selfcheck_all": selfcheck_info,
        "adapter_integration": adapter_info,
    }

    json_out = out_dir / "healthcheck-datahub.json"
    txt_out = out_dir / "healthcheck-datahub.txt"
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_out.write_text(render_text(report), encoding="utf-8")

    print(render_text(report).rstrip())
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
