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


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-team-governance-"))
    repo = tmpdir / "repo"
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(
            ".git",
            ".worktrees",
            ".planning",
            "__pycache__",
            ".cache",
            "catalog",
            "scripts/__pycache__",
        ),
    )
    return tmpdir, repo


def scaffold_skill(
    repo: Path,
    stage: str,
    folder_name: str,
    *,
    name: str,
    publisher: str,
    owners,
    maintainers=None,
):
    skill_dir = repo / "skills" / stage / folder_name
    shutil.copytree(repo / "templates" / "basic-skill", skill_dir)
    meta_path = skill_dir / "_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    maintainers = maintainers or list(owners)
    meta.update(
        {
            "name": name,
            "version": "0.1.0",
            "status": stage,
            "summary": f"Fixture skill {name} for delegated team governance tests.",
            "owner": owners[0],
            "owners": list(owners),
            "author": owners[0],
            "maintainers": list(maintainers),
            "publisher": publisher,
            "qualified_name": f"{publisher}/{name}",
            "review_state": "draft",
            "risk_level": "medium",
        }
    )
    write_json(meta_path, meta)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: Fixture skill for delegated team governance tests.\n"
        "---\n\n"
        f"# {name}\n",
        encoding="utf-8",
    )
    (skill_dir / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.1.0 - 2026-03-15\n- Added delegated team governance fixture.\n",
        encoding="utf-8",
    )
    write_json(skill_dir / "reviews.json", {"version": 1, "requests": [], "entries": []})
    return skill_dir


def write_team_policy(repo: Path):
    write_json(
        repo / "policy" / "team-policy.json",
        {
            "$schema": "../schemas/team-policy.schema.json",
            "version": 1,
            "teams": {
                "platform-admins": {
                    "members": ["alice"],
                    "description": "Platform administrators allowed to own team-backed publishers.",
                },
                "release-owners": {
                    "members": ["owner"],
                    "description": "Delegated publisher owners for team-backed fixtures.",
                },
                "security-review": {
                    "members": ["bob"],
                    "description": "Security reviewers required for delegated approval scopes.",
                },
            },
        },
    )


def write_namespace_policy(repo: Path, *, owner_teams, maintainer_teams):
    write_json(
        repo / "policy" / "namespace-policy.json",
        {
            "$schema": "../schemas/namespace-policy.schema.json",
            "version": 1,
            "compatibility": {
                "allow_unqualified_names": True,
            },
            "publishers": {
                "teamco": {
                    "owner_teams": list(owner_teams),
                    "maintainer_teams": list(maintainer_teams),
                    "authorized_signer_teams": list(owner_teams),
                    "authorized_releaser_teams": list(owner_teams),
                }
            },
            "transfers": [],
        },
    )


