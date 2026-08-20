from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from infinitas_skill.agent.profile import (
    fingerprint,
    new_keys,
    read_profile,
    verifier,
    write_profile,
)
from infinitas_skill.install.distribution_materialization import safely_extract_bundle
from infinitas_skill.install.distribution_verification import verify_distribution_manifest
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


def _download(url: str, destination: Path, token: str = "") -> None:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Registry returned HTTP {exc.code} while downloading artifact") from exc


def _public_entry(base_url: str, qualified_name: str, version: str | None = None) -> dict:
    payload = _request(base_url, "GET", "/api/v1/registry/distributions.json")
    entries = payload.get("skills", []) if isinstance(payload, dict) else []
    matches = [item for item in entries if item.get("qualified_name") == qualified_name]
    if version:
        matches = [item for item in matches if item.get("version") == version]
    if not matches:
        raise RuntimeError(
            f"public skill not found: {qualified_name}{'@' + version if version else ''}"
        )
    return sorted(matches, key=lambda item: str(item.get("version", "")), reverse=True)[0]


def _fetch_distribution(
    base_url: str, entry: dict, token: str = ""
) -> tuple[Path, Path, tempfile.TemporaryDirectory]:
    temp = tempfile.TemporaryDirectory(prefix="infinitas-agent-restore-")
    root = Path(temp.name)
    manifest = root / str(entry["manifest_path"])
    bundle = root / str(entry["bundle_path"])
    provenance = root / str(entry["attestation_path"])
    signature = root / str(entry["attestation_signature_path"])
    for path in (manifest, bundle, provenance, signature):
        _download(
            f"{base_url.rstrip('/')}/api/v1/registry/{path.relative_to(root).as_posix()}",
            path,
            token,
        )
    verified = verify_distribution_manifest(manifest, root=root, attestation_root=root)
    expected = entry.get("bundle_sha256")
    if expected and hashlib.sha256(
        verified["bundle_path"].read_bytes()
    ).hexdigest() != expected.removeprefix("sha256:"):
        raise RuntimeError("public registry bundle digest mismatch")
    return manifest, verified["bundle_path"], temp


def _restore(args: argparse.Namespace) -> int:
    profile = read_profile(args.profile)
    base_url = str(args.base_url or profile["base_url"])
    entry = _public_entry(base_url, args.qualified_name, args.version)
    manifest, bundle, temp = _fetch_distribution(base_url, entry)
    try:
        target = Path(args.target).expanduser().resolve()
        if target.exists() and any(target.iterdir()) and not args.force:
            raise RuntimeError(f"target is not empty: {target} (use --force)")
        target.mkdir(parents=True, exist_ok=True)
        extracted = safely_extract_bundle(
            bundle, target / ".staging", expected_root=(entry.get("name") or "")
        )
        source = Path(extracted)
        for item in source.iterdir():
            destination = target / item.name
            if destination.exists() and destination.is_dir():
                shutil.rmtree(destination)
            elif destination.exists():
                destination.unlink()
            shutil.move(str(item), destination)
        distribution_dir = target / ".infinitas-distribution"
        shutil.copytree(Path(temp.name), distribution_dir, dirs_exist_ok=True)
        shutil.rmtree(target / ".staging", ignore_errors=True)
        print(
            json.dumps(
                {
                    "ok": True,
                    "qualified_name": entry["qualified_name"],
                    "version": entry["version"],
                    "target": str(target),
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        temp.cleanup()


def _verify(args: argparse.Namespace) -> int:
    root = Path(args.target).expanduser().resolve()
    candidates = sorted((root / ".infinitas-distribution").rglob("manifest.json"))
    manifest = candidates[0] if candidates else root / "manifest.json"
    result = verify_distribution_manifest(manifest, root=root, attestation_root=root)
    print(
        json.dumps(
            {
                "ok": True,
                "manifest": str(manifest),
                "bundle_sha256": result["manifest"]["bundle"]["sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def _update(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser().resolve()
    metadata = target / "_meta.json"
    if not metadata.is_file():
        raise RuntimeError("target does not contain _meta.json; pass --name explicitly")
    payload = json.loads(metadata.read_text(encoding="utf-8"))
    qualified = args.qualified_name or payload.get("qualified_name")
    if not qualified:
        raise RuntimeError("could not determine qualified skill name")
    args.qualified_name = qualified
    args.version = None
    args.force = True
    return _restore(args)


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
    restore = subparsers.add_parser("restore", help="Restore a public Skill backup")
    restore.add_argument("qualified_name")
    restore.add_argument("target")
    restore.add_argument("--version")
    restore.add_argument("--base-url")
    restore.add_argument("--profile", default="default")
    restore.add_argument("--force", action="store_true")
    restore.set_defaults(_handler=_restore)
    update = subparsers.add_parser("update", help="Update a restored public Skill")
    update.add_argument("target")
    update.add_argument("--qualified-name")
    update.add_argument("--profile", default="default")
    update.add_argument("--base-url")
    update.set_defaults(_handler=_update)
    verify_cmd = subparsers.add_parser("verify", help="Verify a restored public Skill distribution")
    verify_cmd.add_argument("target")
    verify_cmd.set_defaults(_handler=_verify)


__all__ = ["configure_agent_cli"]
