"""CLI flow for SSH signing bootstrap operations."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from infinitas_skill.release.signing_bootstrap import (
    SigningBootstrapError,
    configure_git_signing,
    current_git_value,
    default_allowed_signers_path,
    default_namespace_policy_path,
    public_key_from_key_path,
    public_key_from_private_key,
    update_namespace_policy,
    upsert_allowed_signer,
)
from infinitas_skill.release.state import ROOT


def configure_signing_bootstrap_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_key = subparsers.add_parser("init-key", help="Generate a new SSH signing key pair")
    init_key.add_argument(
        "--identity", required=True, help="Signer identity to store as the SSH key comment"
    )
    init_key.add_argument("--output", required=True, help="Private key path to create")
    init_key.add_argument(
        "--force", action="store_true", help="Overwrite an existing key path"
    )

    add_signer = subparsers.add_parser(
        "add-allowed-signer", help="Add or update a trusted signer entry"
    )
    add_signer.add_argument(
        "--identity", required=True, help="Signer identity stored in config/allowed_signers"
    )
    add_signer.add_argument(
        "--key", required=True, help="Private SSH key path or .pub file"
    )
    add_signer.add_argument(
        "--allowed-signers",
        default=str(default_allowed_signers_path()),
        help="Allowed signers file to update",
    )

    configure = subparsers.add_parser(
        "configure-git", help="Configure git to use SSH signing with a key path"
    )
    configure.add_argument("--key", required=True, help="Private SSH signing key path")
    configure.add_argument(
        "--scope", choices=["local", "global"], default="local", help="Git config scope"
    )

    authorize = subparsers.add_parser(
        "authorize-publisher",
        help="Authorize signer or releaser identities for a publisher",
    )
    authorize.add_argument(
        "--publisher", required=True, help="Publisher slug in policy/namespace-policy.json"
    )
    authorize.add_argument(
        "--signer",
        action="append",
        default=[],
        help="Signer identity to add to authorized_signers",
    )
    authorize.add_argument(
        "--releaser",
        action="append",
        default=[],
        help="Releaser identity to add to authorized_releasers",
    )
    authorize.add_argument(
        "--policy",
        default=str(default_namespace_policy_path()),
        help="Namespace policy JSON path to update",
    )

    return parser


def build_signing_bootstrap_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Bootstrap SSH signing and repository signer policy",
    )
    return configure_signing_bootstrap_parser(parser)


def parse_signing_bootstrap_args(
    argv: list[str] | None = None,
    *,
    prog: str | None = None,
) -> argparse.Namespace:
    return build_signing_bootstrap_parser(prog=prog).parse_args(argv)


def run_init_key(args) -> None:
    output = Path(args.output).expanduser()
    pub_path = Path(str(output) + ".pub")
    if not args.force and (output.exists() or pub_path.exists()):
        raise SigningBootstrapError(
            f"key path already exists: {output} (use --force to overwrite)"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", args.identity, "-f", str(output)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "ssh-keygen failed"
        raise SigningBootstrapError(message)
    public_key = public_key_from_private_key(output)
    print(f"created key: {output}")
    print(f"public key: {pub_path}")
    print(f"public key text: {public_key}")
    print(
        "next: python3 scripts/bootstrap-signing.py add-allowed-signer --identity "
        f"{args.identity} --key {output}"
    )


def run_add_allowed_signer(args) -> None:
    public_key = public_key_from_key_path(args.key)
    result = upsert_allowed_signer(Path(args.allowed_signers), args.identity, public_key)
    status = "updated" if result["changed"] else "unchanged"
    print(f"{status} allowed signers: {Path(args.allowed_signers)}")
    print(f"entry: {result['line']}")
    print(
        "next: git add config/allowed_signers "
        '&& git commit -m "chore: trust release signer" && git push'
    )


def run_configure_git(args) -> None:
    key_path = Path(args.key).expanduser()
    if not key_path.exists():
        raise SigningBootstrapError(f"key path does not exist: {key_path}")
    configure_git_signing(ROOT, key_path, scope=args.scope)
    effective_format = current_git_value(ROOT, "gpg.format") or "-"
    effective_key = current_git_value(ROOT, "user.signingkey") or "-"
    print(f"configured git signing ({args.scope})")
    print(f"gpg.format={effective_format}")
    print(f"user.signingkey={effective_key}")


def run_authorize_publisher(args) -> None:
    if not args.signer and not args.releaser:
        raise SigningBootstrapError(
            "authorize-publisher requires at least one --signer or --releaser"
        )
    result = update_namespace_policy(
        Path(args.policy),
        args.publisher,
        signers=args.signer,
        releasers=args.releaser,
    )
    status = "updated" if result["changed"] else "unchanged"
    print(f"{status} namespace policy: {args.policy}")
    print(f"publisher: {args.publisher}")
    print(
        "authorized_signers: "
        + ", ".join(result["summary"].get("authorized_signers", []))
    )
    print(
        "authorized_releasers: "
        + ", ".join(result["summary"].get("authorized_releasers", []))
    )
    print(
        "next: git add policy/namespace-policy.json "
        '&& git commit -m "chore: authorize release identities" && git push'
    )


def signing_bootstrap_cli_main(argv: list[str] | None = None) -> int:
    args = parse_signing_bootstrap_args(argv)
    try:
        if args.command == "init-key":
            run_init_key(args)
        elif args.command == "add-allowed-signer":
            run_add_allowed_signer(args)
        elif args.command == "configure-git":
            run_configure_git(args)
        elif args.command == "authorize-publisher":
            run_authorize_publisher(args)
        else:
            raise SigningBootstrapError(f"unknown command: {args.command}")
    except SigningBootstrapError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


__all__ = [
    "ROOT",
    "build_signing_bootstrap_parser",
    "configure_signing_bootstrap_parser",
    "parse_signing_bootstrap_args",
    "run_add_allowed_signer",
    "run_authorize_publisher",
    "run_configure_git",
    "run_init_key",
    "signing_bootstrap_cli_main",
]