def write_promotion_policy(repo: Path):
    write_json(
        repo / "policy" / "promotion-policy.json",
        {
            "$schema": "../schemas/promotion-policy.schema.json",
            "version": 4,
            "active_requires": {
                "review_state": ["approved"],
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
                        "teams": ["platform-admins"],
                    },
                    "security": {
                        "teams": ["security-review"],
                    },
                },
                "quorum": {
                    "defaults": {
                        "min_approvals": 1,
                        "required_groups": [],
                    },
                    "stage_overrides": {
                        "active": {
                            "min_approvals": 2,
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


def scenario_namespace_team_authorization_passes():
    tmpdir, repo = prepare_repo()
    try:
        write_team_policy(repo)
        write_namespace_policy(
            repo, owner_teams=["platform-admins"], maintainer_teams=["platform-admins"]
        )
        skill_dir = scaffold_skill(
            repo,
            "active",
            "team-namespace-fixture",
            name="team-namespace-fixture",
            publisher="teamco",
            owners=["alice"],
            maintainers=["alice"],
        )
        run(
            [sys.executable, str(repo / "scripts" / "validate-registry.py"), str(skill_dir)],
            cwd=repo,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_namespace_team_failure_is_structured():
    tmpdir, repo = prepare_repo()
    try:
        write_team_policy(repo)
        write_namespace_policy(
            repo, owner_teams=["platform-admins"], maintainer_teams=["platform-admins"]
        )
        skill_dir = scaffold_skill(
            repo,
            "active",
            "team-namespace-blocked",
            name="team-namespace-blocked",
            publisher="teamco",
            owners=["mallory"],
            maintainers=["mallory"],
        )
        command = [
            sys.executable,
            str(repo / "scripts" / "validate-registry.py"),
            "--json",
            str(skill_dir),
        ]
        result = run(command, cwd=repo, expect=1)
        payload = load_json_output(result, command=command)
        validation_errors = payload.get("validation_errors") or []
        skill_rel = str(skill_dir.relative_to(repo))
        entry = next(
            (item for item in validation_errors if item.get("skill_path") == skill_rel), None
        )
        if not entry:
            fail(f"expected validation error entry for {skill_rel!r}, got {validation_errors!r}")
        errors = entry.get("errors") or []
        if not any(
            "authorized owners" in message or "authorized for publisher" in message
            for message in errors
        ):
            fail(f"unexpected delegated-team validation errors: {errors!r}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_team_review_scope_and_policy_trace():
    tmpdir, repo = prepare_repo()
    try:
        write_team_policy(repo)
        write_namespace_policy(
            repo, owner_teams=["release-owners"], maintainer_teams=["platform-admins"]
        )
        write_promotion_policy(repo)
        skill_dir = scaffold_skill(
            repo,
            "incubating",
            "delegated-review-fixture",
            name="delegated-review-fixture",
            publisher="teamco",
            owners=["owner"],
            maintainers=["alice"],
        )

        run(
            [
                str(repo / "scripts" / "request-review.sh"),
                "delegated-review-fixture",
                "--note",
                "Delegated team review",
            ],
            cwd=repo,
        )
        run(
            [
                str(repo / "scripts" / "approve-skill.sh"),
                "delegated-review-fixture",
                "--reviewer",
                "alice",
                "--decision",
                "approved",
            ],
            cwd=repo,
        )

        fail_command = [
            *infinitas_cli(repo, "policy", "check-promotion"),
            "--json",
            "--as-active",
            str(skill_dir),
        ]
        fail_result = run(fail_command, cwd=repo, expect=1)
        fail_payload = load_json_output(fail_result, command=fail_command)
        fail_trace = fail_payload.get("policy_trace") or {}
        if fail_trace.get("decision") != "deny":
            fail(
                f"expected deny decision before security review, got {fail_trace.get('decision')!r}"
            )
        blocking_rules = fail_trace.get("blocking_rules") or []
        if not any("security" in json.dumps(item, ensure_ascii=False) for item in blocking_rules):
            fail(
                f"expected delegated review trace to mention missing security coverage, got {blocking_rules!r}"
            )

        run(
            [
                str(repo / "scripts" / "approve-skill.sh"),
                "delegated-review-fixture",
                "--reviewer",
                "bob",
                "--decision",
                "approved",
            ],
            cwd=repo,
        )
        run(
            [
                sys.executable,
                str(repo / "scripts" / "review-status.py"),
                "delegated-review-fixture",
                "--as-active",
                "--require-pass",
            ],
            cwd=repo,
        )

        pass_command = [
            *infinitas_cli(repo, "policy", "check-promotion"),
            "--json",
            "--as-active",
            str(skill_dir),
        ]
        pass_result = run(pass_command, cwd=repo)
        pass_payload = load_json_output(pass_result, command=pass_command)
        pass_trace = pass_payload.get("policy_trace") or {}
        if pass_trace.get("decision") != "allow":
            fail(
                f"expected allow decision after delegated approvals, got {pass_trace.get('decision')!r}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_namespace_team_authorization_passes()
    scenario_namespace_team_failure_is_structured()
    scenario_team_review_scope_and_policy_trace()
    print("OK: team governance scope checks passed")


if __name__ == "__main__":
    main()
