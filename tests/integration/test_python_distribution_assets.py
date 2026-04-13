from __future__ import annotations

import subprocess
import tarfile
import zipfile
from pathlib import Path


def _run_build(repo: Path) -> None:
    result = subprocess.run(
        ["uv", "build"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"uv build failed with exit code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _wheel_members(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        return set(archive.namelist())


def _sdist_members(path: Path) -> set[str]:
    with tarfile.open(path, "r:gz") as archive:
        return set(archive.getnames())


def _assert_contains(members: set[str], expected_suffixes: list[str], *, label: str) -> None:
    for expected in expected_suffixes:
        assert any(member.endswith(expected) for member in members), (
            f"{label} is missing required runtime asset {expected!r}"
        )


def test_python_distribution_artifacts_include_server_runtime_assets(temp_repo_copy: Path) -> None:
    _run_build(temp_repo_copy)

    dist_dir = temp_repo_copy / "dist"
    wheel_path = next(dist_dir.glob("*.whl"))
    sdist_path = next(dist_dir.glob("*.tar.gz"))
    expected_assets = [
        "server/templates/index-kawaii.html",
        "server/static/css/output.css",
        "server/static/js/app.js",
    ]

    _assert_contains(_wheel_members(wheel_path), expected_assets, label="wheel")
    _assert_contains(_sdist_members(sdist_path), expected_assets, label="sdist")
