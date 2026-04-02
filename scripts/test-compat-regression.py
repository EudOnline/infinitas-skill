#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def cli_env(repo: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "src")
    return env


def infinitas_cli(repo: Path, *args: str) -> list[str]:
    return [sys.executable, "-m", "infinitas_skill.cli.main", *args]


def run(command, cwd, expect=0):
    result = subprocess.run(
        command, cwd=cwd, text=True, capture_output=True, env=cli_env(Path(cwd))
    )
    if result.returncode != expect:
        fail(
            f"command {command!r} exited {result.returncode}, expected {expect}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-compat-regression-"))
    repo = tmpdir / "repo"
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(
            ".git", ".planning", "__pycache__", ".cache", "scripts/__pycache__"
        ),
    )
    return tmpdir, repo


def scaffold_skill(
    repo: Path,
    stage: str,
    dir_name: str,
    *,
    version: str,
    publisher="lvxiaoer",
    snapshot_of=None,
    snapshot_created_at=None,
    with_schema=True,
):
    skill_dir = repo / "skills" / stage / dir_name
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    shutil.copytree(repo / "templates" / "basic-skill", skill_dir)
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    meta.update(
        {
            "name": "demo-skill",
            "publisher": publisher,
            "qualified_name": f"{publisher}/demo-skill",
            "version": version,
            "status": stage,
            "summary": f"Demo skill version {version}",
            "owner": publisher,
            "owners": [publisher],
            "author": publisher,
            "review_state": "approved" if stage == "active" else "draft",
        }
    )
    if snapshot_of is not None:
        meta["snapshot_of"] = snapshot_of
    if snapshot_created_at is not None:
        meta["snapshot_created_at"] = snapshot_created_at
    if not with_schema:
        meta.pop("schema_version", None)
    write_json(skill_dir / "_meta.json", meta)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo-skill\n"
        "description: Demo skill for compatibility regression tests.\n"
        "---\n\n"
        "# Demo Skill\n",
        encoding="utf-8",
    )
    (skill_dir / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## {version} - 2026-03-12\n- Fixture entry.\n",
        encoding="utf-8",
    )
    return skill_dir


def prepare_installed_target(repo: Path):
    target = repo / ".tmp-installed-skills"
    target.mkdir(parents=True, exist_ok=True)
    installed_dir = target / "demo-skill"
    shutil.copytree(repo / "templates" / "basic-skill", installed_dir)
    meta = json.loads((installed_dir / "_meta.json").read_text(encoding="utf-8"))
    meta.update(
        {
            "name": "demo-skill",
            "publisher": "lvxiaoer",
            "qualified_name": "lvxiaoer/demo-skill",
            "version": "1.2.3",
            "status": "active",
            "summary": "Installed demo skill",
            "owner": "lvxiaoer",
            "owners": ["lvxiaoer"],
            "author": "lvxiaoer",
            "review_state": "approved",
        }
    )
    write_json(installed_dir / "_meta.json", meta)
    (installed_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo-skill\n"
        "description: Installed demo skill for compatibility regression tests.\n"
        "---\n\n"
        "# Installed Demo Skill\n",
        encoding="utf-8",
    )
    manifest = {
        "repo": "https://example.invalid/repo.git",
        "updated_at": "2026-03-12T00:00:00Z",
        "skills": {
            "demo-skill": {
                "name": "demo-skill",
                "publisher": "lvxiaoer",
                "qualified_name": "lvxiaoer/demo-skill",
                "version": "1.2.3",
                "locked_version": "1.2.3",
                "source_registry": "self",
                "source_qualified_name": "lvxiaoer/demo-skill",
            }
        },
        "history": {},
    }
    write_json(target / ".infinitas-skill-install-manifest.json", manifest)
    return target


def main():
    tmpdir, repo = prepare_repo()
    try:
        scaffold_skill(repo, "active", "demo-skill", version="1.2.4", with_schema=False)
        scaffold_skill(
            repo,
            "archived",
            "demo-skill--v1.2.3--20260312T000000Z",
            version="1.2.3",
            snapshot_of="demo-skill@1.2.3",
            snapshot_created_at="2026-03-12T00:00:00Z",
        )
        target = prepare_installed_target(repo)

        result = run([sys.executable, str(repo / "scripts" / "validate-registry.py")], cwd=repo)
        combined = result.stdout + result.stderr
        if "validated " not in combined or "skill directories" not in combined:
            fail(f"legacy _meta.json without schema_version should still validate\n{combined}")

        result = run([str(repo / "scripts" / "list-installed.sh"), str(target)], cwd=repo)
        combined = result.stdout + result.stderr
        if "- lvxiaoer/demo-skill: 1.2.3" not in combined:
            fail(f"legacy install manifest without schema_version should still load\n{combined}")

        result = run(
            [
                sys.executable,
                str(repo / "scripts" / "resolve-skill-source.py"),
                "demo-skill",
                "--json",
            ],
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        if payload.get("qualified_name") != "lvxiaoer/demo-skill":
            fail(
                f"bare skill name should still resolve with qualified identity present\n{result.stdout}"
            )

        result = run(
            [
                sys.executable,
                str(repo / "scripts" / "resolve-skill-source.py"),
                "demo-skill",
                "--version",
                "1.2.3",
                "--json",
            ],
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        if (
            payload.get("stage") != "archived"
            or payload.get("resolution_reason") != "archived-exact-snapshot"
        ):
            fail(f"archived exact-version snapshot should resolve\n{result.stdout}")

        result = run(
            infinitas_cli(
                repo,
                "install",
                "resolve-plan",
                "--skill-dir",
                str(repo / "skills" / "active" / "demo-skill"),
                "--target-dir",
                str(target),
                "--mode",
                "sync",
                "--json",
            ),
            cwd=repo,
            expect=1,
        )
        combined = result.stdout + result.stderr
        if "locked to 1.2.3" not in combined:
            fail(f"locked install should refuse unsafe upgrade\n{combined}")
    finally:
        shutil.rmtree(tmpdir)

    print("OK: compatibility regression checks passed")


if __name__ == "__main__":
    main()
