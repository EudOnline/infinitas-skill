from __future__ import annotations

import argparse
import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

JsonRequest = Callable[[argparse.Namespace, str, str, dict[str, Any] | None], dict[str, Any]]
HandlerWrapper = Callable[
    [Callable[[argparse.Namespace], object]], Callable[[argparse.Namespace], int]
]
_JSON_REQUEST: JsonRequest | None = None


def _request(
    args: argparse.Namespace,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if _JSON_REQUEST is None:  # pragma: no cover - configured by the parent CLI
        raise RuntimeError("collaboration CLI request function is not configured")
    return _JSON_REQUEST(args, method, path, payload)


def _change_set_path(args: argparse.Namespace, suffix: str = "") -> str:
    return f"/api/v1/skills/{args.skill_id}/changesets/{args.change_set_id}{suffix}"


def command_changeset_create(args: argparse.Namespace) -> dict[str, Any]:
    return _request(
        args,
        "POST",
        f"/api/v1/skills/{args.skill_id}/changesets",
        {
            "base_version_id": args.base_version_id,
            "content_id": args.content_id,
            "proposed_version": args.version,
        },
    )


def command_changeset_list(args: argparse.Namespace) -> dict[str, Any]:
    return {"items": _request(args, "GET", f"/api/v1/skills/{args.skill_id}/changesets")}


def command_changeset_get(args: argparse.Namespace) -> dict[str, Any]:
    return _request(args, "GET", _change_set_path(args))


def command_changeset_transition(args: argparse.Namespace) -> dict[str, Any]:
    return _request(args, "POST", _change_set_path(args, f"/{args.transition}"))


def command_changeset_accept(args: argparse.Namespace) -> dict[str, Any]:
    return _request(
        args,
        "POST",
        _change_set_path(args, "/accept"),
        {"expected_latest_digest": args.expected_latest_digest},
    )


def command_snapshot_register(args: argparse.Namespace) -> dict[str, Any]:
    encrypted = Path(args.file).expanduser().resolve()
    digest = hashlib.sha256()
    with encrypted.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return _request(
        args,
        "POST",
        f"/api/v1/skills/{args.skill_id}/data-snapshots",
        {
            "skill_version_id": args.skill_version_id,
            "parent_snapshot_id": args.parent_snapshot_id,
            "schema_version": args.schema_version,
            "encrypted_object_uri": args.object_uri,
            "ciphertext_sha256": f"sha256:{digest.hexdigest()}",
            "ciphertext_size_bytes": encrypted.stat().st_size,
            "manifest_digest": args.manifest_digest,
            "encryption": "age",
        },
    )


def command_snapshot_list(args: argparse.Namespace) -> dict[str, Any]:
    return {"items": _request(args, "GET", f"/api/v1/skills/{args.skill_id}/data-snapshots")}


def command_snapshot_get(args: argparse.Namespace) -> dict[str, Any]:
    return _request(
        args,
        "GET",
        f"/api/v1/skills/{args.skill_id}/data-snapshots/{args.snapshot_id}",
    )


def _configure_changesets(subparsers: argparse._SubParsersAction, wrap: HandlerWrapper) -> None:
    root = subparsers.add_parser("changesets", help="Coordinate concurrent Agent improvements")
    commands = root.add_subparsers(
        dest="subcommand", metavar="{create,list,get,submit,accept,reject}"
    )
    create = commands.add_parser("create", help="Create a candidate from the current version")
    create.add_argument("skill_id", type=int)
    create.add_argument("--base-version-id", type=int, default=None)
    create.add_argument("--content-id", required=True)
    create.add_argument("--version", required=True)
    create.set_defaults(_handler=wrap(command_changeset_create))
    listing = commands.add_parser("list", help="List ChangeSets for one skill")
    listing.add_argument("skill_id", type=int)
    listing.set_defaults(_handler=wrap(command_changeset_list))
    get = commands.add_parser("get", help="Get one ChangeSet")
    _add_change_set_identity(get)
    get.set_defaults(_handler=wrap(command_changeset_get))
    for transition in ("submit", "reject"):
        command = commands.add_parser(transition, help=f"{transition.title()} one ChangeSet")
        _add_change_set_identity(command)
        command.set_defaults(transition=transition, _handler=wrap(command_changeset_transition))
    accept = commands.add_parser("accept", help="CAS-promote a submitted ChangeSet")
    _add_change_set_identity(accept)
    accept.add_argument("--expected-latest-digest", required=True)
    accept.set_defaults(_handler=wrap(command_changeset_accept))


def _add_change_set_identity(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("skill_id", type=int)
    parser.add_argument("change_set_id")


def _configure_snapshots(subparsers: argparse._SubParsersAction, wrap: HandlerWrapper) -> None:
    root = subparsers.add_parser("data-snapshots", help="Register encrypted skill data backups")
    commands = root.add_subparsers(dest="subcommand", metavar="{register,list,get}")
    register = commands.add_parser("register", help="Register an encrypted off-host object")
    register.add_argument("skill_id", type=int)
    register.add_argument("--skill-version-id", type=int, required=True)
    register.add_argument("--file", required=True, help="Local .age object used for hashing")
    register.add_argument("--object-uri", required=True)
    register.add_argument("--manifest-digest", required=True)
    register.add_argument("--schema-version", type=int, default=1)
    register.add_argument("--parent-snapshot-id", default=None)
    register.set_defaults(_handler=wrap(command_snapshot_register))
    listing = commands.add_parser("list", help="List registered data snapshots")
    listing.add_argument("skill_id", type=int)
    listing.set_defaults(_handler=wrap(command_snapshot_list))
    get = commands.add_parser("get", help="Get data snapshot recovery metadata")
    get.add_argument("skill_id", type=int)
    get.add_argument("snapshot_id")
    get.set_defaults(_handler=wrap(command_snapshot_get))


def configure_collaboration_commands(
    subparsers: argparse._SubParsersAction,
    *,
    request_json: JsonRequest,
    wrap: HandlerWrapper,
) -> None:
    global _JSON_REQUEST
    _JSON_REQUEST = request_json
    _configure_changesets(subparsers, wrap)
    _configure_snapshots(subparsers, wrap)


__all__ = ["configure_collaboration_commands"]
