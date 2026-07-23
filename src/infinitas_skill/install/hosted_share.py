"""Install one immutable release obtained from a hosted share link."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

from infinitas_skill.install.distribution_core import load_json
from infinitas_skill.install.distribution_materialization import safely_extract_bundle
from infinitas_skill.install.distribution_verification import verify_distribution_manifest
from infinitas_skill.install.exact import _run_install_resolved


class HostedShareError(RuntimeError):
    """Raised when a share cannot be resolved or its release is not verifiable."""


DEFAULT_SHARE_PASSWORD_ENV = "INFINITAS_SHARE_PASSWORD"
DEFAULT_SHARE_SECRET_ENV = "INFINITAS_SHARE_SECRET"


def configure_install_from_share_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("resolve_url", help="Hosted share resolve URL")
    parser.add_argument("target_dir", help="Target directory for the installed skill")
    parser.add_argument(
        "--password-env",
        default=DEFAULT_SHARE_PASSWORD_ENV,
        help="Environment variable containing a share password",
    )
    parser.add_argument(
        "--secret-env",
        default=DEFAULT_SHARE_SECRET_ENV,
        help="Environment variable containing a passwordless share secret",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing target")
    parser.add_argument("--no-deps", action="store_true", help="Reject dependency changes")
    parser.add_argument("--repo-root", default=".", help="Repository root for verification")
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_from_share_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "infinitas install from-share",
        description="Resolve and install one immutable release from a hosted share",
    )
    return configure_install_from_share_parser(parser)


def _origin(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise HostedShareError("share URL must use an http(s) origin")
    return f"{parsed.scheme}://{parsed.netloc}"


def _request_json(
    url: str, *, method: str, token: str | None = None, payload: dict | None = None
) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = httpx.request(method, url, json=payload, headers=headers, timeout=60.0)
    except httpx.HTTPError as exc:
        raise HostedShareError(f"share request failed: {exc}") from exc
    try:
        body = response.json() if response.content else {}
    except ValueError as exc:
        raise HostedShareError("share endpoint returned invalid JSON") from exc
    if response.status_code >= 400:
        detail = body.get("detail", body) if isinstance(body, dict) else body
        raise HostedShareError(f"share endpoint returned HTTP {response.status_code}: {detail}")
    if not isinstance(body, dict):
        raise HostedShareError("share endpoint returned an invalid object")
    return body


def _resolve_share(
    resolve_url: str, *, password: str | None, secret: str | None
) -> tuple[str, dict]:
    parsed = urllib.parse.urlparse(resolve_url)
    if not parsed.path.startswith("/api/v1/share-links/") or not parsed.path.endswith("/resolve"):
        raise HostedShareError("resolve URL must be /api/v1/share-links/{id}/resolve")
    body: dict[str, Any] = {}
    if password:
        body["password"] = password
    if secret:
        body["secret"] = secret
    resolved = _request_json(resolve_url, method="POST", payload=body)
    token = str(resolved.get("access_token") or "")
    install_url = str(resolved.get("install_url") or "")
    if not token or not install_url:
        raise HostedShareError("share resolution did not return an install token and URL")
    if _origin(install_url) != _origin(resolve_url):
        raise HostedShareError("share install URL changed origin")
    install = _request_json(install_url, method="GET", token=token)
    return _origin(resolve_url), {"share": resolved, "install": install, "access_token": token}


def _safe_reference(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HostedShareError("hosted manifest contains an empty artifact reference")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme or parsed.netloc or Path(parsed.path).is_absolute():
        raise HostedShareError("hosted manifest artifact reference must be relative")
    candidate = Path(parsed.path)
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise HostedShareError("hosted manifest artifact reference is unsafe")
    return value


def _download_artifact(url: str, *, origin: str, token: str, destination: Path) -> None:
    if _origin(url) != origin:
        raise HostedShareError("share artifact URL changed origin")
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60.0)
    except httpx.HTTPError as exc:
        raise HostedShareError(f"share artifact download failed: {exc}") from exc
    if response.status_code >= 400:
        raise HostedShareError(f"share artifact download returned HTTP {response.status_code}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)


def _materialize_share(origin: str, payload: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    install = payload["install"]
    token = payload["access_token"]
    temp_root = Path(tempfile.mkdtemp(prefix="infinitas-share-install-"))
    try:
        manifest_url = str(install.get("manifest_url") or "")
        _download_artifact(
            manifest_url, origin=origin, token=token, destination=temp_root / "manifest.json"
        )
        manifest = load_json(temp_root / "manifest.json")
        bundle = manifest.get("bundle") or {}
        attestation = manifest.get("attestation_bundle") or {}
        refs = {
            "bundle": (_safe_reference(bundle.get("path")), str(install.get("bundle_url") or "")),
            "provenance": (
                _safe_reference(attestation.get("provenance_path")),
                str(install.get("provenance_url") or ""),
            ),
            "signature": (
                _safe_reference(attestation.get("signature_path")),
                str(install.get("signature_url") or ""),
            ),
        }
        for relative, url in refs.values():
            _download_artifact(url, origin=origin, token=token, destination=temp_root / relative)
        verified = verify_distribution_manifest(
            temp_root / "manifest.json",
            root=temp_root,
            attestation_root=repo_root,
        )
        materialized = safely_extract_bundle(
            verified["bundle_path"], temp_root / "materialized", bundle.get("root_dir")
        )
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
    return {
        "source_type": "working-tree",
        "skill_path": str(materialized),
        "materialized_path": str(materialized),
        "cleanup_dir": str(temp_root),
        "registry_name": "share",
        "registry_kind": "share",
        "registry_base_url": origin,
        "name": install.get("name"),
        "qualified_name": install.get("qualified_name"),
        "publisher": install.get("publisher"),
        "version": install.get("version"),
        "distribution_manifest": "manifest.json",
        "distribution_bundle": refs["bundle"][0],
        "distribution_bundle_sha256": bundle.get("sha256"),
        "source_snapshot_kind": "hosted-release",
        "source_snapshot_ref": install.get("release_id"),
        "share_id": payload["share"].get("id"),
    }


def run_install_from_share(
    *,
    root: str | Path,
    resolve_url: str,
    target_dir: str,
    password_env: str | None = None,
    secret_env: str | None = None,
    force: bool = False,
    no_deps: bool = False,
    as_json: bool = False,
) -> int:
    password_var = password_env or DEFAULT_SHARE_PASSWORD_ENV
    secret_var = secret_env or DEFAULT_SHARE_SECRET_ENV
    password = os.environ.get(password_var)
    secret = os.environ.get(secret_var)
    if not password and not secret:
        if not os.isatty(0):
            raise HostedShareError(
                f"set {password_var} or {secret_var} for a non-interactive install"
            )
        password = getpass.getpass("Share password or secret: ")
    repo_root = Path(root).resolve()
    origin, payload = _resolve_share(resolve_url, password=password, secret=secret)
    resolved = _materialize_share(origin, payload, repo_root=repo_root)
    return _run_install_resolved(
        repo_root=repo_root,
        name=str(resolved.get("qualified_name") or resolved.get("name") or "shared-skill"),
        target_dir=target_dir,
        resolved_payload=resolved,
        requested_version=str(resolved.get("version") or "") or None,
        force=force,
        no_deps=no_deps,
        as_json=as_json,
    )


def run_install_from_share_command(**kwargs: Any) -> int:
    try:
        return run_install_from_share(**kwargs)
    except HostedShareError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "state": "failed",
                    "error_code": "hosted-share-install-failed",
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2 if kwargs.get("as_json") else None,
            )
        )
        return 1


__all__ = [
    "HostedShareError",
    "build_install_from_share_parser",
    "configure_install_from_share_parser",
    "run_install_from_share",
    "run_install_from_share_command",
]
