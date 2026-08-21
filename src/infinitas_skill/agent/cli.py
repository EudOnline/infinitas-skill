from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from infinitas_skill.agent.profile import (
    finalize_profile_rotation,
    fingerprint,
    new_keys,
    read_profile,
    stage_profile_rotation,
    verifier,
    write_profile,
)
from infinitas_skill.install.exact import run_install_exact
from infinitas_skill.install.install_manifest import InstallManifestError, load_install_manifest
from infinitas_skill.install.installed_integrity import (
    InstalledIntegrityError,
    verify_installed_skill,
)
from infinitas_skill.install.upgrade import run_install_upgrade
from infinitas_skill.registry.local_ops import bootstrap_public_registry
from infinitas_skill.registry.publish import publish_skill


def _request(
    base_url: str, method: str, path: str, *, token: str = "", body: dict | None = None
) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Agent API returned HTTP {exc.code}: {detail[:500]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Agent API returned invalid JSON")
    return payload


def _join(args: argparse.Namespace) -> int:
    invitation = sys.stdin.read().strip()
    if not invitation.startswith("enroll_"):
        raise RuntimeError("read an enroll_ invitation from stdin")
    status_key, api_key = new_keys()
    api_verifier = verifier(api_key)
    status_verifier = verifier(status_key)
    result = _request(
        args.base_url,
        "POST",
        "/api/v1/agent-enrollments",
        token=invitation,
        body={
            "status_verifier": status_verifier,
            "api_key_verifier": api_verifier,
            "fingerprint": fingerprint(api_verifier),
            "runtime": {"platform": sys.platform, "cli_version": "1"},
        },
    )
    profile = {
        "base_url": args.base_url.rstrip("/"),
        "status_key": status_key,
        "api_key": api_key,
        "enrollment_public_id": result.get("public_id"),
        "fingerprint": result.get("fingerprint"),
    }
    path = write_profile(args.profile, profile)
    print(
        json.dumps(
            {"ok": True, "state": result.get("state"), "profile": str(path)}, ensure_ascii=False
        )
    )
    return 0


def _status(args: argparse.Namespace) -> int:
    profile = read_profile(args.profile)
    result = _request(
        str(profile["base_url"]),
        "GET",
        f"/api/v1/agent-enrollments/{profile['enrollment_public_id']}",
        token=str(profile["status_key"]),
    )
    print(json.dumps(result, ensure_ascii=False))
    if result.get("state") == "approved":
        identity = _request(
            str(profile["base_url"]), "GET", "/api/v1/access/me", token=str(profile["api_key"])
        )
        profile["principal_id"] = identity.get("principal_id")
        profile["principal_slug"] = identity.get("principal_slug")
        write_profile(args.profile, profile)
    return 0


def _backup(args: argparse.Namespace) -> int:
    profile = read_profile(args.profile)
    result = publish_skill(
        args.source,
        base_url=str(profile["base_url"]),
        token=str(profile["api_key"]),
        version=args.version,
        repo_root=args.repo_root,
        visibility="public",
        wait=not args.no_wait,
        agent_mode=True,
    )
    print(json.dumps(result.payload, ensure_ascii=False, default=str))
    return 0


def _rotate(args: argparse.Namespace) -> int:
    profile = read_profile(args.profile)
    current_key = str(profile["api_key"])
    _status_key, replacement_key = new_keys()
    replacement_verifier = verifier(replacement_key)
    staged_profile, created = stage_profile_rotation(
        args.profile,
        {
            **profile,
            "api_key": replacement_key,
            "fingerprint": fingerprint(replacement_verifier),
        },
        expected_api_key=current_key,
    )
    replacement_key = str(staged_profile["api_key"])
    replacement_verifier = verifier(replacement_key)
    if not created:
        try:
            _request(
                str(profile["base_url"]),
                "GET",
                "/api/v1/access/me",
                token=replacement_key,
            )
        except RuntimeError:
            pass
        else:
            path = finalize_profile_rotation(args.profile)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "profile": str(path),
                        "fingerprint": fingerprint(replacement_verifier),
                        "recovered": True,
                    }
                )
            )
            return 0
    result = _request(
        str(profile["base_url"]),
        "POST",
        "/api/v1/agent/credentials/rotate",
        token=current_key,
        body={
            "api_key_verifier": replacement_verifier,
            "fingerprint": fingerprint(replacement_verifier),
        },
    )
    if result["fingerprint"] != fingerprint(replacement_verifier):
        raise RuntimeError("Agent API returned an unexpected credential fingerprint")
    path = finalize_profile_rotation(args.profile)
    print(json.dumps({"ok": True, "profile": str(path), "fingerprint": result["fingerprint"]}))
    return 0


