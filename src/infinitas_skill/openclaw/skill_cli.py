"""OpenClaw skill validation, migration, and snapshot CLI commands."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from infinitas_skill.root import ROOT
from infinitas_skill.skills.openclaw import (
    OpenClawBridgeError,
    derive_registry_meta,
    export_release_to_directory,
    parse_skill_frontmatter,
    resolve_ai_release,
    resolve_skill_dir,
    scaffold_imported_skill,
)

from .skill_contract import OpenClawSkillContractError, load_openclaw_skill_contract


def _print_payload(payload: dict, *, as_json: bool) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_openclaw_skill_validate(*, skill_dir: str, as_json: bool = False) -> int:
    try:
        contract = load_openclaw_skill_contract(Path(skill_dir).resolve())
    except OpenClawSkillContractError as exc:
        if as_json:
            _print_payload({"ok": False, "error": str(exc)}, as_json=True)
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    _print_payload({"ok": True, "contract": contract}, as_json=as_json)
    return 0


def run_openclaw_skill_backup(
    *,
    skill_dir: str,
    output_path: str,
    data_dir: str | None,
    age_recipients: list[str],
    allow_plaintext_data: bool,
    force: bool,
    as_json: bool = False,
) -> int:
    from .snapshot import OpenClawSnapshotError, create_openclaw_snapshot

    try:
        payload = create_openclaw_snapshot(
            skill_dir=skill_dir,
            output_path=output_path,
            data_dir=data_dir,
            age_recipients=age_recipients,
            allow_plaintext_data=allow_plaintext_data,
            force=force,
        )
    except OpenClawSnapshotError as exc:
        if as_json:
            _print_payload({"ok": False, "error": str(exc)}, as_json=True)
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    _print_payload(payload, as_json=as_json)
    return 0


def run_openclaw_skill_restore(
    *,
    snapshot_path: str,
    skill_dir: str | None,
    data_dir: str | None,
    age_identities: list[str],
    verify_only: bool,
    force: bool,
    as_json: bool = False,
) -> int:
    from .snapshot import OpenClawSnapshotError, restore_openclaw_snapshot

    try:
        payload = restore_openclaw_snapshot(
            snapshot_path=snapshot_path,
            skill_target=skill_dir,
            data_target=data_dir,
            age_identities=age_identities,
            verify_only=verify_only,
            force=force,
        )
    except OpenClawSnapshotError as exc:
        if as_json:
            _print_payload({"ok": False, "error": str(exc)}, as_json=True)
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    _print_payload(payload, as_json=as_json)
    return 0


def run_openclaw_skill_import(
    *,
    source_path: str,
    owner: str,
    publisher: str | None,
    mode: str,
    force: bool,
    root: str | Path = ROOT,
    as_json: bool = False,
) -> int:
    repo_root = Path(root).resolve()
    try:
        source_dir = resolve_skill_dir(source_path)
        meta = derive_registry_meta(
            parse_skill_frontmatter(source_dir / "SKILL.md"), owner=owner, publisher=publisher
        )
        target_dir = repo_root / "skills" / "incubating" / str(meta["name"])
        payload = {
            "ok": True,
            "state": "planned" if mode == "confirm" else "imported",
            "source_dir": str(source_dir),
            "target_dir": str(target_dir),
            "name": meta["name"],
            "qualified_name": meta.get("qualified_name") or meta["name"],
            "owner": meta["owner"],
            "publisher": meta.get("publisher"),
            "mode": mode,
            "force": force,
        }
        if mode == "confirm":
            payload["next_step"] = "run-import"
        else:
            result = scaffold_imported_skill(source_dir, target_dir, meta, force=force)
            payload["files"] = result["files"]
            payload["next_step"] = "validate-imported-skill"
    except OpenClawBridgeError as exc:
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "import-openclaw-failed",
            "message": str(exc),
        }
        _print_payload(payload, as_json=as_json)
        return 1
    _print_payload(payload, as_json=as_json)
    return 0


def run_openclaw_skill_export(
    *,
    requested_name: str,
    out_dir: str,
    requested_version: str | None,
    mode: str,
    force: bool,
    root: str | Path = ROOT,
    as_json: bool = False,
) -> int:
    repo_root = Path(root).resolve()
    try:
        selected, resolved_version, version_entry = resolve_ai_release(
            repo_root, requested_name, requested_version=requested_version
        )
        export_dir = (
            Path(out_dir).expanduser() / str(selected.get("name") or requested_name)
        ).resolve()
        manifest_path = (repo_root / str(version_entry["manifest_path"])).resolve()
        payload = {
            "ok": True,
            "state": "planned" if mode == "confirm" else "exported",
            "name": selected.get("name"),
            "qualified_name": selected.get("qualified_name") or selected.get("name"),
            "resolved_version": resolved_version,
            "manifest_path": str(manifest_path),
            "bundle_path": str((repo_root / str(version_entry["bundle_path"])).resolve()),
            "export_dir": str(export_dir),
            "mode": mode,
            "force": force,
            "suggested_publish_command": ["clawhub", "publish", str(export_dir)],
        }
        target = export_dir
        if mode == "confirm":
            target = repo_root / ".tmp-openclaw-export-preview" / str(selected.get("name"))
        result = export_release_to_directory(
            repo_root,
            manifest_path,
            target,
            force=True if mode == "confirm" else force,
            public_ready=True,
        )
        payload["public_ready"] = result["public_ready"]
        payload["validation_errors"] = result["validation_errors"]
        payload["migration_contract_source_mode"] = result["migration_contract_source_mode"]
        if result["validation_errors"]:
            payload.update(
                {
                    "ok": False,
                    "state": "failed",
                    "error_code": "export-openclaw-validation-failed",
                    "message": "export did not satisfy OpenClaw public-ready requirements",
                }
            )
            _print_payload(payload, as_json=as_json)
            return 1
        if mode == "confirm":
            shutil.rmtree(target.parent, ignore_errors=True)
            payload["next_step"] = "run-export"
        else:
            payload["files"] = result["files"]
            payload["next_step"] = "review-or-publish-manually"
    except OpenClawBridgeError as exc:
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "export-openclaw-failed",
            "message": str(exc),
        }
        _print_payload(payload, as_json=as_json)
        return 1
    _print_payload(payload, as_json=as_json)
    return 0


def configure_openclaw_skill_validate_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "skill_dir", help="Skill directory to validate against the OpenClaw contract"
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    return parser


def configure_openclaw_skill_backup_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("skill_dir", help="OpenClaw skill directory to snapshot")
    parser.add_argument("--out", required=True, help="Snapshot output path")
    parser.add_argument("--data-dir", help="Optional workspace data directory to include")
    parser.add_argument(
        "--age-recipient",
        action="append",
        default=[],
        help="age recipient for encrypted output; repeat for multiple recipients",
    )
    parser.add_argument(
        "--allow-plaintext-data",
        action="store_true",
        help="Explicitly allow an unencrypted snapshot containing workspace data",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing output file")
    parser.add_argument("--json", action="store_true")
    return parser


def configure_openclaw_skill_restore_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("snapshot_path", help="Snapshot archive or .age file")
    parser.add_argument("--skill-dir", help="Skill restore target")
    parser.add_argument("--data-dir", help="Workspace data restore target")
    parser.add_argument(
        "--age-identity",
        action="append",
        default=[],
        help="age identity file; repeat for multiple identities",
    )
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--force", action="store_true", help="Atomically replace existing targets")
    parser.add_argument("--json", action="store_true")
    return parser


def configure_openclaw_skill_import_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("source_path")
    parser.add_argument("--owner", default=os.environ.get("USER", "unknown"))
    parser.add_argument("--publisher")
    parser.add_argument("--mode", choices=("auto", "confirm"), default="auto")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    return parser


def configure_openclaw_skill_export_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("requested_name")
    parser.add_argument("--out", required=True)
    parser.add_argument("--version")
    parser.add_argument("--mode", choices=("auto", "confirm"), default="auto")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    return parser


def build_openclaw_skill_validate_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Validate one skill directory against the OpenClaw runtime contract",
    )
    return configure_openclaw_skill_validate_parser(parser)


def build_openclaw_skill_backup_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Create a checksummed OpenClaw skill and workspace-data snapshot",
    )
    return configure_openclaw_skill_backup_parser(parser)


def build_openclaw_skill_restore_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Verify or restore an OpenClaw skill and workspace-data snapshot",
    )
    return configure_openclaw_skill_restore_parser(parser)


def _configure_runtime_commands(skill_sub: Any) -> None:
    validate = skill_sub.add_parser(
        "validate",
        help="Validate one skill directory against the OpenClaw runtime contract",
        description="Validate one skill directory against the OpenClaw runtime contract",
    )
    configure_openclaw_skill_validate_parser(validate)
    validate.set_defaults(
        _handler=lambda args: run_openclaw_skill_validate(
            skill_dir=args.skill_dir, as_json=args.json
        )
    )
    backup = skill_sub.add_parser(
        "backup", help="Create a checksummed skill and workspace-data snapshot"
    )
    configure_openclaw_skill_backup_parser(backup)
    backup.set_defaults(
        _handler=lambda args: run_openclaw_skill_backup(
            skill_dir=args.skill_dir,
            output_path=args.out,
            data_dir=args.data_dir,
            age_recipients=args.age_recipient,
            allow_plaintext_data=args.allow_plaintext_data,
            force=args.force,
            as_json=args.json,
        )
    )
    restore = skill_sub.add_parser(
        "restore", help="Verify or restore a skill and workspace-data snapshot"
    )
    configure_openclaw_skill_restore_parser(restore)
    restore.set_defaults(
        _handler=lambda args: run_openclaw_skill_restore(
            snapshot_path=args.snapshot_path,
            skill_dir=args.skill_dir,
            data_dir=args.data_dir,
            age_identities=args.age_identity,
            verify_only=args.verify_only,
            force=args.force,
            as_json=args.json,
        )
    )


def _configure_migration_commands(skill_sub: Any) -> None:
    import_parser = skill_sub.add_parser("import", help="Import a rendered OpenClaw skill")
    configure_openclaw_skill_import_parser(import_parser)
    import_parser.set_defaults(
        _handler=lambda args: run_openclaw_skill_import(
            source_path=args.source_path,
            owner=args.owner,
            publisher=args.publisher,
            mode=args.mode,
            force=args.force,
            root=args.repo_root,
            as_json=args.json,
        )
    )
    export = skill_sub.add_parser("export", help="Export an immutable OpenClaw release")
    configure_openclaw_skill_export_parser(export)
    export.set_defaults(
        _handler=lambda args: run_openclaw_skill_export(
            requested_name=args.requested_name,
            out_dir=args.out,
            requested_version=args.version,
            mode=args.mode,
            force=args.force,
            root=args.repo_root,
            as_json=args.json,
        )
    )


def configure_openclaw_skill_commands(subparsers: Any) -> None:
    skill = subparsers.add_parser(
        "skill",
        help="OpenClaw skill lifecycle tools",
        description="OpenClaw skill lifecycle tools",
    )
    skill_sub = skill.add_subparsers(dest="openclaw_skill_command")
    _configure_runtime_commands(skill_sub)
    _configure_migration_commands(skill_sub)


__all__ = [
    "build_openclaw_skill_backup_parser",
    "build_openclaw_skill_restore_parser",
    "build_openclaw_skill_validate_parser",
    "configure_openclaw_skill_commands",
    "run_openclaw_skill_backup",
    "run_openclaw_skill_export",
    "run_openclaw_skill_import",
    "run_openclaw_skill_restore",
    "run_openclaw_skill_validate",
]
