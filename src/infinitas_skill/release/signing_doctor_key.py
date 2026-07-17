"""Signing-key diagnostic used by the release doctor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infinitas_skill.release.signing_bootstrap import (
    SigningBootstrapError,
    public_key_from_key_path,
    signer_identities_for_key,
)
from infinitas_skill.release.state import signing_key_path


def make_check(
    check_id: str,
    status: str,
    summary: str,
    *,
    detail: str | None = None,
    fixes: list[str] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "summary": summary,
        "detail": detail,
        "fixes": fixes or [],
        "data": data or {},
    }


def check_signing_key(
    signing: dict[str, Any],
    allowed_entries: list[dict[str, Any]],
    identity: str | None,
    root: Path,
) -> tuple[list[str], list[dict[str, Any]]]:
    configured_key = signing_key_path(root, signing)
    if not configured_key:
        identity_hint = identity or "release-signer"
        return [], [
            make_check(
                "signing-key",
                "fail",
                "No SSH signing key is configured for stable release tags",
                detail=(
                    f"Set `{signing['signing_key_env']}` or `git config user.signingkey` "
                    "to a private SSH key path."
                ),
                fixes=[
                    "Create a key with "
                    "`uv run infinitas release bootstrap-signing init-key "
                    f"--identity {identity_hint} "
                    "--output ~/.ssh/infinitas-skill-release-signing`",
                    "Point git at that key with `uv run infinitas release bootstrap-signing "
                    "configure-git --key ~/.ssh/infinitas-skill-release-signing`",
                ],
            )
        ]
    key_path = Path(configured_key).expanduser()
    if not key_path.exists():
        return [], [
            make_check(
                "signing-key",
                "fail",
                f"Configured SSH signing key does not exist: {key_path}",
                detail=(
                    "Release tag creation cannot succeed until the configured "
                    "private key path is present."
                ),
                fixes=[
                    "Update the key path in git config or recreate the key with "
                    "`uv run infinitas release bootstrap-signing init-key ...`"
                ],
            )
        ]
    try:
        configured_public_key = public_key_from_key_path(key_path)
    except SigningBootstrapError as exc:
        return [], [
            make_check(
                "signing-key", "fail", "Cannot read configured SSH signing key", detail=str(exc)
            )
        ]
    inferred = signer_identities_for_key(allowed_entries, configured_public_key)
    if allowed_entries and not inferred:
        identity_hint = identity or "release-signer"
        return [], [
            make_check(
                "signing-key-trust",
                "fail",
                "Configured SSH signing key is not trusted by the repository",
                detail=(
                    f"The key at `{key_path}` is not present in `{signing['allowed_signers_rel']}`."
                ),
                fixes=[
                    "Run `uv run infinitas release bootstrap-signing add-allowed-signer "
                    f"--identity {identity_hint} --key {key_path}`",
                    f"Commit and push the updated `{signing['allowed_signers_rel']}` "
                    "before tagging",
                ],
            )
        ]
    detail = f"Configured key path: {key_path}"
    if inferred:
        detail += "; matched identities: " + ", ".join(inferred)
    return inferred, [
        make_check(
            "signing-key", "ok", "An SSH signing key is configured for release tags", detail=detail
        )
    ]
