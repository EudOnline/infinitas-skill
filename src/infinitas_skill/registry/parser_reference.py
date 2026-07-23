"""Standalone registry parsers used by generated CLI reference docs."""

from __future__ import annotations

import argparse
import os


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
    sub = parser.add_subparsers(
        dest="subcommand", metavar="{create,list,get,upload-content,archive}"
    )
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
    list_command = sub.add_parser("list", help="List owned skills")
    list_command.add_argument("--slug", default=None, help="Optional exact skill slug")
    get = sub.add_parser("get", help="Fetch one skill by id")
    get.add_argument("skill_id", type=int, help="Skill identifier")
    upload = sub.add_parser("upload-content", help="Upload a validated tar.gz content bundle")
    upload.add_argument("skill_id", type=int, help="Skill identifier")
    upload.add_argument("bundle", help="Path to the tar.gz content bundle")
    archive = sub.add_parser("archive", help="Archive a skill permanently")
    archive.add_argument("skill_id", type=int, help="Skill identifier")
    return parser


def build_registry_versions_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas registry versions",
        description="Create immutable skill versions directly",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="subcommand", metavar="{create,list,get,compare}")
    create = sub.add_parser("create", help="Create an immutable version for a skill")
    create.add_argument("skill_id", type=int, help="Skill identifier")
    create.add_argument("--version", required=True, help="Semantic version to create")
    create.add_argument(
        "--content-id", required=True, help="Validated content identifier returned by upload"
    )
    list_command = sub.add_parser("list", help="List immutable versions")
    list_command.add_argument("skill_id", type=int, help="Skill identifier")
    get = sub.add_parser("get", help="Fetch one immutable version")
    get.add_argument("skill_id", type=int, help="Skill identifier")
    get.add_argument("version", help="Semantic version")
    compare = sub.add_parser("compare", help="Compare sealed metadata and content digests")
    compare.add_argument("skill_id", type=int, help="Skill identifier")
    compare.add_argument("left", help="Baseline version")
    compare.add_argument("right", help="Candidate version")
    return parser


def build_registry_releases_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas registry releases",
        description="Create and inspect immutable releases",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="subcommand", metavar="{create,list,get,artifacts}")
    create = sub.add_parser("create", help="Create or fetch a release for one skill version")
    create.add_argument("version_id", type=int, help="Skill version identifier")
    list_command = sub.add_parser("list", help="List releases for one skill")
    list_command.add_argument("skill_id", type=int, help="Skill identifier")
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


def build_registry_shares_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas registry shares",
        description="Create, inspect, and revoke Agent share links",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="subcommand", metavar="{create,list,revoke}")
    create = sub.add_parser("create", help="Create a share link for one release")
    create.add_argument("release_id", type=int, help="Release identifier")
    create.add_argument("--name", required=True, help="Share name")
    create.add_argument(
        "--password-env", default=None, help="Optional password environment variable"
    )
    create.add_argument("--expires-in-days", type=int, default=None, help="Optional expiry in days")
    create.add_argument("--max-uses", type=int, default=None, help="Optional maximum resolutions")
    list_command = sub.add_parser("list", help="List shares for one release")
    list_command.add_argument("release_id", type=int, help="Release identifier")
    revoke = sub.add_parser("revoke", help="Revoke one share")
    revoke.add_argument("share_id", type=int, help="Share identifier")
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
