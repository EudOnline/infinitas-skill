#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROMOTION_FIXTURE = "promotion-break-glass-fixture"
PROMOTION_EXCEPTION_ID = "promotion-group-waiver"
RELEASE_EXCEPTION_ID = "dirty-worktree-waiver"
PLATFORM_EVIDENCE_MINUTES = {
    "codex": 0,
    "claude": 1,
    "openclaw": 2,
}


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def cli_env(repo: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "src")
    env.setdefault("INFINITAS_SKILL_RELEASER", "lvxiaoer")
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json_output(result, *, command):
    stdout = result.stdout.strip()
    if not stdout:
        fail(f"expected JSON output from {command!r}\nstderr:\n{result.stderr}")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        fail(
            f"expected valid JSON output from {command!r}: {exc}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def contract_checked_at(repo: Path, platform: str):
    profile_path = repo / "profiles" / f"{platform}.json"
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    last_verified = contract.get("last_verified")
    if not isinstance(last_verified, str) or not last_verified:
        fail(f"missing contract.last_verified for platform {platform!r}")
    minute = PLATFORM_EVIDENCE_MINUTES.get(platform, 0)
    return f"{last_verified}T12:{minute:02d}:00Z"


def refresh_platform_evidence(repo: Path, skill_name: str):
    meta_path = repo / "skills" / "active" / skill_name / "_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    version = meta["version"]
    for platform in PLATFORM_EVIDENCE_MINUTES:
        path = (
            repo
            / "catalog"
            / "compatibility-evidence"
            / platform
            / skill_name
            / f"{version}.json"
        )
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        payload.update(
            {
                "platform": platform,
                "skill": skill_name,
                "version": version,
                "state": payload.get("state") or "adapted",
                "checked_at": contract_checked_at(repo, platform),
                "checker": payload.get("checker") or f"check-{platform}-compat.py",
            }
        )
        write_json(path, payload)


def copy_repo(prefix):
    tmpdir = Path(tempfile.mkdtemp(prefix=prefix))
    repo = tmpdir / "repo"
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".worktrees",
            ".planning",
            ".pytest_cache",
            ".ruff_cache",
            ".mypy_cache",
            "__pycache__",
            "*.pyc",
            ".cache",
            "catalog",
            "scripts/__pycache__",
        ),
    )
    compatibility_root = ROOT / "catalog" / "compatibility-evidence"
    if compatibility_root.is_dir():
        shutil.copytree(compatibility_root, repo / "catalog" / "compatibility-evidence")
    else:
        (repo / "catalog" / "compatibility-evidence").mkdir(parents=True, exist_ok=True)
    return tmpdir, repo


def rewrite_promotion_policy(repo: Path):
    write_json(
        repo / "policy" / "promotion-policy.json",
        {
            "$schema": "../schemas/promotion-policy.schema.json",
            "version": 4,
            "active_requires": {
                "review_state": ["under-review"],
                "require_changelog": True,
                "require_smoke_test": True,
                "require_owner": True,
            },
            "reviews": {
                "require_reviews_file": True,
                "reviewer_must_differ_from_owner": True,
                "block_on_rejection": True,
                "groups": {
                    "maintainers": {
                        "members": ["alice"],
                    },
                    "security": {
                        "members": ["bob"],
                    },
                },
                "quorum": {
                    "defaults": {
                        "min_approvals": 1,
                        "required_groups": [],
                    },
                    "stage_overrides": {
                        "active": {
                            "min_approvals": 1,
                            "required_groups": ["maintainers", "security"],
                        },
                    },
                },
            },
            "high_risk_active_requires": {
                "min_maintainers": 1,
                "require_requires_block": True,
            },
            "dependency_rules": {
                "allow_name_only_refs": True,
                "allow_version_pins": True,
                "require_resolvable_refs_for_active": True,
                "auto_install_dependencies_default": True,
            },
        },
    )


def scaffold_promotion_fixture(repo: Path):
    skill_dir = repo / "skills" / "incubating" / PROMOTION_FIXTURE
    shutil.copytree(repo / "templates" / "basic-skill", skill_dir)
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    meta.update(
        {
            "name": PROMOTION_FIXTURE,
            "publisher": "fixture",
            "qualified_name": f"fixture/{PROMOTION_FIXTURE}",
            "version": "0.1.0",
            "status": "incubating",
            "summary": "Fixture skill for break-glass promotion checks.",
            "owner": "owner",
            "owners": ["owner"],
            "author": "owner",
            "maintainers": ["owner"],
            "review_state": "approved",
            "risk_level": "low",
            "distribution": {
                "installable": True,
                "channel": "git",
            },
            "tests": {
                "smoke": "tests/smoke.md",
            },
        }
    )
    write_json(skill_dir / "_meta.json", meta)
    (skill_dir / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.1.0 - 2026-03-15\n- Added fixture.\n", encoding="utf-8"
    )
    (skill_dir / "tests").mkdir(exist_ok=True)
    (skill_dir / "tests" / "smoke.md").write_text(
        "# Smoke\n\nFixture smoke test.\n", encoding="utf-8"
    )
    write_json(
        skill_dir / "reviews.json",
        {
            "version": 1,
            "requests": [
                {
                    "requested_at": "2026-03-15T00:00:00Z",
                    "requested_by": "owner",
                    "note": "Ready for urgent promotion",
                }
            ],
            "entries": [
                {
                    "reviewer": "alice",
                    "decision": "approved",
                    "at": "2026-03-15T00:05:00Z",
                    "note": "Maintainer approved urgent promotion",
                }
            ],
        },
    )
    return skill_dir


