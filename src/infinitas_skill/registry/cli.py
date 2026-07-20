"""Private-first hosted registry CLI wired into the unified infinitas command."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import httpx

from infinitas_skill.registry.catalog import configure_registry_catalog_parser
from infinitas_skill.registry.local_ops import configure_registry_sources_parser

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


def _configure_registry_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=os.environ.get("INFINITAS_REGISTRY_API_BASE_URL", "http://127.0.0.1:8000"),
        help="Hosted registry API base URL",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("INFINITAS_REGISTRY_API_TOKEN", ""),
        help="Bearer token for hosted registry API",
    )


def _configure_registry_authoring_commands(subparsers: argparse._SubParsersAction) -> None:
    skills = subparsers.add_parser("skills", help="Manage private-first skill records")
    skills_subparsers = skills.add_subparsers(
        dest="subcommand", metavar="{create,get,upload-content}"
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
    skills_get = skills_subparsers.add_parser("get", help="Fetch one skill by id")
    skills_get.add_argument("skill_id", type=int, help="Skill identifier")
    skills_get.set_defaults(_handler=_wrap_registry_handler(command_authoring_get_skill))
    skills_upload = skills_subparsers.add_parser(
        "upload-content", help="Upload a validated tar.gz content bundle"
    )
    skills_upload.add_argument("skill_id", type=int, help="Skill identifier")
    skills_upload.add_argument("bundle", help="Path to the tar.gz content bundle")
    skills_upload.set_defaults(_handler=_wrap_registry_handler(command_authoring_upload_content))

    versions = subparsers.add_parser("versions", help="Create immutable skill versions directly")
    versions_subparsers = versions.add_subparsers(dest="subcommand", metavar="{create}")
    versions_create = versions_subparsers.add_parser(
        "create", help="Create an immutable version for a skill"
    )
    versions_create.add_argument("skill_id", type=int, help="Skill identifier")
    versions_create.add_argument("--version", required=True, help="Semantic version to create")
    versions_create.add_argument(
        "--content-id", required=True, help="Validated content identifier returned by upload"
    )
    versions_create.set_defaults(_handler=_wrap_registry_handler(command_authoring_create_version))

    releases = subparsers.add_parser("releases", help="Create and inspect immutable releases")
    releases_subparsers = releases.add_subparsers(
        dest="subcommand", metavar="{create,get,artifacts}"
    )
    releases_create = releases_subparsers.add_parser(
        "create", help="Create or fetch a release for one skill version"
    )
    releases_create.add_argument("version_id", type=int, help="Skill version identifier")
    releases_create.set_defaults(_handler=_wrap_registry_handler(command_release_create))
    releases_get = releases_subparsers.add_parser("get", help="Fetch one release by id")
    releases_get.add_argument("release_id", type=int, help="Release identifier")
    releases_get.set_defaults(_handler=_wrap_registry_handler(command_release_get))
    releases_artifacts = releases_subparsers.add_parser(
        "artifacts", help="List artifacts for one release"
    )
    releases_artifacts.add_argument("release_id", type=int, help="Release identifier")
    releases_artifacts.set_defaults(_handler=_wrap_registry_handler(command_release_artifacts))


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
    _configure_registry_connection_args(parser)
    subparsers = parser.add_subparsers(
        dest="registry_command",
        metavar="{skills,versions,releases,exposures,tokens,reviews}",
    )
    _configure_registry_authoring_commands(subparsers)
    _configure_registry_access_commands(subparsers)
    _configure_registry_review_commands(subparsers)
    return parser


def build_registry_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=REGISTRY_PARSER_DESCRIPTION, prog=prog)
    return configure_registry_parser(parser)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=os.environ.get("INFINITAS_REGISTRY_API_BASE_URL", "http://127.0.0.1:8000"),
        help="Hosted registry API base URL",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("INFINITAS_REGISTRY_API_TOKEN", ""),
        help="Bearer token for hosted registry API",
    )


def build_registry_skills_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas registry skills",
        description="Manage private-first skill records",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="subcommand", metavar="{create,get,upload-content}")
    create = sub.add_parser("create", help="Create a new skill namespace entry")
    create.add_argument("--slug", required=True, help="Skill slug")
    create.add_argument("--display-name", required=True, help="Human readable skill display name")
    create.add_argument("--summary", default="", help="Skill summary")
    create.add_argument(
        "--default-visibility-profile",
        default=None,
        choices=("private", "grant", "authenticated", "public"),
        help="Default visibility profile",
    )
    get = sub.add_parser("get", help="Fetch one skill by id")
    get.add_argument("skill_id", type=int, help="Skill identifier")
    upload = sub.add_parser("upload-content", help="Upload a validated tar.gz content bundle")
    upload.add_argument("skill_id", type=int, help="Skill identifier")
    upload.add_argument("bundle", help="Path to the tar.gz content bundle")
    return parser


def build_registry_versions_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas registry versions",
        description="Create immutable skill versions directly",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="subcommand", metavar="{create}")
    create = sub.add_parser("create", help="Create an immutable version for a skill")
    create.add_argument("skill_id", type=int, help="Skill identifier")
    create.add_argument("--version", required=True, help="Semantic version to create")
    create.add_argument(
        "--content-id", required=True, help="Validated content identifier returned by upload"
    )
    return parser


def build_registry_releases_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas registry releases",
        description="Create and inspect immutable releases",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="subcommand", metavar="{create,get,artifacts}")
    create = sub.add_parser("create", help="Create or fetch a release for one skill version")
    create.add_argument("version_id", type=int, help="Skill version identifier")
    get = sub.add_parser("get", help="Fetch one release by id")
    get.add_argument("release_id", type=int, help="Release identifier")
    artifacts = sub.add_parser("artifacts", help="List artifacts for one release")
    artifacts.add_argument("release_id", type=int, help="Release identifier")
    return parser


def build_registry_exposures_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas registry exposures",
        description="Manage audience exposure and share policy",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="subcommand", metavar="{create,update,activate,revoke}")
    create = sub.add_parser("create", help="Create a new audience exposure for one release")
    create.add_argument("release_id", type=int, help="Release identifier")
    create.add_argument(
        "--audience-type",
        default=None,
        choices=("private", "grant", "authenticated", "public"),
        help="Audience type; omit to use the Skill default visibility profile",
    )
    create.add_argument("--listing-mode", default="listed", help="Listing mode")
    create.add_argument("--install-mode", default="enabled", help="Install mode")
    create.add_argument("--requested-review-mode", default="none", help="Requested review mode")
    update = sub.add_parser("update", help="Patch share policy on an existing exposure")
    update.add_argument("exposure_id", type=int, help="Exposure identifier")
    update.add_argument("--listing-mode", default=None, help="Updated listing mode")
    update.add_argument("--install-mode", default=None, help="Updated install mode")
    update.add_argument(
        "--requested-review-mode", default=None, help="Updated requested review mode"
    )
    activate = sub.add_parser("activate", help="Activate an exposure")
    activate.add_argument("exposure_id", type=int, help="Exposure identifier")
    revoke = sub.add_parser("revoke", help="Revoke an exposure")
    revoke.add_argument("exposure_id", type=int, help="Exposure identifier")
    return parser


def build_registry_tokens_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas registry tokens",
        description="Inspect token identity and release authorization",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="subcommand", metavar="{me,check-release}")
    sub.add_parser("me", help="Show the current access identity from the bearer token")
    check = sub.add_parser("check-release", help="Check release access for the current credential")
    check.add_argument("release_id", type=int, help="Release identifier")
    return parser


def build_registry_reviews_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas registry reviews",
        description="Manage review cases for public-facing exposures",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="subcommand", metavar="{open-case,get-case,decide}")
    open_case = sub.add_parser("open-case", help="Open a review case for one exposure")
    open_case.add_argument("exposure_id", type=int, help="Exposure identifier")
    open_case.add_argument("--mode", default=None, help="Optional review mode override")
    get_case = sub.add_parser("get-case", help="Fetch one review case by id")
    get_case.add_argument("review_case_id", type=int, help="Review case identifier")
    decide = sub.add_parser("decide", help="Record a review decision")
    decide.add_argument("review_case_id", type=int, help="Review case identifier")
    decide.add_argument("--decision", required=True, help="Decision: approve, reject, or comment")
    decide.add_argument("--note", default="", help="Decision note")
    decide.add_argument("--evidence-json", default="{}", help="Evidence JSON object")
    return parser


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
    "build_registry_exposures_parser",
    "build_registry_versions_parser",
    "build_registry_parser",
    "build_registry_releases_parser",
    "build_registry_reviews_parser",
    "build_registry_skills_parser",
    "build_registry_tokens_parser",
    "configure_registry_parser",
    "registry_main",
]
