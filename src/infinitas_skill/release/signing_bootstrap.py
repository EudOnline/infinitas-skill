"""SSH signing bootstrap helpers for release flows."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from infinitas_skill.root import ROOT

KEY_PREFIXES = ("ssh-", "ecdsa-", "sk-")


class SigningBootstrapError(Exception):
    pass


JsonDict = dict[str, Any]


def load_json(path: str | Path) -> JsonDict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: object) -> None:
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_public_key(value: str | None) -> str | None:
    tokens = (value or "").strip().split()
    for index, token in enumerate(tokens):
        if token.startswith(KEY_PREFIXES):
            if index + 1 >= len(tokens):
                return None
            return f"{token} {tokens[index + 1]}"
    return None


def parse_allowed_signers(path: str | Path) -> list[JsonDict]:
    entries: list[dict[str, Any]] = []
    path = Path(path)
    if not path.exists():
        return entries
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 1)
        if len(parts) < 2 or not parts[0].strip() or not normalize_public_key(parts[1]):
            raise SigningBootstrapError(
                f'{path} line {line_number} must use "<identity> <public-key>" format'
            )
        identity = parts[0].strip()
        public_key = parts[1].strip()
        entries.append(
            {
                "line_number": line_number,
                "identity": identity,
                "public_key": public_key,
                "normalized_key": normalize_public_key(public_key),
            }
        )
    return entries


def public_key_from_private_key(path: str | Path) -> str:
    result = subprocess.run(
        ["ssh-keygen", "-y", "-f", str(path)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "ssh-keygen failed"
        raise SigningBootstrapError(f"cannot derive public key from {path}: {message}")
    return result.stdout.strip()


def public_key_from_file(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8").strip()
    if not normalize_public_key(text):
        raise SigningBootstrapError(f"{path} does not contain a valid SSH public key")
    return text


def public_key_from_key_path(path: str | Path) -> str:
    key_path = Path(path).expanduser()
    if not key_path.exists():
        raise SigningBootstrapError(f"key path does not exist: {key_path}")
    if key_path.suffix == ".pub":
        return public_key_from_file(key_path)
    return public_key_from_private_key(key_path)


def upsert_allowed_signer(path: str | Path, identity: str, public_key: str) -> JsonDict:
    allowed_path = Path(path)
    existing_lines = (
        allowed_path.read_text(encoding="utf-8").splitlines() if allowed_path.exists() else []
    )
    desired_line = f"{identity} {public_key.strip()}"
    new_lines: list[str] = []
    replaced = False
    changed = False
    matched_existing = False
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            new_lines.append(line)
            continue
        if parts[0].strip() != identity:
            new_lines.append(line)
            continue
        matched_existing = True
        if not replaced:
            new_lines.append(desired_line)
            replaced = True
            if stripped != desired_line:
                changed = True
        else:
            changed = True
    if not matched_existing:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(desired_line)
        changed = True
    if changed:
        allowed_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return {
        "changed": changed,
        "action": "updated" if matched_existing else "added",
        "line": desired_line,
    }


def configure_git_signing(root: str | Path, key_path: str | Path, scope: str = "local") -> None:
    commands = [
        ["git", "config", "gpg.format", "ssh"],
        ["git", "config", "user.signingkey", str(Path(key_path).expanduser())],
    ]
    if scope == "global":
        commands = [command[:2] + ["--global"] + command[2:] for command in commands]
    for command in commands:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "git config failed"
            raise SigningBootstrapError(message)


def update_namespace_policy(
    path: str | Path,
    publisher: str,
    *,
    signers: list[str] | None = None,
    releasers: list[str] | None = None,
) -> JsonDict:
    policy_path = Path(path)
    payload = load_json(policy_path)
    raw_publishers = payload.get("publishers")
    publishers: JsonDict = dict(raw_publishers) if isinstance(raw_publishers, dict) else {}
    if publisher not in publishers:
        raise SigningBootstrapError(f"publisher {publisher!r} is not declared in {policy_path}")
    entry = publishers[publisher]
    if not isinstance(entry, dict):
        raise SigningBootstrapError(f"publisher {publisher!r} must be an object")
    changed = False
    summary: JsonDict = {}
    for key, additions in [
        ("authorized_signers", signers or []),
        ("authorized_releasers", releasers or []),
    ]:
        current = entry.get(key)
        if not isinstance(current, list):
            current = []
        merged: list[str] = []
        for value in [*current, *additions]:
            if not isinstance(value, str):
                continue
            text = value.strip()
            if not text or text in merged:
                continue
            merged.append(text)
        if merged != current:
            entry[key] = merged
            changed = True
        summary[key] = list(entry.get(key, []))
    if changed:
        write_json(policy_path, payload)
    return {"changed": changed, "summary": summary}


def current_git_value(root: str | Path, key: str) -> str | None:
    result = subprocess.run(
        ["git", "config", "--get", key],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def signer_identities_for_key(entries: list[JsonDict], public_key: str) -> list[str]:
    normalized = normalize_public_key(public_key)
    if not normalized:
        return []
    matches: list[str] = []
    for entry in entries:
        if entry.get("normalized_key") == normalized and entry.get("identity") not in matches:
            matches.append(entry["identity"])
    return matches


def default_allowed_signers_path(root: str | Path = ROOT) -> Path:
    config = load_json(Path(root) / "config" / "signing.json")
    tag_cfg = config.get("git_tag") or {}
    allowed_rel = (
        tag_cfg.get("allowed_signers") or config.get("allowed_signers") or "config/allowed_signers"
    )
    return (Path(root) / allowed_rel).resolve()


def default_namespace_policy_path(root: str | Path = ROOT) -> Path:
    return (Path(root) / "policy" / "namespace-policy.json").resolve()


__all__ = [
    "KEY_PREFIXES",
    "SigningBootstrapError",
    "load_json",
    "write_json",
    "normalize_public_key",
    "parse_allowed_signers",
    "public_key_from_private_key",
    "public_key_from_file",
    "public_key_from_key_path",
    "upsert_allowed_signer",
    "configure_git_signing",
    "update_namespace_policy",
    "current_git_value",
    "signer_identities_for_key",
    "default_allowed_signers_path",
    "default_namespace_policy_path",
]