def _profile_base_url(args: argparse.Namespace) -> str:
    if args.base_url:
        return str(args.base_url).rstrip("/")
    try:
        profile = read_profile(args.profile)
    except ValueError as exc:
        raise RuntimeError(
            "no public Registry configured; pass --base-url or create an Agent profile"
        ) from exc
    base_url = str(profile.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("Agent profile has no base_url; pass --base-url")
    return base_url


def _registry_base_url(base_url: str) -> str:
    suffix = "/api/v1/registry"
    return base_url if base_url.endswith(suffix) else f"{base_url.rstrip('/')}{suffix}"


def _bootstrap_install_root(args: argparse.Namespace, target: Path) -> str:
    registry_name = str(args.registry or "public")
    bootstrap_public_registry(
        root=target,
        name=registry_name,
        base_url=_registry_base_url(_profile_base_url(args)),
        set_default=True,
    )
    return registry_name


def _restore(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    registry_name = _bootstrap_install_root(args, target)
    return run_install_exact(
        root=target,
        name=args.qualified_name,
        target_dir=str(target),
        requested_version=args.version,
        source_registry=registry_name,
        force=args.force,
        as_json=True,
    )


def _verify(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser().resolve()
    try:
        manifest = load_install_manifest(target)
    except InstallManifestError as exc:
        raise RuntimeError(str(exc)) from exc
    names = list((manifest.get("skills") or {}).keys())
    requested = args.qualified_name or (names[0] if len(names) == 1 else None)
    if not requested:
        raise RuntimeError("multiple installed Skills found; pass --qualified-name")
    try:
        result = verify_installed_skill(target, requested, root=target)
    except InstalledIntegrityError as exc:
        raise RuntimeError(str(exc)) from exc
    print(
        json.dumps(
            {
                "ok": result.get("state") == "verified",
                "qualified_name": requested,
                **result,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _update(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser().resolve()
    if args.base_url:
        _bootstrap_install_root(args, target)
    try:
        manifest = load_install_manifest(target)
    except InstallManifestError as exc:
        raise RuntimeError(str(exc)) from exc
    names = list((manifest.get("skills") or {}).keys())
    qualified = args.qualified_name or (names[0] if len(names) == 1 else None)
    if not qualified:
        raise RuntimeError("multiple installed Skills found; pass --qualified-name")
    return run_install_upgrade(
        root=target,
        installed_name=qualified,
        target_dir=str(target),
        force=args.force,
        as_json=True,
    )


def configure_agent_cli(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="agent_command")
    join = subparsers.add_parser("join", help="Join an Agent invitation from hidden stdin")
    join.add_argument("--base-url", required=True)
    join.add_argument(
        "--enrollment-token-stdin",
        action="store_true",
        help="Read the one-time enrollment invitation from stdin",
    )
    join.add_argument("--profile", default="default")
    join.set_defaults(_handler=_join)
    status = subparsers.add_parser("status", help="Poll Agent enrollment status")
    status.add_argument("--profile", default="default")
    status.set_defaults(_handler=_status)
    backup = subparsers.add_parser("backup", help="Publish a validated public Skill backup")
    backup.add_argument("source")
    backup.add_argument("--version", required=True)
    backup.add_argument("--repo-root", default=".")
    backup.add_argument("--profile", default="default")
    backup.add_argument("--no-wait", action="store_true")
    backup.set_defaults(_handler=_backup)
    rotate = subparsers.add_parser("rotate-key", help="Rotate the local Agent API key")
    rotate.add_argument("--profile", default="default")
    rotate.set_defaults(_handler=_rotate)
    restore = subparsers.add_parser("restore", help="Restore a public Skill backup")
    restore.add_argument("qualified_name")
    restore.add_argument("target")
    restore.add_argument("--version")
    restore.add_argument("--base-url")
    restore.add_argument("--registry", default="public")
    restore.add_argument("--profile", default="default")
    restore.add_argument("--force", action="store_true")
    restore.set_defaults(_handler=_restore)
    update = subparsers.add_parser("update", help="Update a restored public Skill")
    update.add_argument("target")
    update.add_argument("--qualified-name")
    update.add_argument("--profile", default="default")
    update.add_argument("--base-url")
    update.add_argument("--registry", default="public")
    update.add_argument("--force", action="store_true")
    update.set_defaults(_handler=_update)
    verify_cmd = subparsers.add_parser("verify", help="Verify a restored public Skill distribution")
    verify_cmd.add_argument("target")
    verify_cmd.add_argument("--qualified-name")
    verify_cmd.set_defaults(_handler=_verify)


__all__ = ["configure_agent_cli"]
