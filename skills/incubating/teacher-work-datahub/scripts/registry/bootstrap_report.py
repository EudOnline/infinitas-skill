#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parents[4]
PYTHON = sys.executable


def get_paths(root: Path) -> dict[str, Path]:
    skill_dir = root / "skills" / "teacher-work-datahub"
    datahub_dir = root / "data" / "teacher-work-datahub"
    return {
        "ROOT": root,
        "SKILL_DIR": skill_dir,
        "DATAHUB_DIR": datahub_dir,
        "CATALOG": datahub_dir / "catalog" / "sources.json",
        "SEM_CTX": datahub_dir / "curated" / "indexes" / "semester_context.json",
        "ACTIVE_SOURCES": datahub_dir / "curated" / "indexes" / "active_sources.json",
        "TEACHER_INDEX": datahub_dir / "curated" / "indexes" / "teacher_index.json",
        "CLASS_INDEX": datahub_dir / "curated" / "indexes" / "class_index.json",
        "SELF_CHECK": skill_dir / "scripts" / "query" / "selfcheck_all.py",
        "ENV_EXAMPLE": skill_dir / ".env.teacher-work-datahub.example",
        "OCR_CFG": root / "config" / "ocr.json",
    }


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def count_records(payload: dict[str, Any] | None) -> int | None:
    if not payload:
        return None
    records = payload.get("records")
    if isinstance(records, list):
        return len(records)
    return None


def has_nonempty_api_key(cfg: dict[str, Any] | None) -> bool:
    if not cfg:
        return False
    api_key = str(cfg.get("api_key") or "").strip()
    return bool(api_key)


def run_selfcheck(root: Path, self_check: Path) -> dict[str, Any]:
    p = subprocess.run([PYTHON, str(self_check), "--workspace-root", str(root)], cwd=root, capture_output=True, text=True)
    payload = None
    if p.stdout.strip():
        try:
            payload = json.loads(p.stdout)
        except Exception:
            payload = None
    return {
        "returncode": p.returncode,
        "payload": payload,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }


def build_suggested_actions(*, ocr_key_present: bool, env_example_exists: bool, catalog_exists: bool, indexes_ready: bool) -> list[str]:
    actions: list[str] = []
    if not env_example_exists:
        actions.append("生成并检查 skills/teacher-work-datahub/.env.teacher-work-datahub.example")
    if not ocr_key_present:
        actions.extend(
            [
                "当前未配置 OCR key：在环境变量中设置 SILICONFLOW_API_KEY，或在 config/ocr.json 中填写 api_key",
                "若暂时不需要 OCR，可先跳过 OCR 相关链路，优先跑已有结构化数据的 bootstrap / selfcheck",
                "配置完成后，用 `bash tools/scripts/ocr-manager.sh config` 自检 OCR 配置是否生效",
            ]
        )
    if not catalog_exists:
        actions.append("先运行 bootstrap 脚本补齐 datahub catalog：scripts/registry/bootstrap_from_existing_sources.py 与 bootstrap_teaching_progress_sources.py")
    if catalog_exists and not indexes_ready:
        actions.extend(
            [
                "运行 `python3 skills/teacher-work-datahub/scripts/registry/rebuild_active_sources.py`",
                "运行 `python3 skills/teacher-work-datahub/scripts/registry/rebuild_teacher_index.py`",
                "运行 `python3 skills/teacher-work-datahub/scripts/registry/rebuild_class_index.py`",
            ]
        )
    if not actions:
        actions.append("bootstrap 基线已具备，可继续运行 `python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py` 做健康确认")
    return actions


def build_report(root: Path) -> dict[str, Any]:
    paths = get_paths(root)
    catalog = load_json(paths["CATALOG"])
    semester_context = load_json(paths["SEM_CTX"])
    active_sources = load_json(paths["ACTIVE_SOURCES"])
    teacher_index = load_json(paths["TEACHER_INDEX"])
    class_index = load_json(paths["CLASS_INDEX"])
    ocr_cfg = load_json(paths["OCR_CFG"])

    catalog_exists = paths["CATALOG"].exists()
    indexes_ready = paths["ACTIVE_SOURCES"].exists() and paths["TEACHER_INDEX"].exists() and paths["CLASS_INDEX"].exists()
    ocr_key_present = bool(os.getenv("SILICONFLOW_API_KEY")) or has_nonempty_api_key(ocr_cfg)
    env_example_exists = paths["ENV_EXAMPLE"].exists()
    selfcheck = run_selfcheck(root, paths["SELF_CHECK"])

    report = {
        "report": "teacher-work-datahub-bootstrap-report",
        "ok": bool(catalog_exists and indexes_ready),
        "checks": {
            "catalog_exists": catalog_exists,
            "semester_context_exists": paths["SEM_CTX"].exists(),
            "active_sources_exists": paths["ACTIVE_SOURCES"].exists(),
            "teacher_index_exists": paths["TEACHER_INDEX"].exists(),
            "class_index_exists": paths["CLASS_INDEX"].exists(),
            "env_example_exists": env_example_exists,
            "ocr_key_present": ocr_key_present,
        },
        "snapshot": {
            "catalog_records": count_records(catalog),
            "semester_context_current": (semester_context or {}).get("current", {}),
            "active_sources_keys": sorted(list((active_sources or {}).keys())) if isinstance(active_sources, dict) else [],
            "teacher_index_keys": len((teacher_index or {}).keys()) if isinstance(teacher_index, dict) else None,
            "class_index_keys": len((class_index or {}).keys()) if isinstance(class_index, dict) else None,
            "ocr": {
                "config_exists": ocr_cfg is not None,
                "enabled": bool((ocr_cfg or {}).get("enabled", False)),
                "provider": (ocr_cfg or {}).get("provider", ""),
                "service": (ocr_cfg or {}).get("service", ""),
                "model": (ocr_cfg or {}).get("model", ""),
                "api_key_present": ocr_key_present,
            },
        },
        "selfcheck": {
            "returncode": selfcheck["returncode"],
            "counts": ((selfcheck.get("payload") or {}).get("counts") or {}),
        },
    }
    report["suggested_actions"] = build_suggested_actions(
        ocr_key_present=ocr_key_present,
        env_example_exists=env_example_exists,
        catalog_exists=catalog_exists,
        indexes_ready=indexes_ready,
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--workspace-root", default="", help="工作区根目录；默认当前教师工作区")
    args = parser.parse_args()

    root = Path(args.workspace_root).expanduser().resolve() if args.workspace_root else DEFAULT_ROOT
    report = build_report(root)
    report["workspace_root"] = str(root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Teacher Work DataHub Bootstrap Report")
        print(f"ok: {report['ok']}")
        print("checks:")
        for k, v in report["checks"].items():
            print(f"- {k}: {v}")
        print("suggested_actions:")
        for item in report["suggested_actions"]:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
