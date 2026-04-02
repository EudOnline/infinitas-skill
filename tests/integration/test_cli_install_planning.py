from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(
    command: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)


def _prepare_repo() -> tuple[Path, Path]:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-cli-install-planning-"))
    repo = tmpdir / "repo"
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
    return tmpdir, repo


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prepare_target(repo: Path) -> Path:
    target = repo / ".tmp-installed-skills"
    target.mkdir(parents=True, exist_ok=True)
    skill_dir = target / "demo-skill"
    shutil.copytree(repo / "templates" / "basic-skill", skill_dir)
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    meta.update(
        {
            "name": "demo-skill",
            "version": "1.2.3",
            "status": "active",
            "summary": "Demo installed skill",
            "owner": "compat-test",
            "owners": ["compat-test"],
            "author": "compat-test",
            "review_state": "approved",
        }
    )
    _write_json(skill_dir / "_meta.json", meta)
    _write_json(
        target / ".infinitas-skill-install-manifest.json",
        {
            "repo": "https://example.invalid/repo.git",
            "updated_at": "2026-03-12T00:00:00Z",
            "skills": {
                "demo-skill": {
                    "name": "demo-skill",
                    "version": "1.2.3",
                    "locked_version": "1.2.3",
                    "source_registry": "self",
                }
            },
            "history": {},
        },
    )
    return target


def _cli_env(repo: Path) -> dict[str, str]:
    return dict(os.environ, PYTHONPATH=str(repo / "src"))


def _run_cli(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return _run(
        [sys.executable, "-m", "infinitas_skill.cli.main", *args],
        cwd=repo,
        env=_cli_env(repo),
    )


def _run_cli_probe(
    repo: Path,
    args: list[str],
    probe_modules: list[str],
) -> subprocess.CompletedProcess[str]:
    script = (
        "import contextlib, io, json, sys\n"
        "from infinitas_skill.cli.main import main\n"
        "stdout = io.StringIO()\n"
        "stderr = io.StringIO()\n"
        "with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):\n"
        f"    code = main({args!r})\n"
        "payload = {\n"
        "    'returncode': code,\n"
        "    'stdout': stdout.getvalue(),\n"
        "    'stderr': stderr.getvalue(),\n"
        f"    'modules': {{name: name in sys.modules for name in {probe_modules!r}}},\n"
        "}\n"
        "print(json.dumps(payload))\n"
    )
    return _run([sys.executable, "-c", script], cwd=repo, env=_cli_env(repo))


def _load_json_output(result: subprocess.CompletedProcess[str], label: str) -> dict:
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        raise AssertionError(
            f"{label} did not emit JSON output: {exc}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        ) from exc


def _assert_cli_result(
    repo: Path,
    cli_args: list[str],
    *,
    expect_returncode: int,
) -> subprocess.CompletedProcess[str]:
    cli = _run_cli(repo, cli_args)

    assert cli.returncode == expect_returncode, (
        f"CLI command returned {cli.returncode}, expected {expect_returncode}\n"
        f"stdout:\n{cli.stdout}\n"
        f"stderr:\n{cli.stderr}"
    )
    return cli


def _assert_package_owned_install_command(repo: Path, cli_args: list[str]) -> None:
    probe = _run_cli_probe(
        repo,
        cli_args,
        [
            "dependency_lib",
            "infinitas_skill.install.source_resolution",
            "infinitas_skill.install.target_validation",
            "infinitas_skill.install.plan_builder",
            "infinitas_skill.install.output",
        ],
    )
    assert probe.returncode == 0, probe.stderr
    probe_payload = _load_json_output(probe, "install ownership probe")
    assert probe_payload["returncode"] in {0, 1}, probe_payload
    modules = probe_payload["modules"]
    assert not modules.get("dependency_lib")
    for module_name in [
        "infinitas_skill.install.source_resolution",
        "infinitas_skill.install.target_validation",
        "infinitas_skill.install.plan_builder",
        "infinitas_skill.install.output",
    ]:
        assert modules.get(module_name), f"install CLI did not route through {module_name}"


def test_install_cli_handles_success_and_failure_paths() -> None:
    tmpdir, repo = _prepare_repo()
    try:
        target = _prepare_target(repo)
        skill_dir = repo / "templates" / "basic-skill"

        cli = _assert_cli_result(
            repo,
            [
                "install",
                "resolve-plan",
                "--skill-dir",
                str(skill_dir),
                "--target-dir",
                str(target),
                "--json",
            ],
            expect_returncode=0,
        )
        check_target = _assert_cli_result(
            repo,
            [
                "install",
                "check-target",
                str(skill_dir),
                str(target),
            ],
            expect_returncode=0,
        )

        payload = _load_json_output(cli, "install resolve-plan CLI")
        assert payload["root"]["name"] == "basic-skill"
        assert payload["steps"], "expected at least one install planning step"
        assert "OK: install target check passed for basic-skill" in check_target.stdout

        manifest_path = target / ".infinitas-skill-install-manifest.json"
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_payload["schema_version"] = 999
        _write_json(manifest_path, manifest_payload)

        _assert_cli_result(
            repo,
            [
                "install",
                "resolve-plan",
                "--skill-dir",
                str(skill_dir),
                "--target-dir",
                str(target),
                "--json",
            ],
            expect_returncode=1,
        )
        _assert_cli_result(
            repo,
            [
                "install",
                "check-target",
                str(skill_dir),
                str(target),
            ],
            expect_returncode=1,
        )
    finally:
        shutil.rmtree(tmpdir)


def test_install_cli_routes_through_extracted_modules_for_both_commands() -> None:
    tmpdir, repo = _prepare_repo()
    try:
        target = _prepare_target(repo)
        skill_dir = repo / "templates" / "basic-skill"
        _assert_package_owned_install_command(
            repo,
            [
                "install",
                "resolve-plan",
                "--skill-dir",
                str(skill_dir),
                "--target-dir",
                str(target),
                "--json",
            ],
        )
        _assert_package_owned_install_command(
            repo,
            [
                "install",
                "check-target",
                str(skill_dir),
                str(target),
            ],
        )
    finally:
        shutil.rmtree(tmpdir)


def main() -> None:
    test_install_cli_handles_success_and_failure_paths()
    test_install_cli_routes_through_extracted_modules_for_both_commands()
