"""Parser and dispatch glue for release commands."""

from __future__ import annotations

import argparse

from infinitas_skill.release.signing_bootstrap_cli import (
    build_signing_bootstrap_parser,
    signing_bootstrap_cli_main,
)
from infinitas_skill.release.signing_doctor import (
    build_signing_doctor_parser,
    signing_doctor_main,
)
from infinitas_skill.release.signing_readiness import (
    build_signing_readiness_parser,
    signing_readiness_main,
)
from infinitas_skill.release.state import (
    build_release_check_state_parser,
    run_release_check_state,
)

RELEASE_TOP_LEVEL_HELP = "Release readiness, signing, and verification tools"
RELEASE_PARSER_DESCRIPTION = "Release CLI"


def configure_release_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(
        dest="release_command",
        metavar="{check-state,signing-readiness,doctor-signing,bootstrap-signing}",
    )

    check_state = subparsers.add_parser(
        "check-state",
        parents=[build_release_check_state_parser()],
        add_help=False,
    )
    check_state.description = "Check stable release invariants for a skill"
    check_state.help = "Check stable release invariants for a skill"
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
    signing_readiness.help = "Report repository-level SSH signing readiness"
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
    doctor_signing.help = "Diagnose signing bootstrap and release readiness"
    doctor_signing.set_defaults(
        _handler=lambda args: signing_doctor_main(_signing_doctor_argv(args))
    )

    bootstrap_signing = subparsers.add_parser(
        "bootstrap-signing",
        parents=[build_signing_bootstrap_parser()],
        add_help=False,
    )
    bootstrap_signing.description = "Bootstrap SSH signing and repository signer policy"
    bootstrap_signing.help = "Bootstrap SSH signing and signer policy"
    bootstrap_signing.set_defaults(
        _handler=lambda args: signing_bootstrap_cli_main(_signing_bootstrap_argv(args))
    )

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
    return handler(args)


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
