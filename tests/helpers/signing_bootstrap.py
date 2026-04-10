# ruff: noqa: E402

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers.env import make_test_env
from tests.helpers.repo_copy import copy_repo_without_local_state

FIXTURE_NAME = "bootstrap-fixture"
FIXTURE_VERSION = "1.2.3"


def fail(message):
    raise AssertionError(message)


def run(command, cwd, expect=0, env=None):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if result.returncode != expect:
        fail(
            f"command {command!r} exited {result.returncode}, expected {expect}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def scaffold_fixture(repo: Path):
    fixture_dir = repo / "skills" / "active" / FIXTURE_NAME
    shutil.copytree(ROOT / "templates" / "basic-skill", fixture_dir)
    meta = json.loads((fixture_dir / "_meta.json").read_text(encoding="utf-8"))
    meta.update(
        {
            "name": FIXTURE_NAME,
            "publisher": "lvxiaoer",
            "qualified_name": f"lvxiaoer/{FIXTURE_NAME}",
            "version": FIXTURE_VERSION,
            "status": "active",
            "summary": "Fixture skill for signing bootstrap rehearsal",
            "owner": "lvxiaoer",
            "owners": ["lvxiaoer"],
            "maintainers": ["lvxiaoer"],
            "author": "release-test",
            "review_state": "approved",
        }
    )
    write_json(fixture_dir / "_meta.json", meta)
    (fixture_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {FIXTURE_NAME}\n"
        "description: Fixture skill for signing bootstrap rehearsal.\n"
        "---\n\n"
        "# Bootstrap Fixture\n\n"
        "Used only by automated signing bootstrap tests.\n",
        encoding="utf-8",
    )
    (fixture_dir / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        f"## {FIXTURE_VERSION} - 2026-03-09\n"
        "- Added signing bootstrap rehearsal fixture.\n",
        encoding="utf-8",
    )
    write_json(
        fixture_dir / "reviews.json",
        {
            "version": 1,
            "requests": [
                {
                    "requested_at": "2026-03-09T00:00:00Z",
                    "requested_by": "release-test",
                    "note": "Fixture approval for signing bootstrap rehearsal",
                }
            ],
            "entries": [
                {
                    "reviewer": "alice",
                    "decision": "approved",
                    "at": "2026-03-09T00:05:00Z",
                    "note": "Fixture approval",
                }
            ],
        },
    )


def seed_fresh_platform_evidence(repo: Path):
    seed_platform_evidence(
        repo,
        [
            ("codex", "2026-03-12T12:00:00Z", "adapted"),
            ("claude", "2026-03-12T12:01:00Z", "adapted"),
            ("openclaw", "2026-03-12T12:02:00Z", "adapted"),
        ],
    )


def seed_platform_evidence(repo: Path, fixtures, *, clear_existing=True):
    if clear_existing:
        evidence_root = repo / "catalog" / "compatibility-evidence"
        for path in evidence_root.glob(f"*/{FIXTURE_NAME}"):
            if path.is_dir():
                shutil.rmtree(path)

    for platform, checked_at, state in fixtures:
        path = (
            repo
            / "catalog"
            / "compatibility-evidence"
            / platform
            / FIXTURE_NAME
            / f"{FIXTURE_VERSION}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            path,
            {
                "platform": platform,
                "skill": FIXTURE_NAME,
                "version": FIXTURE_VERSION,
                "state": state,
                "checked_at": checked_at,
                "checker": f"check-{platform}-compat.py",
            },
        )


def rewrite_promotion_policy(repo: Path):
    policy_path = repo / "policy" / "promotion-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    reviews = policy.get("reviews") if isinstance(policy.get("reviews"), dict) else {}
    groups = reviews.get("groups") if isinstance(reviews.get("groups"), dict) else {}
    maintainers = groups.get("maintainers") if isinstance(groups.get("maintainers"), dict) else {}
    members = maintainers.get("members") if isinstance(maintainers.get("members"), list) else []
    maintainers["members"] = list(dict.fromkeys([*members, "alice"]))
    groups["maintainers"] = maintainers
    reviews["groups"] = groups
    policy["reviews"] = reviews
    write_json(policy_path, policy)


def stabilize_active_skill_reviews(repo: Path):
    active_root = repo / "skills" / "active"
    if not active_root.is_dir():
        return
    for skill_dir in sorted(path for path in active_root.iterdir() if path.is_dir()):
        reviews_path = skill_dir / "reviews.json"
        reviews = (
            json.loads(reviews_path.read_text(encoding="utf-8"))
            if reviews_path.exists()
            else {"version": 1, "requests": [], "entries": []}
        )
        entries = reviews.get("entries") if isinstance(reviews.get("entries"), list) else []
        if not any(
            item.get("reviewer") == "alice" and item.get("decision") == "approved"
            for item in entries
        ):
            entries.append(
                {
                    "reviewer": "alice",
                    "decision": "approved",
                    "at": "2026-03-12T00:10:00Z",
                    "note": f"Fixture-compatible approval for active skill {skill_dir.name}",
                }
            )
        reviews["entries"] = entries
        write_json(reviews_path, reviews)


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-bootstrap-test-"))
    repo = copy_repo_without_local_state(tmpdir)
    origin = tmpdir / "origin.git"
    rewrite_promotion_policy(repo)
    (repo / "config" / "allowed_signers").write_text("", encoding="utf-8")
    stabilize_active_skill_reviews(repo)
    scaffold_fixture(repo)
    seed_fresh_platform_evidence(repo)
    run(["git", "init", "--bare", str(origin)], cwd=tmpdir)
    run(["git", "init", "-b", "main"], cwd=repo)
    run(["git", "config", "user.name", "Release Fixture"], cwd=repo)
    run(["git", "config", "user.email", "release@example.com"], cwd=repo)
    run(["git", "remote", "add", "origin", str(origin)], cwd=repo)
    run(["git", "add", "."], cwd=repo)
    run(["git", "commit", "-m", "fixture repo"], cwd=repo)
    run(["git", "push", "-u", "origin", "main"], cwd=repo)
    run([str(repo / "scripts" / "build-catalog.sh")], cwd=repo)
    run(["git", "add", "catalog"], cwd=repo)
    run(["git", "commit", "-m", "build fixture catalog"], cwd=repo)
    run(["git", "push"], cwd=repo)
    return tmpdir, repo


def assert_contains(text, needle, label):
    if needle not in text:
        fail(f"{label} did not include {needle!r}\n{text}")


def assert_signing_bootstrap_rehearsal_passes():
    tmpdir, repo = prepare_repo()
    try:
        doctor_before = run(
            [
                sys.executable,
                str(repo / "scripts" / "doctor-signing.py"),
                FIXTURE_NAME,
                "--identity",
                "release-test",
                "--json",
            ],
            cwd=repo,
            expect=1,
            env=make_test_env(),
        )
        before_report = json.loads(doctor_before.stdout)
        failing_checks = {
            check["id"]
            for check in before_report.get("checks", [])
            if check.get("status") == "fail"
        }
        if "trusted-signers" not in failing_checks:
            fail(f"expected trusted-signers failure before bootstrap, got {failing_checks!r}")
        if "signing-key" not in failing_checks:
            fail(f"expected signing-key failure before bootstrap, got {failing_checks!r}")

        key_path = tmpdir / "release-test-key"
        run(
            [
                sys.executable,
                str(repo / "scripts" / "bootstrap-signing.py"),
                "init-key",
                "--identity",
                "release-test",
                "--output",
                str(key_path),
            ],
            cwd=repo,
            env=make_test_env(),
        )
        run(
            [
                sys.executable,
                str(repo / "scripts" / "bootstrap-signing.py"),
                "add-allowed-signer",
                "--identity",
                "release-test",
                "--key",
                str(key_path),
            ],
            cwd=repo,
            env=make_test_env(),
        )
        run(
            [
                sys.executable,
                str(repo / "scripts" / "bootstrap-signing.py"),
                "configure-git",
                "--key",
                str(key_path),
            ],
            cwd=repo,
            env=make_test_env(),
        )
        run(
            [
                sys.executable,
                str(repo / "scripts" / "bootstrap-signing.py"),
                "authorize-publisher",
                "--publisher",
                "lvxiaoer",
                "--signer",
                "release-test",
                "--releaser",
                "Release Fixture",
            ],
            cwd=repo,
            env=make_test_env(),
        )
        run(["git", "add", "config/allowed_signers", "policy/namespace-policy.json"], cwd=repo)
        run(["git", "commit", "-m", "bootstrap release signer"], cwd=repo)
        run(["git", "push"], cwd=repo)

        doctor_ready = run(
            [
                sys.executable,
                str(repo / "scripts" / "doctor-signing.py"),
                FIXTURE_NAME,
                "--identity",
                "release-test",
                "--json",
            ],
            cwd=repo,
            env=make_test_env(),
        )
        ready_report = json.loads(doctor_ready.stdout)
        if ready_report.get("overall_status") != "ok":
            fail(f"expected ready doctor report, got {ready_report.get('overall_status')!r}")
        release_tag_checks = [
            check for check in ready_report["checks"] if check["id"] == "release-tag"
        ]
        if not release_tag_checks or release_tag_checks[0]["status"] != "info":
            fail(f"expected release-tag info status before tagging, got {release_tag_checks!r}")

        notes_path = tmpdir / "bootstrap-release-notes.md"
        release_result = run(
            [
                str(repo / "scripts" / "release-skill.sh"),
                FIXTURE_NAME,
                "--push-tag",
                "--notes-out",
                str(notes_path),
                "--write-provenance",
            ],
            cwd=repo,
            env=make_test_env(),
        )
        assert_contains(
            release_result.stdout + release_result.stderr,
            "verified attestation:",
            "release attestation summary",
        )

        provenance_path = repo / "catalog" / "provenance" / f"{FIXTURE_NAME}-{FIXTURE_VERSION}.json"
        doctor_after = run(
            [
                sys.executable,
                str(repo / "scripts" / "doctor-signing.py"),
                FIXTURE_NAME,
                "--identity",
                "release-test",
                "--provenance",
                str(provenance_path),
                "--json",
            ],
            cwd=repo,
            env=make_test_env(),
        )
        after_report = json.loads(doctor_after.stdout)
        if after_report.get("overall_status") not in {"ok", "warn"}:
            fail(
                "expected non-blocking doctor report after release, "
                f"got {after_report.get('overall_status')!r}"
            )
        blocking_checks = [
            check for check in after_report["checks"] if check.get("status") == "fail"
        ]
        if blocking_checks:
            fail(f"expected no blocking checks after release, got {blocking_checks!r}")
        attestation_checks = [
            check for check in after_report["checks"] if check["id"] == "attestation"
        ]
        if not attestation_checks or attestation_checks[0]["status"] != "ok":
            fail(f"expected attestation OK after release, got {attestation_checks!r}")
        assert_contains(
            notes_path.read_text(encoding="utf-8"),
            "## Source Snapshot",
            "release notes snapshot block",
        )
    finally:
        shutil.rmtree(tmpdir)


def main():
    assert_signing_bootstrap_rehearsal_passes()
