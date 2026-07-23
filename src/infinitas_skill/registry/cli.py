from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

import httpx

from infinitas_skill.registry.bootstrap_cli import configure_registry_bootstrap_command
from infinitas_skill.registry.catalog import configure_registry_catalog_parser
from infinitas_skill.registry.connection_cli import configure_registry_connection_args
from infinitas_skill.registry.local_ops import configure_registry_sources_parser

if TYPE_CHECKING:
    from infinitas_skill.registry.publish import HostedRegistryClient

REGISTRY_TOP_LEVEL_HELP = "Hosted registry control-plane tools"
REGISTRY_PARSER_DESCRIPTION = "Hosted registry private-first control plane CLI"


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def request_json(
    args: argparse.Namespace,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    try:
        response = httpx.request(
            method, args.base_url.rstrip("/") + path, json=payload, headers=headers, timeout=30.0
        )
    except httpx.HTTPError as exc:
        fail(f"API request failed: {exc}")
    if response.status_code >= 400:
        fail(response.text)
    if response.content:
        result: dict[str, Any] = response.json()
        return result
    return {"ok": True}


def request_binary(
    args: argparse.Namespace,
    path: str,
    data: bytes,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/gzip"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    try:
        response = httpx.request(
            "POST",
            args.base_url.rstrip("/") + path,
            content=data,
            headers=headers,
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        fail(f"API request failed: {exc}")
    if response.status_code >= 400:
        fail(response.text)
    result: dict[str, Any] = response.json()
    return result


def command_access_me(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "GET", "/api/v1/access/me")


def command_access_check_release(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "GET", f"/api/v1/access/releases/{args.release_id}/check")


def command_authoring_get_skill(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "GET", f"/api/v1/skills/{args.skill_id}")


def _parse_json_object(raw: str, *, arg_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"invalid {arg_name}: {exc}")
    if not isinstance(payload, dict):
        fail(f"invalid {arg_name}: expected JSON object")
    return payload


def command_authoring_create_skill(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(
        args,
        "POST",
        "/api/v1/skills",
        {
            "slug": args.slug,
            "display_name": args.display_name,
            "summary": args.summary,
            "default_visibility_profile": args.default_visibility_profile,
        },
    )


def command_authoring_upload_content(args: argparse.Namespace) -> dict[str, Any]:
    bundle_path = Path(args.bundle).expanduser()
    try:
        data = bundle_path.read_bytes()
    except OSError as exc:
        fail(f"could not read content bundle {bundle_path}: {exc}")
    return request_binary(args, f"/api/v1/skills/{args.skill_id}/content", data)


def command_authoring_create_version(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "version": args.version,
        "content_id": args.content_id,
    }
    return request_json(args, "POST", f"/api/v1/skills/{args.skill_id}/versions", payload)


def command_registry_publish(args: argparse.Namespace) -> dict[str, Any]:
    from infinitas_skill.registry.publish import HostedPublishError, publish_skill

    try:
        result = publish_skill(
            args.source,
            base_url=args.base_url,
            token=args.token,
            version=args.version,
            repo_root=args.repo_root,
            visibility=args.visibility,
            wait=not args.no_wait,
            timeout_seconds=args.timeout,
            dry_run=args.dry_run,
            receipt_path=args.receipt,
            resume=args.resume,
        )
    except HostedPublishError as exc:
        fail(str(exc))
    return result.payload


def _registry_client(args: argparse.Namespace) -> "HostedRegistryClient":
    from infinitas_skill.registry.publish import HostedRegistryClient

    return HostedRegistryClient(args.base_url, args.token)


def command_registry_list_skills(args: argparse.Namespace) -> dict[str, Any]:
    return {"items": _registry_client(args).list_skills(args.slug)}


def command_registry_list_versions(args: argparse.Namespace) -> dict[str, Any]:
    return {"items": _registry_client(args).list_versions(args.skill_id)}


def command_registry_get_version(args: argparse.Namespace) -> dict[str, Any]:
    return _registry_client(args).get_version(args.skill_id, args.version)


def command_registry_compare_versions(args: argparse.Namespace) -> dict[str, Any]:
    from infinitas_skill.registry.publish import compare_versions

    client = _registry_client(args)
    return compare_versions(
        client.get_version(args.skill_id, args.left),
        client.get_version(args.skill_id, args.right),
    )


def command_registry_list_releases(args: argparse.Namespace) -> dict[str, Any]:
    return _registry_client(args).list_releases(args.skill_id)


def command_registry_archive_skill(args: argparse.Namespace) -> dict[str, Any]:
    return _registry_client(args).archive_skill(args.skill_id)


def command_release_create(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "POST", f"/api/v1/versions/{args.version_id}/releases", {})


def command_release_get(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "GET", f"/api/v1/releases/{args.release_id}")


def command_release_artifacts(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "GET", f"/api/v1/releases/{args.release_id}/artifacts")


def command_exposure_create(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "listing_mode": args.listing_mode,
        "install_mode": args.install_mode,
        "requested_review_mode": args.requested_review_mode,
    }
    if args.audience_type is not None:
        payload["audience_type"] = args.audience_type
    return request_json(
        args,
        "POST",
        f"/api/v1/releases/{args.release_id}/exposures",
        payload,
    )


def command_exposure_update(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if args.listing_mode is not None:
        payload["listing_mode"] = args.listing_mode
    if args.install_mode is not None:
        payload["install_mode"] = args.install_mode
    if args.requested_review_mode is not None:
        payload["requested_review_mode"] = args.requested_review_mode
    if not payload:
        fail(
            "exposures update requires at least one of --listing-mode, --install-mode, or --requested-review-mode"
        )
    return request_json(args, "PATCH", f"/api/v1/exposures/{args.exposure_id}", payload)


def command_exposure_activate(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "POST", f"/api/v1/exposures/{args.exposure_id}/activate", {})


def command_exposure_revoke(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "POST", f"/api/v1/exposures/{args.exposure_id}/revoke", {})


def command_share_create(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": args.name}
    if args.password_env:
        password = os.environ.get(args.password_env)
        if not password:
            fail(f"missing share password in environment variable {args.password_env}")
        payload["password"] = password
    if args.expires_in_days is not None:
        payload["expires_in_days"] = args.expires_in_days
    if args.max_uses is not None:
        payload["max_uses"] = args.max_uses
    result = request_json(
        args,
        "POST",
        f"/api/v1/share-links/releases/{args.release_id}/share-links",
        payload,
    )
    result["agent_install_command"] = (
        f"infinitas install from-share '{result.get('resolve_url', '<resolve-url>')}' '<target-dir>'"
    )
    result["credential_env"] = (
        "INFINITAS_SHARE_PASSWORD" if result.get("has_password") else "INFINITAS_SHARE_SECRET"
    )
    return result


def command_share_list(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(
        args,
        "GET",
        f"/api/v1/share-links/releases/{args.release_id}/share-links",
    )


def command_share_revoke(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "POST", f"/api/v1/share-links/{args.share_id}/revoke", {})


def command_review_open_case(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if args.mode:
        payload["mode"] = args.mode
    return request_json(args, "POST", f"/api/v1/exposures/{args.exposure_id}/review-cases", payload)


def command_review_get_case(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "GET", f"/api/v1/review-cases/{args.review_case_id}")


def command_review_decide(args: argparse.Namespace) -> dict[str, Any]:
    evidence = _parse_json_object(args.evidence_json, arg_name="--evidence-json")
    return request_json(
        args,
        "POST",
        f"/api/v1/review-cases/{args.review_case_id}/decisions",
        {
            "decision": args.decision,
            "note": args.note,
            "evidence": evidence,
        },
    )


def _emit_json_result(result: object) -> int:
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _wrap_registry_handler(
    func: Callable[[argparse.Namespace], object],
) -> Callable[[argparse.Namespace], int]:
    return lambda args: _emit_json_result(func(args))


def _configure_registry_publish_command(subparsers: argparse._SubParsersAction) -> None:
    publish = subparsers.add_parser(
        "publish",
        help="Normalize, publish, and expose one local skill idempotently",
    )
    publish.add_argument("source", help="Local Codex/OpenClaw skill directory")
    publish.add_argument("--version", required=True, help="Semantic version to publish")
    publish.add_argument(
        "--visibility",
        choices=("private", "grant", "authenticated", "public"),
        default="private",
        help="Exposure audience (default: private)",
    )
    publish.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used by installability validation",
    )
    publish.add_argument("--timeout", type=int, default=120, help="Release wait timeout in seconds")
    publish.add_argument("--no-wait", action="store_true", help="Return after Release creation")
    publish.add_argument(
        "--dry-run", action="store_true", help="Validate and package without writes"
    )
    publish.add_argument(
        "--receipt",
        default=None,
        help="Publish receipt path (default: XDG state directory)",
    )
    publish.add_argument(
        "--resume",
        action="store_true",
        help="Require and resume a matching existing publish receipt",
    )
    publish.set_defaults(_handler=_wrap_registry_handler(command_registry_publish))


def _configure_registry_skill_commands(subparsers: argparse._SubParsersAction) -> None:
    skills = subparsers.add_parser("skills", help="Manage private-first skill records")
    skills_subparsers = skills.add_subparsers(
        dest="subcommand", metavar="{create,list,get,upload-content,archive}"
    )
    skills_create = skills_subparsers.add_parser(
        "create", help="Create a new skill namespace entry"
    )
    skills_create.add_argument("--slug", required=True, help="Skill slug")
    skills_create.add_argument(
        "--display-name", required=True, help="Human readable skill display name"
    )
    skills_create.add_argument("--summary", default="", help="Skill summary")
    skills_create.add_argument(
        "--default-visibility-profile",
        default=None,
        choices=("private", "grant", "authenticated", "public"),
        help="Optional default visibility profile identifier",
    )
    skills_create.set_defaults(_handler=_wrap_registry_handler(command_authoring_create_skill))
    skills_list = skills_subparsers.add_parser("list", help="List owned skills")
    skills_list.add_argument("--slug", default=None, help="Optional exact skill slug")
    skills_list.set_defaults(_handler=_wrap_registry_handler(command_registry_list_skills))
    skills_get = skills_subparsers.add_parser("get", help="Fetch one skill by id")
    skills_get.add_argument("skill_id", type=int, help="Skill identifier")
    skills_get.set_defaults(_handler=_wrap_registry_handler(command_authoring_get_skill))
    skills_upload = skills_subparsers.add_parser(
        "upload-content", help="Upload a validated tar.gz content bundle"
    )
    skills_upload.add_argument("skill_id", type=int, help="Skill identifier")
    skills_upload.add_argument("bundle", help="Path to the tar.gz content bundle")
    skills_upload.set_defaults(_handler=_wrap_registry_handler(command_authoring_upload_content))
    skills_archive = skills_subparsers.add_parser("archive", help="Archive a skill permanently")
    skills_archive.add_argument("skill_id", type=int, help="Skill identifier")
    skills_archive.set_defaults(_handler=_wrap_registry_handler(command_registry_archive_skill))


def _configure_registry_version_commands(subparsers: argparse._SubParsersAction) -> None:
    versions = subparsers.add_parser("versions", help="Create immutable skill versions directly")
    versions_subparsers = versions.add_subparsers(
        dest="subcommand", metavar="{create,list,get,compare}"
    )
    versions_create = versions_subparsers.add_parser(
        "create", help="Create an immutable version for a skill"
    )
    versions_create.add_argument("skill_id", type=int, help="Skill identifier")
    versions_create.add_argument("--version", required=True, help="Semantic version to create")
    versions_create.add_argument(
        "--content-id", required=True, help="Validated content identifier returned by upload"
    )
    versions_create.set_defaults(_handler=_wrap_registry_handler(command_authoring_create_version))
    versions_list = versions_subparsers.add_parser("list", help="List immutable versions")
    versions_list.add_argument("skill_id", type=int, help="Skill identifier")
    versions_list.set_defaults(_handler=_wrap_registry_handler(command_registry_list_versions))
    versions_get = versions_subparsers.add_parser("get", help="Fetch one immutable version")
    versions_get.add_argument("skill_id", type=int, help="Skill identifier")
    versions_get.add_argument("version", help="Semantic version")
    versions_get.set_defaults(_handler=_wrap_registry_handler(command_registry_get_version))
    versions_compare = versions_subparsers.add_parser(
        "compare", help="Compare sealed metadata and content digests"
    )
    versions_compare.add_argument("skill_id", type=int, help="Skill identifier")
    versions_compare.add_argument("left", help="Baseline version")
    versions_compare.add_argument("right", help="Candidate version")
    versions_compare.set_defaults(
        _handler=_wrap_registry_handler(command_registry_compare_versions)
    )


def _configure_registry_release_commands(subparsers: argparse._SubParsersAction) -> None:
    releases = subparsers.add_parser("releases", help="Create and inspect immutable releases")
    releases_subparsers = releases.add_subparsers(
        dest="subcommand", metavar="{create,list,get,artifacts}"
    )
    releases_create = releases_subparsers.add_parser(
        "create", help="Create or fetch a release for one skill version"
    )
    releases_create.add_argument("version_id", type=int, help="Skill version identifier")
    releases_create.set_defaults(_handler=_wrap_registry_handler(command_release_create))
    releases_list = releases_subparsers.add_parser("list", help="List releases for one skill")
    releases_list.add_argument("skill_id", type=int, help="Skill identifier")
    releases_list.set_defaults(_handler=_wrap_registry_handler(command_registry_list_releases))
    releases_get = releases_subparsers.add_parser("get", help="Fetch one release by id")
    releases_get.add_argument("release_id", type=int, help="Release identifier")
    releases_get.set_defaults(_handler=_wrap_registry_handler(command_release_get))
    releases_artifacts = releases_subparsers.add_parser(
        "artifacts", help="List artifacts for one release"
    )
    releases_artifacts.add_argument("release_id", type=int, help="Release identifier")
    releases_artifacts.set_defaults(_handler=_wrap_registry_handler(command_release_artifacts))


def _configure_registry_authoring_commands(subparsers: argparse._SubParsersAction) -> None:
    configure_registry_bootstrap_command(subparsers)
    _configure_registry_publish_command(subparsers)
    _configure_registry_skill_commands(subparsers)
    _configure_registry_version_commands(subparsers)
    _configure_registry_release_commands(subparsers)


def _configure_registry_access_commands(subparsers: argparse._SubParsersAction) -> None:
    exposures = subparsers.add_parser("exposures", help="Manage audience exposure and share policy")
    exposures_subparsers = exposures.add_subparsers(
        dest="subcommand", metavar="{create,update,activate,revoke}"
    )
    exposures_create = exposures_subparsers.add_parser(
        "create", help="Create a new audience exposure for one release"
    )
    exposures_create.add_argument("release_id", type=int, help="Release identifier")
    exposures_create.add_argument(
        "--audience-type",
        default=None,
        choices=("private", "grant", "authenticated", "public"),
        help="Audience type; omit to use the Skill default visibility profile",
    )
    exposures_create.add_argument("--listing-mode", default="listed", help="Listing mode")
    exposures_create.add_argument("--install-mode", default="enabled", help="Install mode")
    exposures_create.add_argument(
        "--requested-review-mode", default="none", help="Requested review mode"
    )
    exposures_create.set_defaults(_handler=_wrap_registry_handler(command_exposure_create))
    exposures_update = exposures_subparsers.add_parser(
        "update", help="Patch share policy on an existing exposure"
    )
    exposures_update.add_argument("exposure_id", type=int, help="Exposure identifier")
    exposures_update.add_argument("--listing-mode", default=None, help="Updated listing mode")
    exposures_update.add_argument("--install-mode", default=None, help="Updated install mode")
    exposures_update.add_argument(
        "--requested-review-mode", default=None, help="Updated requested review mode"
    )
    exposures_update.set_defaults(_handler=_wrap_registry_handler(command_exposure_update))
    exposures_activate = exposures_subparsers.add_parser("activate", help="Activate an exposure")
    exposures_activate.add_argument("exposure_id", type=int, help="Exposure identifier")
    exposures_activate.set_defaults(_handler=_wrap_registry_handler(command_exposure_activate))
    exposures_revoke = exposures_subparsers.add_parser("revoke", help="Revoke an exposure")
    exposures_revoke.add_argument("exposure_id", type=int, help="Exposure identifier")
    exposures_revoke.set_defaults(_handler=_wrap_registry_handler(command_exposure_revoke))

    tokens = subparsers.add_parser(
        "tokens", help="Inspect token identity and release authorization"
    )
    tokens_subparsers = tokens.add_subparsers(dest="subcommand", metavar="{me,check-release}")
    tokens_me = tokens_subparsers.add_parser(
        "me", help="Show the current access identity from the bearer token"
    )
    tokens_me.set_defaults(_handler=_wrap_registry_handler(command_access_me))
    tokens_check = tokens_subparsers.add_parser(
        "check-release", help="Check release access for the current credential"
    )
    tokens_check.add_argument("release_id", type=int, help="Release identifier")
    tokens_check.set_defaults(_handler=_wrap_registry_handler(command_access_check_release))


def _configure_registry_share_commands(subparsers: argparse._SubParsersAction) -> None:
    shares = subparsers.add_parser("shares", help="Manage Agent share links")
    shares_subparsers = shares.add_subparsers(dest="subcommand", metavar="{create,list,revoke}")
    create = shares_subparsers.add_parser("create", help="Create a share link for one release")
    create.add_argument("release_id", type=int, help="Release identifier")
    create.add_argument("--name", required=True, help="Share name")
    create.add_argument(
        "--password-env", default=None, help="Optional password environment variable"
    )
    create.add_argument("--expires-in-days", type=int, default=None, help="Optional expiry in days")
    create.add_argument("--max-uses", type=int, default=None, help="Optional maximum resolutions")
    create.set_defaults(_handler=_wrap_registry_handler(command_share_create))
    list_command = shares_subparsers.add_parser("list", help="List shares for one release")
    list_command.add_argument("release_id", type=int, help="Release identifier")
    list_command.set_defaults(_handler=_wrap_registry_handler(command_share_list))
    revoke = shares_subparsers.add_parser("revoke", help="Revoke one share")
    revoke.add_argument("share_id", type=int, help="Share identifier")
    revoke.set_defaults(_handler=_wrap_registry_handler(command_share_revoke))


def _configure_registry_review_commands(subparsers: argparse._SubParsersAction) -> None:
    reviews = subparsers.add_parser(
        "reviews", help="Manage review cases for public-facing exposures"
    )
    reviews_subparsers = reviews.add_subparsers(
        dest="subcommand", metavar="{open-case,get-case,decide}"
    )
    reviews_open = reviews_subparsers.add_parser(
        "open-case", help="Open a review case for one exposure"
    )
    reviews_open.add_argument("exposure_id", type=int, help="Exposure identifier")
    reviews_open.add_argument("--mode", default=None, help="Optional review mode override")
    reviews_open.set_defaults(_handler=_wrap_registry_handler(command_review_open_case))
    reviews_get = reviews_subparsers.add_parser("get-case", help="Fetch one review case by id")
    reviews_get.add_argument("review_case_id", type=int, help="Review case identifier")
    reviews_get.set_defaults(_handler=_wrap_registry_handler(command_review_get_case))
    reviews_decide = reviews_subparsers.add_parser("decide", help="Record a review decision")
    reviews_decide.add_argument("review_case_id", type=int, help="Review case identifier")
    reviews_decide.add_argument(
        "--decision", required=True, help="Decision: approve, reject, or comment"
    )
    reviews_decide.add_argument("--note", default="", help="Decision note")
    reviews_decide.add_argument("--evidence-json", default="{}", help="Evidence JSON object")
    reviews_decide.set_defaults(_handler=_wrap_registry_handler(command_review_decide))

    sources = subparsers.add_parser("sources", help="Manage repository registry sources")
    configure_registry_sources_parser(sources)

    catalog = subparsers.add_parser("catalog", help="Build generated registry catalog views")
    configure_registry_catalog_parser(catalog)


def configure_registry_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    configure_registry_connection_args(parser)
    subparsers = parser.add_subparsers(
        dest="registry_command",
        metavar="{bootstrap,publish,skills,versions,releases,exposures,shares,tokens,reviews,sources,catalog}",
    )
    _configure_registry_authoring_commands(subparsers)
    _configure_registry_access_commands(subparsers)
    _configure_registry_share_commands(subparsers)
    _configure_registry_review_commands(subparsers)
    return parser


def build_registry_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=REGISTRY_PARSER_DESCRIPTION, prog=prog)
    return configure_registry_parser(parser)


def registry_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = build_registry_parser(prog=prog)
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))


__all__ = [
    "REGISTRY_PARSER_DESCRIPTION",
    "REGISTRY_TOP_LEVEL_HELP",
    "build_registry_parser",
    "configure_registry_parser",
    "registry_main",
]
