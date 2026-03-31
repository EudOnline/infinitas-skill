"""Git and tag state helpers for release readiness checks."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

SIGNER_RE = re.compile(r'Good "git" signature for (.+?) with ')
SIGNATURE_MARKERS = ("BEGIN SSH SIGNATURE", "BEGIN PGP SIGNATURE")


class ReleaseError(Exception):
    pass


def git(root, *args, check=True, extra_config=None):
    command = ["git", "-C", str(root)]
    for key, value in (extra_config or {}).items():
        command.extend(["-c", f"{key}={value}"])
    command.extend(args)
    result = subprocess.run(command, text=True, capture_output=True)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise ReleaseError(message)
    return result


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_skill(root, target):
    candidate = Path(target)
    if candidate.is_dir() and (candidate / "_meta.json").exists():
        return candidate.resolve()
    for stage in ["active", "incubating", "archived"]:
        skill_dir = Path(root) / "skills" / stage / target
        if skill_dir.is_dir() and (skill_dir / "_meta.json").exists():
            return skill_dir.resolve()
    raise ReleaseError(f"cannot resolve skill: {target}")


def expected_skill_tag(skill_dir):
    meta = load_json(Path(skill_dir) / "_meta.json")
    return meta, f"skill/{meta['name']}/v{meta['version']}"


def signer_entries(path):
    if not Path(path).exists():
        return []
    entries = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(stripped)
    return entries


def signing_key_path(root, signing):
    env_value = os.environ.get(signing["signing_key_env"])
    if env_value:
        return env_value
    result = git(root, "config", "--get", "user.signingkey", check=False)
    value = result.stdout.strip()
    return value or None


def tracked_upstream(root):
    result = git(root, "rev-parse", "--abbrev-ref", "@{upstream}", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def split_remote(upstream, default_remote):
    if upstream and "/" in upstream:
        return upstream.split("/", 1)[0]
    return default_remote


def ahead_behind(root, upstream):
    if not upstream:
        return None, None
    result = git(root, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
    ahead_text, behind_text = result.stdout.strip().split()
    return int(ahead_text), int(behind_text)


def repo_url(root):
    result = git(root, "config", "--get", "remote.origin.url", check=False)
    return result.stdout.strip() or None


def git_config_value(root, key):
    result = git(root, "config", "--get", key, check=False)
    return result.stdout.strip() or None


def _tag_signature_markers(root, tag_name):
    result = git(root, "cat-file", "-p", tag_name, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout


def local_tag_state(root, tag_name, signing, *, allowed_signer_entries=None):
    state = {
        "exists": False,
        "ref_type": None,
        "target_commit": None,
        "points_to_head": False,
        "signed": False,
        "verified": False,
        "signer": None,
        "verification_output": None,
        "verification_error": None,
    }
    exists = git(
        root,
        "rev-parse",
        "-q",
        "--verify",
        f"refs/tags/{tag_name}",
        check=False,
    )
    if exists.returncode != 0:
        return state
    state["exists"] = True
    ref_type_result = git(root, "cat-file", "-t", f"refs/tags/{tag_name}", check=False)
    state["ref_type"] = ref_type_result.stdout.strip() or None
    target_result = git(root, "rev-parse", f"{tag_name}^{{}}", check=False)
    state["target_commit"] = target_result.stdout.strip() or None
    if state["ref_type"] == "tag":
        payload = _tag_signature_markers(root, tag_name)
        state["signed"] = any(marker in payload for marker in SIGNATURE_MARKERS)
        entries = allowed_signer_entries or []
        if signing["tag_format"] == "ssh" and not entries:
            state["verification_error"] = (
                f"{signing['allowed_signers_rel']} has no signer entries; "
                "add trusted release signers before verifying stable release tags"
            )
            return state
        verify = git(
            root,
            "tag",
            "-v",
            tag_name,
            check=False,
            extra_config={
                "gpg.format": signing["tag_format"],
                "gpg.ssh.allowedSignersFile": str(signing["allowed_signers_path"]),
            },
        )
        combined = (
            "\n".join(
                part for part in [verify.stdout.strip(), verify.stderr.strip()] if part
            ).strip()
            or None
        )
        if verify.returncode == 0:
            state["verified"] = True
            state["verification_output"] = combined
            signer_match = SIGNER_RE.search(combined or "")
            if signer_match:
                state["signer"] = signer_match.group(1).strip()
        else:
            state["verification_error"] = combined or "tag verification failed"
    return state


def remote_tag_state(root, remote_name, tag_name):
    state = {
        "name": remote_name,
        "query_ok": True,
        "query_error": None,
        "tag_exists": False,
        "tag_object": None,
        "target_commit": None,
    }
    if not remote_name:
        state["query_ok"] = False
        state["query_error"] = "no remote configured"
        return state
    result = git(
        root,
        "ls-remote",
        "--tags",
        remote_name,
        f"refs/tags/{tag_name}",
        f"refs/tags/{tag_name}^{{}}",
        check=False,
    )
    if result.returncode != 0:
        state["query_ok"] = False
        state["query_error"] = (
            result.stderr.strip() or result.stdout.strip() or f"cannot query remote {remote_name}"
        )
        return state
    for line in result.stdout.splitlines():
        oid, ref = line.split("\t", 1)
        if ref == f"refs/tags/{tag_name}":
            state["tag_exists"] = True
            state["tag_object"] = oid
        elif ref == f"refs/tags/{tag_name}^{{}}":
            state["tag_exists"] = True
            state["target_commit"] = oid
    return state


__all__ = [
    "ReleaseError",
    "ahead_behind",
    "expected_skill_tag",
    "git",
    "git_config_value",
    "load_json",
    "local_tag_state",
    "remote_tag_state",
    "repo_url",
    "resolve_skill",
    "signer_entries",
    "signing_key_path",
    "split_remote",
    "tracked_upstream",
]
