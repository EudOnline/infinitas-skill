"""Parser and dispatch glue for release commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from infinitas_skill.install.distribution_core import DistributionError
from infinitas_skill.install.skill_validation import SkillValidationError
from infinitas_skill.policy.reviews import resolve_skill
from infinitas_skill.release.attestation import AttestationError
from infinitas_skill.release.publish import (
    ReleasePublishError,
    configure_release_publish_parser,
    publish_skill_release,
)
from infinitas_skill.release.signing_bootstrap_cli import (
    build_signing_bootstrap_parser,
    signing_bootstrap_cli_main,
)
from infinitas_skill.release.signing_doctor import (
    build_signing_doctor_parser,
)
from infinitas_skill.release.signing_doctor_report import signing_doctor_main
from infinitas_skill.release.signing_readiness import (
    build_signing_readiness_parser,
    signing_readiness_main,
)
from infinitas_skill.release.skill_ops import (
    bump_skill_version,
    lineage_diff,
    scaffold_skill,
    snapshot_active_skill,
)
from infinitas_skill.release.state import (
    ReleaseError,
    build_release_check_state_parser,
    run_release_check_state,
)
from infinitas_skill.release.tagging import ReleaseTagError, tag_skill_release
from infinitas_skill.release.trust_cli import configure_release_trust_commands

RELEASE_TOP_LEVEL_HELP = "Release readiness, signing, and verification tools"
RELEASE_PARSER_DESCRIPTION = "Release CLI"


def _emit(payload: dict, *, as_json: bool) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if as_json else None))
    return 0


def _run_tag(args: argparse.Namespace) -> int:
    try:
        payload = tag_skill_release(
            root=args.repo_root,
            skill=args.skill,
            create=args.create,
            push=args.push,
            force=args.force,
            unsigned=args.unsigned,
            local=args.local,
            releaser=args.releaser,
        )
    except ReleaseTagError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return _emit(payload, as_json=args.json)


def _run_publish(args: argparse.Namespace) -> int:
    try:
        payload = publish_skill_release(
            root=args.repo_root,
            skill=args.skill,
            preview=args.preview,
            create_tag=args.create_tag,
            push_tag=args.push_tag,
            unsigned_tag=args.unsigned_tag,
            notes_out=args.notes_out,
            write_attestation=args.write_attestation,
            github_release=args.github_release,
            signer=args.signer,
            releaser=args.releaser,
            ssh_key=args.ssh_key,
        )
    except (
        AttestationError,
        DistributionError,
        ReleaseError,
        ReleasePublishError,
        ReleaseTagError,
        SkillValidationError,
        ValueError,
    ) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if payload.get("verified_attestation"):
        print("verified attestation:", (payload.get("artifacts") or {}).get("signature"))
    return _emit(payload, as_json=args.json)


def _configure_release_trust_state_commands(subparsers: argparse._SubParsersAction) -> None:
    check_state = subparsers.add_parser(
        "check-state",
        parents=[build_release_check_state_parser()],
        add_help=False,
    )
    check_state.description = "Check stable release invariants for a skill"
    setattr(check_state, "help", "Check stable release invariants for a skill")
    check_state.set_defaults(
        _handler=lambda args: run_release_check_state(
            args.skill,
            mode=args.mode,
            as_json=args.json,
            debug_policy=args.debug_policy,
        )
    )

    signing_readiness = subparsers.add_parser(
        "signing-readiness",
        parents=[build_signing_readiness_parser()],
        add_help=False,
    )
    signing_readiness.description = "Report repository-level SSH signing readiness"
    setattr(signing_readiness, "help", "Report repository-level SSH signing readiness")
    signing_readiness.set_defaults(
        _handler=lambda args: signing_readiness_main(_signing_readiness_argv(args))
    )

    doctor_signing = subparsers.add_parser(
        "doctor-signing",
        parents=[build_signing_doctor_parser()],
        add_help=False,
    )
    doctor_signing.description = (
        "Diagnose SSH signing bootstrap, release-tag readiness, and attestation prerequisites"
    )
    setattr(doctor_signing, "help", "Diagnose signing bootstrap and release readiness")
    doctor_signing.set_defaults(
        _handler=lambda args: signing_doctor_main(_signing_doctor_argv(args))
    )

    bootstrap_signing = subparsers.add_parser(
        "bootstrap-signing",
        parents=[build_signing_bootstrap_parser()],
        add_help=False,
    )
    bootstrap_signing.description = "Bootstrap SSH signing and repository signer policy"
    setattr(bootstrap_signing, "help", "Bootstrap SSH signing and signer policy")
    bootstrap_signing.set_defaults(
        _handler=lambda args: signing_bootstrap_cli_main(_signing_bootstrap_argv(args))
    )


def _configure_release_skill_commands(subparsers: argparse._SubParsersAction) -> None:
    scaffold = subparsers.add_parser("scaffold", help="Create a skill from a canonical template")
    scaffold.add_argument("requested_name")
    scaffold.add_argument(
        "--template", choices=("basic", "scripted", "reference-heavy"), default="basic"
    )
    scaffold.add_argument("--target-root", default="skills/incubating")
    scaffold.add_argument("--repo-root", default=".")
    scaffold.add_argument("--json", action="store_true")
    scaffold.set_defaults(
        _handler=lambda args: _emit(
            scaffold_skill(
                root=args.repo_root,
                requested_name=args.requested_name,
                template=args.template,
                target_root=args.target_root,
            ),
            as_json=args.json,
        )
    )

    bump = subparsers.add_parser("bump", help="Bump skill version and changelog")
    bump.add_argument("skill")
    bump.add_argument("bump_kind", choices=("patch", "minor", "major"), nargs="?", default="patch")
    bump.add_argument("--set", dest="set_version")
    bump.add_argument("--note", action="append", default=[])
    bump.add_argument("--repo-root", default=".")
    bump.add_argument("--json", action="store_true")
    bump.set_defaults(
        _handler=lambda args: _emit(
            bump_skill_version(
                resolve_skill(Path(args.repo_root).resolve(), args.skill),
                bump_kind=args.bump_kind,
                set_version=args.set_version,
                notes=args.note,
            ),
            as_json=args.json,
        )
    )

    snapshot = subparsers.add_parser("snapshot", help="Snapshot an active skill")
    snapshot.add_argument("skill_name")
    snapshot.add_argument("--label")
    snapshot.add_argument("--repo-root", default=".")
    snapshot.add_argument("--json", action="store_true")
    snapshot.set_defaults(
        _handler=lambda args: _emit(
            snapshot_active_skill(
                root=args.repo_root,
                skill_name=args.skill_name,
                label=args.label,
            ),
            as_json=args.json,
        )
    )

    lineage = subparsers.add_parser("lineage", help="Inspect a skill's derived-from lineage")
    lineage.add_argument("skill")
    lineage.add_argument("--no-diff", action="store_true")
    lineage.add_argument("--repo-root", default=".")
    lineage.add_argument("--json", action="store_true")
    lineage.set_defaults(
        _handler=lambda args: _emit(
            lineage_diff(
                root=args.repo_root,
                skill=args.skill,
                include_diff=not args.no_diff,
            ),
            as_json=args.json,
        )
    )

    tag = subparsers.add_parser("tag", help="Create or push a signed skill release tag")
    tag.add_argument("skill")
    tag.add_argument("--create", action="store_true")
    tag.add_argument("--push", action="store_true")
    tag.add_argument("--force", action="store_true")
    tag.add_argument("--unsigned", action="store_true")
    tag.add_argument("--local", action="store_true")
    tag.add_argument("--releaser")
    tag.add_argument("--repo-root", default=".")
    tag.add_argument("--json", action="store_true")
    tag.set_defaults(_handler=_run_tag)

    publish = subparsers.add_parser("publish", help="Publish a signed skill release")
    configure_release_publish_parser(publish)
    publish.set_defaults(_handler=_run_publish)

    configure_release_trust_commands(subparsers)


def configure_release_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(dest="release_command")
    _configure_release_trust_state_commands(subparsers)
    _configure_release_skill_commands(subparsers)
    return parser


def build_release_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=RELEASE_PARSER_DESCRIPTION, prog=prog)
    return configure_release_parser(parser)


def release_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = build_release_parser(prog=prog)
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return int(handler(args))


def _signing_readiness_argv(args: argparse.Namespace) -> list[str]:
    argv: list[str] = []
    for skill in getattr(args, "skill", []) or []:
        argv.extend(["--skill", skill])
    if getattr(args, "json", False):
        argv.append("--json")
    return argv


def _signing_doctor_argv(args: argparse.Namespace) -> list[str]:
    argv: list[str] = []
    skill = getattr(args, "skill", None)
    if skill:
        argv.append(skill)
    identity = getattr(args, "identity", None)
    if identity is not None:
        argv.extend(["--identity", identity])
    provenance = getattr(args, "provenance", None)
    if provenance is not None:
        argv.extend(["--provenance", provenance])
    if getattr(args, "json", False):
        argv.append("--json")
    return argv


def _signing_bootstrap_argv(args: argparse.Namespace) -> list[str]:
    argv = [args.command]
    if args.command == "init-key":
        argv.extend(["--identity", args.identity, "--output", args.output])
        if args.force:
            argv.append("--force")
        return argv
    if args.command == "add-allowed-signer":
        argv.extend(["--identity", args.identity, "--key", args.key])
        if args.allowed_signers:
            argv.extend(["--allowed-signers", args.allowed_signers])
        return argv
    if args.command == "configure-git":
        argv.extend(["--key", args.key, "--scope", args.scope])
        return argv
    if args.command == "authorize-publisher":
        argv.extend(["--publisher", args.publisher])
        for signer in args.signer:
            argv.extend(["--signer", signer])
        for releaser in args.releaser:
            argv.extend(["--releaser", releaser])
        if args.policy:
            argv.extend(["--policy", args.policy])
        return argv
    return argv


__all__ = [
    "RELEASE_PARSER_DESCRIPTION",
    "RELEASE_TOP_LEVEL_HELP",
    "build_release_parser",
    "configure_release_parser",
    "release_main",
]
