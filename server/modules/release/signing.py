"""SSH signing logic for the release materializer.

Handles SSH key-based provenance signing and signer identity resolution.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import cast

from infinitas_skill.release.signing_bootstrap import (
    parse_allowed_signers,
    public_key_from_key_path,
    signer_identities_for_key,
)


def resolve_signer_identity(
    *,
    repo_root: Path,
    allowed_signers_path: Path,
    signing_key: str,
) -> str:
    entries = parse_allowed_signers(allowed_signers_path)
    if not entries:
        raise RuntimeError(
            f"{allowed_signers_path.relative_to(repo_root)} has no signer entries; "
            "materialized releases require trusted SSH signers"
        )
    public_key = public_key_from_key_path(signing_key)
    identities = signer_identities_for_key(entries, public_key)
    if not identities:
        raise RuntimeError(
            f"configured signing key {signing_key} is not trusted by "
            f"{allowed_signers_path.relative_to(repo_root)}"
        )
    return cast(str, identities[0])


def sign_provenance(
    *,
    provenance_bytes: bytes,
    provenance_filename: str,
    signing_key: str,
    namespace: str,
    signature_ext: str,
) -> bytes:
    with tempfile.TemporaryDirectory(prefix="infinitas-release-provenance-") as temp_dir:
        provenance_path = Path(temp_dir) / provenance_filename
        provenance_path.write_bytes(provenance_bytes)
        signature_path = Path(f"{provenance_path}{signature_ext}")
        signature_path.unlink(missing_ok=True)
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(Path(signing_key).expanduser()),
                "-n",
                namespace,
                str(provenance_path),
            ],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "ssh-keygen failed"
            raise RuntimeError(f"could not sign release provenance: {message}")
        generated_signature = Path(f"{provenance_path}.sig")
        if generated_signature.exists():
            generated_signature.replace(signature_path)
        if not signature_path.exists():
            raise RuntimeError("ssh-keygen did not produce a provenance signature file")
        return signature_path.read_bytes()
