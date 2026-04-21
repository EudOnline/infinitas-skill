from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURE_NAME = "release-fixture"
V1 = "1.2.3"
V2 = "1.2.4"
PLATFORM_EVIDENCE_MINUTES = {
    "codex": 0,
    "claude": 1,
    "openclaw": 2,
}


def _run(
    command: list[str],
    cwd: Path,
    *,
    expect: int = 0,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if result.returncode != expect:
        raise AssertionError(
            f"command {command!r} exited {result.returncode}, expected {expect}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _regression_env(repo: Path) -> dict[str, str]:
    from infinitas_skill.testing.env import build_regression_test_env

    return build_regression_test_env(
        ROOT,
        extra={"PYTHONPATH": str(repo / "src")},
        env=os.environ.copy(),
    )


def _run_cli(repo: Path, args: list[str], *, expect: int = 0) -> subprocess.CompletedProcess[str]:
    return _run(
        [sys.executable, "-m", "infinitas_skill.cli.main", *args],
        cwd=repo,
        env=_regression_env(repo),
        expect=expect,
    )


def _contract_checked_at(repo: Path, platform: str) -> str:
    profile_path = repo / "profiles" / f"{platform}.json"
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    last_verified = contract.get("last_verified")
    if not isinstance(last_verified, str) or not last_verified:
        raise AssertionError(f"missing contract.last_verified for platform {platform!r}")
    minute = PLATFORM_EVIDENCE_MINUTES.get(platform, 0)
    return f"{last_verified}T12:{minute:02d}:00Z"


def _sync_platform_evidence(repo: Path, version: str) -> None:
    for platform in ("codex", "claude", "openclaw"):
        path = (
            repo
            / "catalog"
            / "compatibility-evidence"
            / platform
            / FIXTURE_NAME
            / f"{version}.json"
        )
        _write_json(
            path,
            {
                "platform": platform,
                "skill": FIXTURE_NAME,
                "version": version,
                "state": "adapted",
                "checked_at": _contract_checked_at(repo, platform),
                "checker": f"check-{platform}-compat.py",
            },
        )


def _update_fixture(repo: Path, version: str) -> None:
    fixture_dir = repo / "skills" / "active" / FIXTURE_NAME
    meta = json.loads((fixture_dir / "_meta.json").read_text(encoding="utf-8"))
    meta.update(
        {
            "name": FIXTURE_NAME,
            "version": version,
            "status": "active",
            "summary": f"Fixture skill version {version} for CLI update workflow tests",
            "owner": "release-test",
            "owners": ["release-test"],
            "maintainers": ["Release Fixture"],
            "author": "release-test",
            "review_state": "approved",
            "distribution": {
                "installable": True,
                "channel": "git",
            },
        }
    )
    _write_json(fixture_dir / "_meta.json", meta)
    (fixture_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {FIXTURE_NAME}\n"
        "description: Fixture skill for CLI update workflow tests.\n"
        "---\n\n"
        "# Release Fixture\n\n"
        f"Current fixture version: {version}.\n",
        encoding="utf-8",
    )
    (fixture_dir / "VERSION.txt").write_text(version + "\n", encoding="utf-8")
    (fixture_dir / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        f"## {version} - 2026-03-12\n"
        f"- Prepared CLI update workflow fixture for {version}.\n",
        encoding="utf-8",
    )
    _write_json(
        fixture_dir / "reviews.json",
        {
            "version": 1,
            "requests": [
                {
                    "requested_at": "2026-03-12T00:00:00Z",
                    "requested_by": "release-test",
                    "note": "Fixture approval for CLI update workflow tests",
                }
            ],
            "entries": [
                {
                    "reviewer": "lvxiaoer",
                    "decision": "approved",
                    "at": "2026-03-12T00:05:00Z",
                    "note": "Fixture approval",
                }
            ],
        },
    )
    _sync_platform_evidence(repo, version)


def _scaffold_fixture(repo: Path, version: str) -> None:
    fixture_dir = repo / "skills" / "active" / FIXTURE_NAME
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    shutil.copytree(ROOT / "templates" / "basic-skill", fixture_dir)
    _update_fixture(repo, version)


def _prepare_repo() -> tuple[Path, Path]:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-cli-update-workflows-"))
    repo = tmpdir / "repo"
    origin = tmpdir / "origin.git"
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(
            ".git",
            ".planning",
            "__pycache__",
            ".cache",
            "scripts/__pycache__",
            ".worktrees",
            ".venv",
        ),
    )
    _scaffold_fixture(repo, V1)
    _run(["git", "init", "--bare", str(origin)], cwd=tmpdir)
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.name", "Release Fixture"], cwd=repo)
    _run(["git", "config", "user.email", "release@example.com"], cwd=repo)
    _run(["git", "remote", "add", "origin", str(origin)], cwd=repo)
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "fixture repo"], cwd=repo)
    _run(["git", "push", "-u", "origin", "main"], cwd=repo)
    _run([str(repo / "scripts" / "build-catalog.sh")], cwd=repo)
    _run(["git", "add", "catalog"], cwd=repo)
    _run(["git", "commit", "-m", "build fixture catalog"], cwd=repo)
    _run(["git", "push"], cwd=repo)

    key_path = tmpdir / "release-test-key"
    identity = "release-test"
    _run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", identity, "-f", str(key_path)],
        cwd=repo,
    )
    with (repo / "config" / "allowed_signers").open("a", encoding="utf-8") as handle:
        public_key = Path(str(key_path) + ".pub").read_text(encoding="utf-8").strip()
        handle.write(f"{identity} {public_key}\n")
    _run(["git", "config", "gpg.format", "ssh"], cwd=repo)
    _run(["git", "config", "user.signingkey", str(key_path)], cwd=repo)
    _run(["git", "add", "config/allowed_signers"], cwd=repo)
    _run(["git", "commit", "-m", "add release signer"], cwd=repo)
    _run(["git", "push"], cwd=repo)

    env = _regression_env(repo)
    _run(
        [
            str(repo / "scripts" / "release-skill.sh"),
            FIXTURE_NAME,
            "--push-tag",
            "--write-provenance",
        ],
        cwd=repo,
        env=env,
    )

    _update_fixture(repo, V2)
    _run([str(repo / "scripts" / "build-catalog.sh")], cwd=repo)
    _run(["git", "add", f"skills/active/{FIXTURE_NAME}", "catalog"], cwd=repo)
    _run(["git", "commit", "-m", f"fixture {V2}"], cwd=repo)
    _run(["git", "push"], cwd=repo)
    _run(
        [
            str(repo / "scripts" / "release-skill.sh"),
            FIXTURE_NAME,
            "--push-tag",
            "--write-provenance",
        ],
        cwd=repo,
        env=env,
    )

    shutil.rmtree(repo / "skills" / "active" / FIXTURE_NAME)
    return tmpdir, repo


