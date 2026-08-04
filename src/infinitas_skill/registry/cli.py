from __future__ import annotations

import argparse
from collections.abc import Callable

from infinitas_skill.registry import hosted_commands as commands
from infinitas_skill.registry.bootstrap_cli import configure_registry_bootstrap_command
from infinitas_skill.registry.catalog import configure_registry_catalog_parser
from infinitas_skill.registry.collaboration_cli import configure_collaboration_commands
from infinitas_skill.registry.connection_cli import configure_registry_connection_args
from infinitas_skill.registry.handler import wrap_hosted_handler
from infinitas_skill.registry.local_ops import configure_registry_sources_parser

REGISTRY_TOP_LEVEL_HELP = "Hosted registry control-plane tools"
REGISTRY_PARSER_DESCRIPTION = "Hosted registry private-first control plane CLI"

# Keep parser declarations readable while command execution lives separately.
request_json = commands.request_json
command_access_me = commands.command_access_me
command_access_check_release = commands.command_access_check_release
command_authoring_get_skill = commands.command_authoring_get_skill
command_authoring_create_skill = commands.command_authoring_create_skill
command_authoring_upload_content = commands.command_authoring_upload_content
command_authoring_create_version = commands.command_authoring_create_version
command_registry_publish = commands.command_registry_publish
command_registry_list_skills = commands.command_registry_list_skills
command_registry_list_versions = commands.command_registry_list_versions
command_registry_get_version = commands.command_registry_get_version
command_registry_compare_versions = commands.command_registry_compare_versions
command_registry_list_releases = commands.command_registry_list_releases
command_registry_archive_skill = commands.command_registry_archive_skill
command_release_create = commands.command_release_create
command_release_get = commands.command_release_get
command_release_artifacts = commands.command_release_artifacts
command_exposure_create = commands.command_exposure_create
command_exposure_update = commands.command_exposure_update
command_exposure_activate = commands.command_exposure_activate
command_exposure_revoke = commands.command_exposure_revoke
command_share_create = commands.command_share_create
command_share_list = commands.command_share_list
command_share_revoke = commands.command_share_revoke
command_review_open_case = commands.command_review_open_case
command_review_get_case = commands.command_review_get_case
command_review_decide = commands.command_review_decide


def _wrap_registry_handler(
    func: Callable[[argparse.Namespace], object],
) -> Callable[[argparse.Namespace], int]:
    return wrap_hosted_handler(func, commands.fail)


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
        "--publisher",
        help="Publisher slug for a fully offline --dry-run",
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
    configure_collaboration_commands(
        subparsers, request_json=request_json, wrap=_wrap_registry_handler
    )
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
