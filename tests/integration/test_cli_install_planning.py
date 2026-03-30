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


def test_install_resolve_plan_cli_matches_legacy_json_and_routes_through_extracted_modules(
) -> None:
    tmpdir, repo = _prepare_repo()
    try:
        target = _prepare_target(repo)
        skill_dir = repo / "templates" / "basic-skill"
        cli = _run(
            [
                sys.executable,
                "-m",
                "infinitas_skill.cli.main",
                "install",
                "resolve-plan",
                "--skill-dir",
                str(skill_dir),
                "--target-dir",
                str(target),
                "--json",
            ],
            cwd=repo,
            env=_cli_env(repo),
        )
        legacy = _run(
            [
                sys.executable,
                str(repo / "scripts" / "resolve-install-plan.py"),
                "--skill-dir",
                str(skill_dir),
                "--target-dir",
                str(target),
                "--json",
            ],
            cwd=repo,
        )

        assert cli.returncode == 0, cli.stderr
        assert legacy.returncode == 0, legacy.stderr
        assert cli.stdout == legacy.stdout
        assert cli.stderr == legacy.stderr

        payload = _load_json_output(cli, "install resolve-plan CLI")
        assert payload["root"]["name"] == "basic-skill"
        assert payload["steps"], "expected at least one install planning step"

        probe = _run_cli_probe(
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
        assert probe_payload["returncode"] == 0, probe_payload
        modules = probe_payload["modules"]
        assert not modules.get("dependency_lib")
        for module_name in [
            "infinitas_skill.install.source_resolution",
            "infinitas_skill.install.target_validation",
            "infinitas_skill.install.plan_builder",
            "infinitas_skill.install.output",
        ]:
            assert modules.get(module_name), f"install CLI did not route through {module_name}"
    finally:
        shutil.rmtree(tmpdir)


def main() -> None:
    test_install_resolve_plan_cli_matches_legacy_json_and_routes_through_extracted_modules()
