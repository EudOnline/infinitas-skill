"""Hosted Registry HTTP command handlers used by the CLI parser."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

import httpx

from infinitas_skill.registry.handler import format_http_error

if TYPE_CHECKING:
    from infinitas_skill.registry.publish import HostedRegistryClient


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
        fail(format_http_error(response))
    if response.content:
        result: dict[str, Any] = response.json()
        return result
    return {"ok": True}


def request_binary(args: argparse.Namespace, path: str, data: bytes) -> dict[str, Any]:
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
        fail(format_http_error(response))
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
    payload = {"version": args.version, "content_id": args.content_id}
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
            publisher=args.publisher,
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
    return request_json(args, "POST", f"/api/v1/releases/{args.release_id}/exposures", payload)


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
            "exposures update requires at least one of --listing-mode, "
            "--install-mode, or --requested-review-mode"
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
        "infinitas install from-share "
        f"'{result.get('resolve_url', '<resolve-url>')}' '<target-dir>'"
    )
    result["credential_env"] = (
        "INFINITAS_SHARE_PASSWORD" if result.get("has_password") else "INFINITAS_SHARE_SECRET"
    )
    return result


def command_share_list(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(args, "GET", f"/api/v1/share-links/releases/{args.release_id}/share-links")


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
        {"decision": args.decision, "note": args.note, "evidence": evidence},
    )
