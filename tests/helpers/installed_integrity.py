import os
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers.env import make_test_env  # noqa: E402
from tests.helpers.repo_copy import copy_repo_without_local_state  # noqa: E402
from tests.helpers.signing import (  # noqa: E402
    add_allowed_signer,
    configure_git_ssh_signing,
    generate_signing_key,
)

FIXTURE_NAME = "release-fixture"
VERSION = "1.2.3"
PLATFORM_EVIDENCE_MINUTES = {
    "codex": 0,
    "claude": 1,
    "openclaw": 2,
}


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


def make_env(repo: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    merged_extra = {"INFINITAS_SKILL_RELEASER": "release-test"}
    if extra:
        merged_extra.update(extra)
    env = make_test_env(merged_extra)
    pythonpath = str(repo / "src")
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{pythonpath}:{current_pythonpath}" if current_pythonpath else pythonpath
    )
    return env


def contract_checked_at(repo: Path, platform: str):
    profile_path = repo / "profiles" / f"{platform}.json"
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    last_verified = contract.get("last_verified")
    if not isinstance(last_verified, str) or not last_verified:
        raise AssertionError(f"missing contract.last_verified for platform {platform!r}")
    minute = PLATFORM_EVIDENCE_MINUTES.get(platform, 0)
    return f"{last_verified}T12:{minute:02d}:00Z"