def init_git_fixture(repo: Path):
    origin = repo.parent / "origin.git"
    run(["git", "init", "--bare", str(origin)], cwd=repo.parent)
    run(["git", "init", "-b", "main"], cwd=repo)
    run(["git", "config", "user.name", "Break Glass Fixture"], cwd=repo)
    run(["git", "config", "user.email", "break-glass@example.com"], cwd=repo)
    run(["git", "remote", "add", "origin", str(origin)], cwd=repo)
    run(["git", "add", "."], cwd=repo)
    run(["git", "commit", "-m", "fixture repo"], cwd=repo)
    run(["git", "push", "-u", "origin", "main"], cwd=repo)


def write_exception_policy(repo: Path, exceptions):
    write_json(
        repo / "policy" / "exception-policy.json",
        {
            "$schema": "../schemas/exception-policy.schema.json",
            "version": 1,
            "exceptions": exceptions,
        },
    )


def assert_exception_usage(payload, exception_id, *, justification, expires_at):
    usage = payload.get("exception_usage")
    if not isinstance(usage, list) or not usage:
        fail(f"expected non-empty exception_usage list, got {usage!r}")
    record = next((item for item in usage if item.get("id") == exception_id), None)
    if not record:
        fail(f"expected exception_usage entry {exception_id!r}, got {usage!r}")
    if record.get("justification") != justification:
        fail(f"expected justification {justification!r}, got {record.get('justification')!r}")
    if record.get("expires_at") != expires_at:
        fail(f"expected expires_at {expires_at!r}, got {record.get('expires_at')!r}")


def assert_trace_exception(payload, exception_id, *, justification, expires_at):
    trace = payload.get("policy_trace") or {}
    exceptions = trace.get("exceptions")
    if not isinstance(exceptions, list) or not exceptions:
        fail(f"expected policy_trace.exceptions list, got {exceptions!r}")
    record = next((item for item in exceptions if item.get("id") == exception_id), None)
    if not record:
        fail(f"expected trace exception {exception_id!r}, got {exceptions!r}")
    if record.get("justification") != justification:
        fail(f"expected trace justification {justification!r}, got {record.get('justification')!r}")
    if record.get("expires_at") != expires_at:
        fail(f"expected trace expires_at {expires_at!r}, got {record.get('expires_at')!r}")