def test_install_cli_exposes_check_update_and_upgrade_workflows() -> None:
    tmpdir, repo = _prepare_repo()
    try:
        target_dir = tmpdir / "installed"
        install = _run_cli(
            repo,
            ["install", "by-name", FIXTURE_NAME, str(target_dir), "--version", V1, "--json"],
        )
        assert install.returncode == 0, install.stdout + install.stderr

        update_check = _run_cli(
            repo,
            ["install", "check-update", FIXTURE_NAME, str(target_dir), "--json"],
        )
        assert update_check.returncode == 0, update_check.stdout + update_check.stderr
        update_payload = json.loads(update_check.stdout)
        assert update_payload["installed_version"] == V1
        assert update_payload["latest_available_version"] == V2
        assert update_payload["update_available"] is True
        assert update_payload["state"] == "update-available"

        upgrade = _run_cli(
            repo,
            ["install", "upgrade", FIXTURE_NAME, str(target_dir), "--mode", "confirm", "--json"],
        )
        assert upgrade.returncode == 0, upgrade.stdout + upgrade.stderr
        upgrade_payload = json.loads(upgrade.stdout)
        assert upgrade_payload["state"] == "planned"
        assert upgrade_payload["from_version"] == V1
        assert upgrade_payload["to_version"] == V2
        assert upgrade_payload["source_registry"] == "self"
    finally:
        shutil.rmtree(tmpdir)
