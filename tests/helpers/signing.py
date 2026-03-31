from __future__ import annotations

import subprocess
from pathlib import Path


def generate_signing_key(base: Path, *, identity: str) -> Path:
    key_path = base / f"{identity}-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", identity, "-f", str(key_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return key_path


def add_allowed_signer(allowed_signers_path: Path, *, identity: str, key_path: Path) -> None:
    allowed_signers_path.parent.mkdir(parents=True, exist_ok=True)
    public_key = Path(str(key_path) + ".pub").read_text(encoding="utf-8").strip()
    with allowed_signers_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{identity} {public_key}\n")


def configure_git_ssh_signing(repo: Path, key_path: Path) -> None:
    subprocess.run(["git", "config", "gpg.format", "ssh"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.signingkey", str(key_path)], cwd=repo, check=True, capture_output=True, text=True)