def scenario_promotion_exception_allows_missing_reviewer_group():
    tmpdir, repo = copy_repo("infinitas-break-glass-promotion-")
    try:
        rewrite_promotion_policy(repo)
        skill_dir = scaffold_promotion_fixture(repo)
        command = [
            *infinitas_cli(repo, "policy", "check-promotion"),
            "--json",
            "--as-active",
            str(skill_dir),
        ]

        baseline = run(command, cwd=repo, expect=1)
        baseline_payload = load_json_output(baseline, command=command)
        baseline_errors = "\n".join(baseline_payload.get("errors") or [])
        if "missing reviewer group coverage for security" not in baseline_errors:
            fail(
                f"expected baseline promotion error to mention missing security coverage, got {baseline_errors!r}"
            )

        expires_at = "2099-01-01T00:00:00Z"
        justification = "Urgent release approved under break-glass procedure"
        write_exception_policy(
            repo,
            [
                {
                    "id": PROMOTION_EXCEPTION_ID,
                    "scope": "promotion",
                    "skills": [PROMOTION_FIXTURE],
                    "rules": ["required-reviewer-groups"],
                    "approved_by": ["incident-commander"],
                    "approved_at": "2026-03-15T00:10:00Z",
                    "justification": justification,
                    "expires_at": expires_at,
                }
            ],
        )

        waived = run(command, cwd=repo, expect=0)
        payload = load_json_output(waived, command=command)
        if payload.get("passed") is not True:
            fail(f"expected promotion check to pass with active exception, got {payload!r}")
        assert_exception_usage(
            payload, PROMOTION_EXCEPTION_ID, justification=justification, expires_at=expires_at
        )
        assert_trace_exception(
            payload, PROMOTION_EXCEPTION_ID, justification=justification, expires_at=expires_at
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_expired_promotion_exception_is_ignored():
    tmpdir, repo = copy_repo("infinitas-break-glass-promotion-expired-")
    try:
        rewrite_promotion_policy(repo)
        skill_dir = scaffold_promotion_fixture(repo)
        write_exception_policy(
            repo,
            [
                {
                    "id": f"{PROMOTION_EXCEPTION_ID}-expired",
                    "scope": "promotion",
                    "skills": [PROMOTION_FIXTURE],
                    "rules": ["required-reviewer-groups"],
                    "approved_by": ["incident-commander"],
                    "approved_at": "2024-01-01T00:00:00Z",
                    "justification": "Expired waiver should not apply",
                    "expires_at": "2024-01-02T00:00:00Z",
                }
            ],
        )
        command = [
            *infinitas_cli(repo, "policy", "check-promotion"),
            "--json",
            "--as-active",
            str(skill_dir),
        ]
        result = run(command, cwd=repo, expect=1)
        payload = load_json_output(result, command=command)
        errors = "\n".join(payload.get("errors") or [])
        if "missing reviewer group coverage for security" not in errors:
            fail(f"expected expired promotion exception to be ignored, got {errors!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_release_exception_allows_dirty_worktree():
    tmpdir, repo = copy_repo("infinitas-break-glass-release-")
    try:
        skill_name = "operate-infinitas-skill"
        skill_ref = "lvxiaoer/operate-infinitas-skill"
        refresh_platform_evidence(repo, skill_name)
        init_git_fixture(repo)
        command = [
            *infinitas_cli(repo, "release", "check-state"),
            skill_name,
            "--mode",
            "preflight",
            "--json",
        ]

        clean = run(command, cwd=repo, expect=0)
        clean_payload = load_json_output(clean, command=command)
        if clean_payload.get("release_ready") is not True:
            fail(f"expected clean preflight release check to pass, got {clean_payload!r}")

        (repo / "DIRTY.txt").write_text("dirty\n", encoding="utf-8")
        dirty = run(command, cwd=repo, expect=1)
        dirty_payload = load_json_output(dirty, command=command)
        dirty_errors = "\n".join(dirty_payload.get("errors") or [])
        if "worktree is dirty" not in dirty_errors:
            fail(f"expected dirty worktree error, got {dirty_errors!r}")

        expires_at = "2099-01-01T00:00:00Z"
        justification = "Dirty worktree waived for emergency release rehearsal"
        write_exception_policy(
            repo,
            [
                {
                    "id": RELEASE_EXCEPTION_ID,
                    "scope": "release",
                    "skills": [skill_ref],
                    "rules": ["dirty-worktree"],
                    "approved_by": ["release-captain"],
                    "approved_at": "2026-03-15T00:20:00Z",
                    "justification": justification,
                    "expires_at": expires_at,
                }
            ],
        )

        waived = run(command, cwd=repo, expect=0)
        payload = load_json_output(waived, command=command)
        if payload.get("release_ready") is not True:
            fail(
                f"expected release preflight to pass with dirty-worktree exception, got {payload!r}"
            )
        assert_exception_usage(
            payload, RELEASE_EXCEPTION_ID, justification=justification, expires_at=expires_at
        )
        assert_trace_exception(
            payload, RELEASE_EXCEPTION_ID, justification=justification, expires_at=expires_at
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_expired_release_exception_is_ignored():
    tmpdir, repo = copy_repo("infinitas-break-glass-release-expired-")
    try:
        refresh_platform_evidence(repo, "operate-infinitas-skill")
        init_git_fixture(repo)
        (repo / "DIRTY.txt").write_text("dirty\n", encoding="utf-8")
        write_exception_policy(
            repo,
            [
                {
                    "id": f"{RELEASE_EXCEPTION_ID}-expired",
                    "scope": "release",
                    "skills": ["lvxiaoer/operate-infinitas-skill"],
                    "rules": ["dirty-worktree"],
                    "approved_by": ["release-captain"],
                    "approved_at": "2024-01-01T00:00:00Z",
                    "justification": "Expired release waiver should not apply",
                    "expires_at": "2024-01-02T00:00:00Z",
                }
            ],
        )
        command = [
            *infinitas_cli(repo, "release", "check-state"),
            "operate-infinitas-skill",
            "--mode",
            "preflight",
            "--json",
        ]
        result = run(command, cwd=repo, expect=1)
        payload = load_json_output(result, command=command)
        errors = "\n".join(payload.get("errors") or [])
        if "worktree is dirty" not in errors:
            fail(f"expected expired release exception to be ignored, got {errors!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_promotion_exception_allows_missing_reviewer_group()
    scenario_expired_promotion_exception_is_ignored()
    scenario_release_exception_allows_dirty_worktree()
    scenario_expired_release_exception_is_ignored()
    print("OK: break-glass exception checks passed")


if __name__ == "__main__":
    main()