def iso_hours_ago(hours: int):
    return (
        (datetime.now(timezone.utc) - timedelta(hours=hours))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def scaffold_fixture(repo: Path):
    fixture_dir = repo / "skills" / "active" / FIXTURE_NAME
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    shutil.copytree(ROOT / "templates" / "basic-skill", fixture_dir)
    meta = json.loads((fixture_dir / "_meta.json").read_text(encoding="utf-8"))
    meta.update(
        {
            "name": FIXTURE_NAME,
            "version": VERSION,
            "status": "active",
            "summary": f"Fixture skill version {VERSION} for installed integrity tests",
            "owner": "release-test",
            "owners": ["release-test"],
            "author": "release-test",
            "review_state": "approved",
        }
    )
    write_json(fixture_dir / "_meta.json", meta)
    (fixture_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {FIXTURE_NAME}\n"
        "description: Fixture skill for installed integrity tests.\n"
        "---\n\n"
        "# Release Fixture\n\n"
        f"Current fixture version: {VERSION}.\n",
        encoding="utf-8",
    )
    (fixture_dir / "VERSION.txt").write_text(VERSION + "\n", encoding="utf-8")
    (fixture_dir / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        f"## {VERSION} - 2026-03-18\n"
        "- Prepared fixture release for installed integrity tests.\n",
        encoding="utf-8",
    )
    write_json(
        fixture_dir / "reviews.json",
        {
            "version": 1,
            "requests": [
                {
                    "requested_at": "2026-03-18T00:00:00Z",
                    "requested_by": "release-test",
                    "note": "Fixture approval for installed integrity tests",
                }
            ],
            "entries": [
                {
                    "reviewer": "lvxiaoer",
                    "decision": "approved",
                    "at": "2026-03-18T00:05:00Z",
                    "note": "Fixture approval",
                }
            ],
        },
    )


def seed_fresh_platform_evidence(repo: Path, *, version: str = VERSION):
    fixtures = (
        ("codex", contract_checked_at(repo, "codex")),
        ("claude", contract_checked_at(repo, "claude")),
        ("openclaw", contract_checked_at(repo, "openclaw")),
    )
    for platform, checked_at in fixtures:
        path = (
            repo
            / "catalog"
            / "compatibility-evidence"
            / platform
            / FIXTURE_NAME
            / f"{version}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            path,
            {
                "platform": platform,
                "skill": FIXTURE_NAME,
                "version": version,
                "state": "adapted",
                "checked_at": checked_at,
                "checker": f"check-{platform}-compat.py",
            },
        )


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-installed-integrity-"))
    repo = copy_repo_without_local_state(tmpdir)
    origin = tmpdir / "origin.git"
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

    key_path = generate_signing_key(tmpdir, identity="release-test")
    add_allowed_signer(
        repo / "config" / "allowed_signers", identity="release-test", key_path=key_path
    )
    configure_git_ssh_signing(repo, key_path)
    run(["git", "add", "config/allowed_signers"], cwd=repo)
    run(["git", "commit", "-m", "add release signer"], cwd=repo)
    run(["git", "push"], cwd=repo)
    return tmpdir, repo


def release_fixture(repo: Path):
    run(
        [
            str(repo / "scripts" / "release-skill.sh"),
            FIXTURE_NAME,
            "--push-tag",
            "--write-provenance",
        ],
        cwd=repo,
        env=make_env(repo),
    )


def install_fixture(repo: Path, target_dir: Path):
    run(
        [
            str(repo / "scripts" / "install-skill.sh"),
            FIXTURE_NAME,
            str(target_dir),
            "--version",
            VERSION,
        ],
        cwd=repo,
        env=make_env(repo),
    )


def read_install_manifest(target_dir: Path):
    manifest_path = target_dir / ".infinitas-skill-install-manifest.json"
    if not manifest_path.exists():
        fail(f"missing install manifest {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_install_manifest(target_dir: Path, payload):
    write_json(target_dir / ".infinitas-skill-install-manifest.json", payload)


def write_install_integrity_policy(
    repo: Path,
    *,
    stale_policy: str,
    never_verified_policy: str | None = None,
    stale_after_hours: int = 24,
    max_inline_events: int = 20,
):
    freshness = {
        "stale_after_hours": stale_after_hours,
        "stale_policy": stale_policy,
    }
    if never_verified_policy is not None:
        freshness["never_verified_policy"] = never_verified_policy
    write_json(
        repo / "config" / "install-integrity-policy.json",
        {
            "$schema": "../schemas/install-integrity-policy.schema.json",
            "schema_version": 1,
            "freshness": freshness,
            "history": {
                "max_inline_events": max_inline_events,
            },
        },
    )


def mark_install_stale(target_dir: Path, name: str, *, hours_ago: int = 72):
    payload = read_install_manifest(target_dir)
    current = (payload.get("skills") or {}).get(name) or {}
    stale_at = iso_hours_ago(hours_ago)
    current["last_checked_at"] = stale_at
    integrity = dict(current.get("integrity") or {})
    integrity["state"] = "verified"
    integrity["last_verified_at"] = stale_at
    current["integrity"] = integrity
    payload["skills"][name] = current
    write_install_manifest(target_dir, payload)


def mark_install_never_verified(target_dir: Path, name: str):
    payload = read_install_manifest(target_dir)
    current = (payload.get("skills") or {}).get(name) or {}
    current.pop("last_checked_at", None)
    integrity = dict(current.get("integrity") or {})
    integrity["state"] = "verified"
    integrity.pop("last_verified_at", None)
    current["integrity"] = integrity
    payload["skills"][name] = current
    write_install_manifest(target_dir, payload)


def refresh_installed_integrity(repo: Path, target_dir: Path):
    result = run(
        [
            sys.executable,
            str(repo / "scripts" / "report-installed-integrity.py"),
            str(target_dir),
            "--refresh",
            "--json",
        ],
        cwd=repo,
        env=make_env(repo),
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(
            "report-installed-integrity.py --refresh did not return JSON:\n"
            f"{result.stdout}\n"
            f"{result.stderr}\n"
            f"{exc}"
        )


def verify_installed_skill(repo: Path, target_dir: Path, *, expect=0):
    result = run(
        [
            sys.executable,
            str(repo / "scripts" / "verify-installed-skill.py"),
            FIXTURE_NAME,
            str(target_dir),
            "--json",
        ],
        cwd=repo,
        env=make_env(repo),
        expect=expect,
    )
    if not result.stdout.strip():
        fail("verify-installed-skill.py did not print JSON output")
    return json.loads(result.stdout)


def assert_installed_integrity_clean_drift_and_repair():
    tmpdir, repo = prepare_repo()
    try:
        release_fixture(repo)
        target_dir = tmpdir / "installed"
        target_dir.mkdir(parents=True, exist_ok=True)
        install_fixture(repo, target_dir)

        manifest = read_install_manifest(target_dir)
        current = (manifest.get("skills") or {}).get(FIXTURE_NAME) or {}
        integrity = current.get("integrity")
        if not isinstance(integrity, dict):
            fail(f"expected install manifest integrity block, got {integrity!r}")
        if integrity.get("state") != "verified":
            fail(f"expected install integrity state 'verified', got {integrity.get('state')!r}")
        if current.get("integrity_capability") != "supported":
            fail(
                "expected install integrity_capability 'supported', got "
                f"{current.get('integrity_capability')!r}"
            )
        if current.get("integrity_reason") is not None:
            fail(
                "expected install integrity_reason to stay null, got "
                f"{current.get('integrity_reason')!r}"
            )
        integrity_events = current.get("integrity_events")
        if not isinstance(integrity_events, list) or not integrity_events:
            fail(
                "expected install manifest integrity_events to include baseline history, "
                f"got {current!r}"
            )
        first_event = integrity_events[0]
        if not isinstance(first_event, dict) or first_event.get("event") != "verified":
            fail(f"expected first integrity event to be 'verified', got {current!r}")
        if not integrity.get("last_verified_at"):
            fail("expected install integrity last_verified_at to be populated")
        if integrity.get("checked_file_count") != integrity.get("release_file_manifest_count"):
            fail(
                "expected install integrity checked_file_count to equal "
                "release_file_manifest_count, "
                "got "
                f"{integrity.get('checked_file_count')!r} vs "
                f"{integrity.get('release_file_manifest_count')!r}"
            )
        if (
            integrity.get("modified_count") != 0
            or integrity.get("missing_count") != 0
            or integrity.get("unexpected_count") != 0
        ):
            fail(f"expected zero install integrity drift counts, got {integrity!r}")

        listed = run(
            [str(repo / "scripts" / "list-installed.sh"), str(target_dir)], cwd=repo
        ).stdout
        if "integrity=verified" not in listed:
            fail(f"expected list-installed output to surface integrity=verified\n{listed}")
        if "capability=supported" not in listed:
            fail(f"expected list-installed output to surface capability=supported\n{listed}")
        if "freshness=fresh" not in listed:
            fail(f"expected list-installed output to surface freshness=fresh\n{listed}")
        if "events=" not in listed:
            fail(f"expected list-installed output to surface event-count hint\n{listed}")

        payload = verify_installed_skill(repo, target_dir)
        if payload.get("state") != "verified":
            fail(f"expected verified state, got {payload.get('state')!r}")
        if payload.get("qualified_name") != FIXTURE_NAME:
            fail(f"expected qualified_name {FIXTURE_NAME!r}, got {payload.get('qualified_name')!r}")
        if payload.get("installed_version") != VERSION:
            fail(
                f"expected installed_version {VERSION!r}, got {payload.get('installed_version')!r}"
            )
        manifest_path = payload.get("source_distribution_manifest") or ""
        if f"/{VERSION}/manifest.json" not in manifest_path:
            fail(f"unexpected source_distribution_manifest {manifest_path!r}")
        attestation_path = payload.get("source_attestation_path") or ""
        if f"{FIXTURE_NAME}-{VERSION}.json" not in attestation_path:
            fail(f"unexpected source_attestation_path {attestation_path!r}")
        if payload.get("release_file_manifest_count", 0) < 1:
            fail(
                "expected release_file_manifest_count > 0, got "
                f"{payload.get('release_file_manifest_count')!r}"
            )
        if payload.get("checked_file_count") != payload.get("release_file_manifest_count"):
            fail(
                "expected checked_file_count to equal "
                "release_file_manifest_count for a clean install, "
                "got "
                f"{payload.get('checked_file_count')!r} vs "
                f"{payload.get('release_file_manifest_count')!r}"
            )
        if payload.get("modified_files") != []:
            fail(f"expected modified_files [], got {payload.get('modified_files')!r}")
        if payload.get("missing_files") != []:
            fail(f"expected missing_files [], got {payload.get('missing_files')!r}")
        if payload.get("unexpected_files") != []:
            fail(f"expected unexpected_files [], got {payload.get('unexpected_files')!r}")

        installed_dir = target_dir / FIXTURE_NAME
        with (installed_dir / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nLocal drift.\n")
        (installed_dir / "tests" / "smoke.md").unlink()
        (installed_dir / "local-notes.txt").write_text("temporary local note\n", encoding="utf-8")

        drift_payload = verify_installed_skill(repo, target_dir, expect=1)
        if drift_payload.get("state") != "drifted":
            fail(f"expected drifted state, got {drift_payload.get('state')!r}")
        if drift_payload.get("modified_files") != ["SKILL.md"]:
            fail(
                f"expected modified_files ['SKILL.md'], got {drift_payload.get('modified_files')!r}"
            )
        if drift_payload.get("missing_files") != ["tests/smoke.md"]:
            fail(
                "expected missing_files ['tests/smoke.md'], got "
                f"{drift_payload.get('missing_files')!r}"
            )
        if drift_payload.get("unexpected_files") != ["local-notes.txt"]:
            fail(
                "expected unexpected_files ['local-notes.txt'], got "
                f"{drift_payload.get('unexpected_files')!r}"
            )

        sync_result = run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(repo),
            expect=1,
        )
        sync_output = sync_result.stdout + sync_result.stderr
        if (
            "repair-installed-skill.sh" not in sync_output
            or "verify-installed-skill.py" not in sync_output
        ):
            fail(
                "expected sync drift failure to recommend verify and repair commands\n"
                f"{sync_output}"
            )

        repair_result = run(
            [str(repo / "scripts" / "repair-installed-skill.sh"), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(repo),
        )
        repair_output = repair_result.stdout + repair_result.stderr
        if "repaired:" not in repair_output:
            fail(f"expected repair-installed-skill.sh to report repaired output\n{repair_output}")

        repaired_payload = verify_installed_skill(repo, target_dir)
        if repaired_payload.get("state") != "verified":
            fail(
                "expected repaired install to verify cleanly, got "
                f"{repaired_payload.get('state')!r}"
            )
        if repaired_payload.get("installed_version") != VERSION:
            fail(
                f"expected repair to restore version {VERSION!r}, got "
                f"{repaired_payload.get('installed_version')!r}"
            )
        repaired_manifest = read_install_manifest(target_dir)
        repaired_current = (repaired_manifest.get("skills") or {}).get(FIXTURE_NAME) or {}
        repaired_events = repaired_current.get("integrity_events")
        if not isinstance(repaired_events, list) or len(repaired_events) < 2:
            fail(
                f"expected repair flow to append integrity event history, got {repaired_current!r}"
            )
    finally:
        shutil.rmtree(tmpdir)


def assert_installed_integrity_stale_mutation_guardrails():
    tmpdir, repo = prepare_repo()
    try:
        release_fixture(repo)
        fixture_dir = repo / "skills" / "active" / FIXTURE_NAME
        meta = json.loads((fixture_dir / "_meta.json").read_text(encoding="utf-8"))
        meta["version"] = "1.2.4"
        write_json(fixture_dir / "_meta.json", meta)
        (fixture_dir / "VERSION.txt").write_text("1.2.4\n", encoding="utf-8")
        (fixture_dir / "CHANGELOG.md").write_text(
            "# Changelog\n\n"
            "## 1.2.4 - 2026-03-19\n"
            "- Prepared fixture update for stale mutation guardrail tests.\n",
            encoding="utf-8",
        )
        run(["git", "add", str(fixture_dir)], cwd=repo)
        run(["git", "commit", "-m", "fixture repo 1.2.4"], cwd=repo)
        run(["git", "push"], cwd=repo)
        run([str(repo / "scripts" / "build-catalog.sh")], cwd=repo)
        seed_fresh_platform_evidence(repo, version="1.2.4")
        run(["git", "add", "catalog"], cwd=repo)
        run(["git", "commit", "-m", "build fixture catalog 1.2.4"], cwd=repo)
        run(["git", "push"], cwd=repo)
        run(
            [
                str(repo / "scripts" / "release-skill.sh"),
                FIXTURE_NAME,
                "--push-tag",
                "--write-provenance",
            ],
            cwd=repo,
            env=make_env(repo),
        )

        target_warn = tmpdir / "installed-warn"
        target_warn.mkdir(parents=True, exist_ok=True)
        install_fixture(repo, target_warn)

        write_install_integrity_policy(repo, stale_policy="warn")
        mark_install_stale(target_warn, FIXTURE_NAME)

        sync_warn = run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_warn)],
            cwd=repo,
            env=make_env(repo),
        )
        sync_warn_output = sync_warn.stdout + sync_warn.stderr
        if (
            "report-installed-integrity.py" not in sync_warn_output
            or "--refresh" not in sync_warn_output
        ):
            fail(
                f"expected stale warn sync output to recommend refresh command\n{sync_warn_output}"
            )

        upgrade_warn = run(
            [str(repo / "scripts" / "upgrade-skill.sh"), FIXTURE_NAME, str(target_warn)],
            cwd=repo,
            env=make_env(repo),
        )
        upgrade_warn_output = upgrade_warn.stdout + upgrade_warn.stderr
        if (
            "report-installed-integrity.py" not in upgrade_warn_output
            or "--refresh" not in upgrade_warn_output
        ):
            fail(
                "expected stale warn upgrade output to recommend refresh command\n"
                f"{upgrade_warn_output}"
            )
        upgrade_warn_payload = json.loads(upgrade_warn.stdout)
        if upgrade_warn_payload.get("state") != "installed":
            fail(
                "expected stale warn upgrade to complete with state 'installed', got "
                f"{upgrade_warn_payload!r}"
            )

        target_never_warn = tmpdir / "installed-never-warn"
        target_never_warn.mkdir(parents=True, exist_ok=True)
        install_fixture(repo, target_never_warn)
        write_install_integrity_policy(repo, stale_policy="warn", never_verified_policy="warn")
        mark_install_never_verified(target_never_warn, FIXTURE_NAME)

        sync_never_warn = run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_never_warn)],
            cwd=repo,
            env=make_env(repo),
        )
        sync_never_warn_output = sync_never_warn.stdout + sync_never_warn.stderr
        if (
            "report-installed-integrity.py" not in sync_never_warn_output
            or "--refresh" not in sync_never_warn_output
        ):
            fail(
                "expected never-verified warn sync output to recommend refresh command\n"
                f"{sync_never_warn_output}"
            )

        upgrade_never_warn = run(
            [str(repo / "scripts" / "upgrade-skill.sh"), FIXTURE_NAME, str(target_never_warn)],
            cwd=repo,
            env=make_env(repo),
        )
        upgrade_never_warn_output = upgrade_never_warn.stdout + upgrade_never_warn.stderr
        if (
            "report-installed-integrity.py" not in upgrade_never_warn_output
            or "--refresh" not in upgrade_never_warn_output
        ):
            fail(
                "expected never-verified warn upgrade output to recommend refresh command\n"
                f"{upgrade_never_warn_output}"
            )
        upgrade_never_warn_payload = json.loads(upgrade_never_warn.stdout)
        if upgrade_never_warn_payload.get("state") != "installed":
            fail(
                "expected never-verified warn upgrade to complete with state 'installed', got "
                f"{upgrade_never_warn_payload!r}"
            )

        target_fail = tmpdir / "installed-fail"
        target_fail.mkdir(parents=True, exist_ok=True)
        install_fixture(repo, target_fail)
        write_install_integrity_policy(repo, stale_policy="fail")
        mark_install_stale(target_fail, FIXTURE_NAME)

        sync_fail = run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_fail)],
            cwd=repo,
            env=make_env(repo),
            expect=1,
        )
        sync_fail_output = sync_fail.stdout + sync_fail.stderr
        if (
            "report-installed-integrity.py" not in sync_fail_output
            or "--refresh" not in sync_fail_output
        ):
            fail(
                f"expected stale fail sync output to recommend refresh command\n{sync_fail_output}"
            )

        upgrade_fail = run(
            [str(repo / "scripts" / "upgrade-skill.sh"), FIXTURE_NAME, str(target_fail)],
            cwd=repo,
            env=make_env(repo),
            expect=1,
        )
        upgrade_fail_payload = json.loads(upgrade_fail.stdout)
        if upgrade_fail_payload.get("error_code") != "stale-installed-integrity":
            fail(
                "expected stale fail upgrade error_code 'stale-installed-integrity', got "
                f"{upgrade_fail_payload!r}"
            )
        if upgrade_fail_payload.get("next_step") != "refresh-installed-integrity":
            fail(
                "expected stale fail upgrade next_step 'refresh-installed-integrity', got "
                f"{upgrade_fail_payload!r}"
            )
        if "report-installed-integrity.py" not in (
            upgrade_fail_payload.get("freshness_warning") or ""
        ):
            fail(
                "expected stale fail upgrade freshness_warning to include refresh command, "
                f"got {upgrade_fail_payload!r}"
            )

        refreshed = refresh_installed_integrity(repo, target_fail)
        if refreshed.get("refreshed") is not True:
            fail(f"expected refresh payload refreshed=true, got {refreshed!r}")
        refreshed_item = next(
            (item for item in (refreshed.get("skills") or []) if item.get("name") == FIXTURE_NAME),
            None,
        )
        if refreshed_item is None:
            fail(f"expected refreshed payload to include {FIXTURE_NAME!r}, got {refreshed!r}")
        if refreshed_item.get("freshness_state") == "stale":
            fail(f"expected refresh run to clear stale state, got {refreshed_item!r}")

        run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_fail)],
            cwd=repo,
            env=make_env(repo),
        )

        target_never_fail = tmpdir / "installed-never-fail"
        target_never_fail.mkdir(parents=True, exist_ok=True)
        install_fixture(repo, target_never_fail)
        write_install_integrity_policy(repo, stale_policy="warn", never_verified_policy="fail")
        mark_install_never_verified(target_never_fail, FIXTURE_NAME)

        sync_never_fail = run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_never_fail)],
            cwd=repo,
            env=make_env(repo),
            expect=1,
        )
        sync_never_fail_output = sync_never_fail.stdout + sync_never_fail.stderr
        if (
            "report-installed-integrity.py" not in sync_never_fail_output
            or "--refresh" not in sync_never_fail_output
        ):
            fail(
                "expected never-verified fail sync output to recommend refresh command\n"
                f"{sync_never_fail_output}"
            )

        upgrade_never_fail = run(
            [str(repo / "scripts" / "upgrade-skill.sh"), FIXTURE_NAME, str(target_never_fail)],
            cwd=repo,
            env=make_env(repo),
            expect=1,
        )
        upgrade_never_fail_payload = json.loads(upgrade_never_fail.stdout)
        if upgrade_never_fail_payload.get("error_code") != "never-verified-installed-integrity":
            fail(
                "expected never-verified fail upgrade error_code "
                "'never-verified-installed-integrity', "
                f"got {upgrade_never_fail_payload!r}"
            )
        if upgrade_never_fail_payload.get("next_step") != "refresh-installed-integrity":
            fail(
                "expected never-verified fail upgrade next_step 'refresh-installed-integrity', "
                f"got {upgrade_never_fail_payload!r}"
            )
        if "report-installed-integrity.py" not in (
            upgrade_never_fail_payload.get("freshness_warning") or ""
        ):
            fail(
                "expected never-verified fail upgrade freshness_warning to include refresh "
                f"command, got {upgrade_never_fail_payload!r}"
            )

        refreshed_never = refresh_installed_integrity(repo, target_never_fail)
        refreshed_never_item = next(
            (
                item
                for item in (refreshed_never.get("skills") or [])
                if item.get("name") == FIXTURE_NAME
            ),
            None,
        )
        if refreshed_never_item is None:
            fail(
                "expected refreshed never-verified payload to include "
                f"{FIXTURE_NAME!r}, got {refreshed_never!r}"
            )
        if refreshed_never_item.get("freshness_state") != "fresh":
            fail(
                f"expected refresh run to clear never-verified state, got {refreshed_never_item!r}"
            )

        run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_never_fail)],
            cwd=repo,
            env=make_env(repo),
        )

        mark_install_never_verified(target_never_fail, FIXTURE_NAME)
        run(
            [
                str(repo / "scripts" / "sync-skill.sh"),
                FIXTURE_NAME,
                str(target_never_fail),
                "--force",
            ],
            cwd=repo,
            env=make_env(repo),
        )

        mark_install_never_verified(target_never_fail, FIXTURE_NAME)
        run(
            [
                str(repo / "scripts" / "upgrade-skill.sh"),
                FIXTURE_NAME,
                str(target_never_fail),
                "--force",
            ],
            cwd=repo,
            env=make_env(repo),
        )

        mark_install_stale(target_fail, FIXTURE_NAME)
        run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_fail), "--force"],
            cwd=repo,
            env=make_env(repo),
        )

        mark_install_stale(target_fail, FIXTURE_NAME)
        run(
            [str(repo / "scripts" / "upgrade-skill.sh"), FIXTURE_NAME, str(target_fail), "--force"],
            cwd=repo,
            env=make_env(repo),
        )

        mark_install_stale(target_fail, FIXTURE_NAME)
        installed_dir = target_fail / FIXTURE_NAME
        with (installed_dir / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nLocal drift before stale-guard precedence check.\n")

        sync_drift = run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_fail)],
            cwd=repo,
            env=make_env(repo),
            expect=1,
        )
        sync_drift_output = sync_drift.stdout + sync_drift.stderr
        if (
            "verify-installed-skill.py" not in sync_drift_output
            or "repair-installed-skill.sh" not in sync_drift_output
        ):
            fail(f"expected drift precedence in sync guardrail output\n{sync_drift_output}")
        if "report-installed-integrity.py" in sync_drift_output:
            fail(
                "expected sync drift precedence to avoid stale refresh guidance\n"
                f"{sync_drift_output}"
            )

        upgrade_drift = run(
            [str(repo / "scripts" / "upgrade-skill.sh"), FIXTURE_NAME, str(target_fail)],
            cwd=repo,
            env=make_env(repo),
            expect=1,
        )
        upgrade_drift_output = upgrade_drift.stdout + upgrade_drift.stderr
        if (
            "verify-installed-skill.py" not in upgrade_drift_output
            or "repair-installed-skill.sh" not in upgrade_drift_output
        ):
            fail(f"expected drift precedence in upgrade guardrail output\n{upgrade_drift_output}")
        if "report-installed-integrity.py" in upgrade_drift_output:
            fail(
                "expected upgrade drift precedence to avoid stale refresh guidance\n"
                f"{upgrade_drift_output}"
            )

        mark_install_never_verified(target_never_fail, FIXTURE_NAME)
        installed_dir = target_never_fail / FIXTURE_NAME
        with (installed_dir / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nLocal drift before never-verified precedence check.\n")

        sync_never_drift = run(
            [str(repo / "scripts" / "sync-skill.sh"), FIXTURE_NAME, str(target_never_fail)],
            cwd=repo,
            env=make_env(repo),
            expect=1,
        )
        sync_never_drift_output = sync_never_drift.stdout + sync_never_drift.stderr
        if (
            "verify-installed-skill.py" not in sync_never_drift_output
            or "repair-installed-skill.sh" not in sync_never_drift_output
        ):
            fail(
                "expected drift precedence in never-verified sync output\n"
                f"{sync_never_drift_output}"
            )
        if "report-installed-integrity.py" in sync_never_drift_output:
            fail(
                "expected never-verified sync drift precedence to avoid refresh guidance\n"
                f"{sync_never_drift_output}"
            )

        upgrade_never_drift = run(
            [str(repo / "scripts" / "upgrade-skill.sh"), FIXTURE_NAME, str(target_never_fail)],
            cwd=repo,
            env=make_env(repo),
            expect=1,
        )
        upgrade_never_drift_output = upgrade_never_drift.stdout + upgrade_never_drift.stderr
        if (
            "verify-installed-skill.py" not in upgrade_never_drift_output
            or "repair-installed-skill.sh" not in upgrade_never_drift_output
        ):
            fail(
                "expected drift precedence in never-verified upgrade output\n"
                f"{upgrade_never_drift_output}"
            )
        if "report-installed-integrity.py" in upgrade_never_drift_output:
            fail(
                "expected never-verified upgrade drift precedence to avoid refresh guidance\n"
                f"{upgrade_never_drift_output}"
            )
    finally:
        shutil.rmtree(tmpdir)


def assert_installed_integrity_docs_exist():
    guide = ROOT / "docs" / "reference" / "installed-skill-integrity.md"
    if not guide.exists():
        fail(f"missing installed integrity guide {guide}")
    content = guide.read_text(encoding="utf-8")
    for required in [
        "verify-installed-skill.py",
        "report-installed-integrity.py",
        "--refresh",
        "freshness_state",
        "last_checked_at",
        "integrity_events",
        "archived_integrity_events",
        ".infinitas-skill-installed-integrity.json",
        "recommended_action",
        "repair-installed-skill.sh",
        "verified",
        "drifted",
        "unknown",
    ]:
        if required not in content:
            fail(f"expected installed integrity guide to mention {required!r}")

    distribution_docs = (ROOT / "docs" / "reference" / "distribution-manifests.md").read_text(
        encoding="utf-8"
    )
    if "repair-installed-skill.sh" not in distribution_docs:
        fail(
            "expected docs/reference/distribution-manifests.md to mention "
            "'repair-installed-skill.sh'"
        )

    compatibility_docs = (ROOT / "docs" / "reference" / "compatibility-contract.md").read_text(
        encoding="utf-8"
    )
    for required in ["integrity_capability", "integrity_reason", "integrity_events"]:
        if required not in compatibility_docs:
            fail(f"expected docs/reference/compatibility-contract.md to mention {required!r}")

    discovery_docs = (ROOT / "docs" / "ai" / "discovery.md").read_text(encoding="utf-8")
    for required in [
        "report-installed-integrity.py",
        "catalog/audit-export.json",
        "target-local",
        ".infinitas-skill-installed-integrity.json",
    ]:
        if required not in discovery_docs:
            fail(f"expected docs/ai/discovery.md to mention {required!r}")

    pull_docs = (ROOT / "docs" / "ai" / "pull.md").read_text(encoding="utf-8")
    for required in [
        "report-installed-integrity.py",
        "catalog/audit-export.json",
        "target-local",
        ".infinitas-skill-installed-integrity.json",
    ]:
        if required not in pull_docs:
            fail(f"expected docs/ai/pull.md to mention {required!r}")

    federation_docs = (ROOT / "docs" / "ops" / "federation-operations.md").read_text(
        encoding="utf-8"
    )
    for required in ["report-installed-integrity.py", "catalog/audit-export.json", "target-local"]:
        if required not in federation_docs:
            fail(f"expected docs/ops/federation-operations.md to mention {required!r}")


def main():
    assert_installed_integrity_clean_drift_and_repair()
    assert_installed_integrity_stale_mutation_guardrails()
    assert_installed_integrity_docs_exist()
