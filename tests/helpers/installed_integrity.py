import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.helpers.env import make_test_env
from tests.helpers.repo_copy import copy_repo_without_local_state
from tests.helpers.signing import (
    add_allowed_signer,
    configure_git_ssh_signing,
    generate_signing_key,
)

ROOT = Path(__file__).resolve().parents[2]
# Ensure subprocess CLI invocations use the project venv even when this helper
# is imported by a test launched with a system Python interpreter.
_VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"
if _VENV_PYTHON.exists() and sys.executable != str(_VENV_PYTHON):
    sys.executable = str(_VENV_PYTHON)

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


def run_cli(repo: Path, args: list[str], *, expect=0):
    return run(
        [sys.executable, "-m", "infinitas_skill.cli.main", *args],
        cwd=repo,
        expect=expect,
        env=make_env(repo),
    )


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_env(repo: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    merged_extra = {"INFINITAS_SKILL_RELEASER": "lvxiaoer"}
    if extra:
        merged_extra.update(extra)
    env = make_test_env(merged_extra)
    pythonpath = str(repo / "src")
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{pythonpath}:{current_pythonpath}" if current_pythonpath else pythonpath
    return env


def contract_checked_at(repo: Path, platform: str):
    minute = PLATFORM_EVIDENCE_MINUTES.get(platform, 0)
    checked_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=minute)
    return checked_at.isoformat().replace("+00:00", "Z")


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
        shutil.rmtree(fixture_dir, ignore_errors=True)
    shutil.copytree(ROOT / "templates" / "basic-skill", fixture_dir)
    meta = json.loads((fixture_dir / "_meta.json").read_text(encoding="utf-8"))
    meta.update(
        {
            "name": FIXTURE_NAME,
            "version": VERSION,
            "status": "active",
            "summary": f"Fixture skill version {VERSION} for installed integrity tests",
            "publisher": "lvxiaoer",
            "qualified_name": f"lvxiaoer/{FIXTURE_NAME}",
            "owner": "lvxiaoer",
            "owners": ["lvxiaoer"],
            "maintainers": ["lvxiaoer"],
            "author": "lvxiaoer",
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
    run_cli(repo, ["registry", "catalog", "build"])
    run(["git", "add", "catalog"], cwd=repo)
    run(["git", "commit", "-m", "build fixture catalog"], cwd=repo)
    run(["git", "push"], cwd=repo)

    key_path = generate_signing_key(tmpdir, identity="lvxiaoer")
    add_allowed_signer(repo / "config" / "allowed_signers", identity="lvxiaoer", key_path=key_path)
    configure_git_ssh_signing(repo, key_path)
    run(["git", "add", "config/allowed_signers"], cwd=repo)
    run(["git", "commit", "-m", "add release signer"], cwd=repo)
    run(["git", "push"], cwd=repo)
    return tmpdir, repo


def release_fixture(repo: Path):
    run_cli(
        repo,
        ["release", "publish", FIXTURE_NAME, "--push-tag", "--write-attestation"],
    )


def install_fixture(repo: Path, target_dir: Path):
    run_cli(
        repo,
        ["install", "exact", FIXTURE_NAME, str(target_dir), "--version", VERSION],
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
    result = run_cli(
        repo,
        ["install", "report", str(target_dir), "--refresh", "--json"],
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(
            "infinitas install report --refresh did not return JSON:\n"
            f"{result.stdout}\n"
            f"{result.stderr}\n"
            f"{exc}"
        )


def verify_installed_skill(repo: Path, target_dir: Path, *, expect=0):
    result = run_cli(
        repo,
        ["install", "verify", FIXTURE_NAME, str(target_dir), "--json"],
        expect=expect,
    )
    if not result.stdout.strip():
        fail("infinitas install verify did not print JSON output")
    return json.loads(result.stdout)


def _assert_clean_manifest(target_dir: Path) -> None:
    manifest = read_install_manifest(target_dir)
    current = (manifest.get("skills") or {}).get(FIXTURE_NAME) or {}
    integrity = current.get("integrity")
    if not isinstance(integrity, dict):
        fail(f"expected install manifest integrity block, got {integrity!r}")
    if integrity.get("state") != "verified":
        fail(f"expected install integrity state 'verified', got {integrity.get('state')!r}")
    if current.get("integrity_capability") != "supported":
        fail(f"expected integrity capability 'supported', got {current!r}")
    if current.get("integrity_reason") is not None:
        fail(f"expected integrity reason to stay null, got {current!r}")
    events = current.get("integrity_events")
    if not isinstance(events, list) or not events:
        fail(f"expected baseline integrity history, got {current!r}")
    if not isinstance(events[0], dict) or events[0].get("event") != "verified":
        fail(f"expected first integrity event to be verified, got {current!r}")
    if not integrity.get("last_verified_at"):
        fail("expected install integrity last_verified_at to be populated")
    if integrity.get("checked_file_count") != integrity.get("release_file_manifest_count"):
        fail(f"expected checked and release file counts to match, got {integrity!r}")
    drift_counts = {
        integrity.get(f"{kind}_count") for kind in ("modified", "missing", "unexpected")
    }
    if drift_counts != {0}:
        fail(f"expected zero install integrity drift counts, got {integrity!r}")


def _assert_listed_integrity(repo: Path, target_dir: Path) -> None:
    listed = run_cli(repo, ["install", "list", str(target_dir)]).stdout
    for expected in ("integrity=verified", "capability=supported", "freshness=fresh", "events="):
        if expected not in listed:
            fail(f"expected list-installed output to surface {expected!r}\n{listed}")


def _assert_clean_verification_payload(payload: dict) -> None:
    expected_values = {
        "state": "verified",
        "qualified_name": f"lvxiaoer/{FIXTURE_NAME}",
        "installed_version": VERSION,
        "modified_files": [],
        "missing_files": [],
        "unexpected_files": [],
    }
    for field, expected in expected_values.items():
        if payload.get(field) != expected:
            fail(f"expected {field} {expected!r}, got {payload.get(field)!r}")
    if f"/{VERSION}/manifest.json" not in (payload.get("source_distribution_manifest") or ""):
        fail(f"unexpected source distribution manifest {payload!r}")
    if f"{FIXTURE_NAME}-{VERSION}.json" not in (payload.get("source_attestation_path") or ""):
        fail(f"unexpected source attestation path {payload!r}")
    release_count = payload.get("release_file_manifest_count", 0)
    if release_count < 1 or payload.get("checked_file_count") != release_count:
        fail(f"expected positive matching verification file counts, got {payload!r}")


def _introduce_install_drift(target_dir: Path, note: str = "Local drift.") -> None:
    installed_dir = target_dir / FIXTURE_NAME
    with (installed_dir / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write(f"\n{note}\n")
    smoke_test = installed_dir / "tests" / "smoke.md"
    if smoke_test.exists():
        smoke_test.unlink()
    (installed_dir / "local-notes.txt").write_text("temporary local note\n", encoding="utf-8")


def _assert_drift_payload(payload: dict) -> None:
    expected_values = {
        "state": "drifted",
        "modified_files": ["SKILL.md"],
        "missing_files": ["tests/smoke.md"],
        "unexpected_files": ["local-notes.txt"],
    }
    for field, expected in expected_values.items():
        if payload.get(field) != expected:
            fail(f"expected {field} {expected!r}, got {payload.get(field)!r}")


def _assert_repair_flow(repo: Path, target_dir: Path) -> None:
    sync_result = run_cli(repo, ["install", "sync", FIXTURE_NAME, str(target_dir)], expect=1)
    sync_output = sync_result.stdout + sync_result.stderr
    if (
        "infinitas install repair" not in sync_output
        or "infinitas install verify" not in sync_output
    ):
        fail(f"expected sync to recommend verify and repair\n{sync_output}")
    repair_result = run_cli(repo, ["install", "repair", FIXTURE_NAME, str(target_dir), "--json"])
    repair_output = repair_result.stdout + repair_result.stderr
    if '"repaired": true' not in repair_output:
        fail(f"expected repair to report repaired output\n{repair_output}")
    repaired = verify_installed_skill(repo, target_dir)
    if repaired.get("state") != "verified" or repaired.get("installed_version") != VERSION:
        fail(f"expected repaired install at {VERSION} to verify, got {repaired!r}")
    current = (read_install_manifest(target_dir).get("skills") or {}).get(FIXTURE_NAME) or {}
    events = current.get("integrity_events")
    if not isinstance(events, list) or len(events) < 2:
        fail(f"expected repair to append integrity history, got {current!r}")


def assert_installed_integrity_clean_drift_and_repair():
    tmpdir, repo = prepare_repo()
    try:
        release_fixture(repo)
        target_dir = tmpdir / "installed"
        target_dir.mkdir(parents=True, exist_ok=True)
        install_fixture(repo, target_dir)
        _assert_clean_manifest(target_dir)
        _assert_listed_integrity(repo, target_dir)
        _assert_clean_verification_payload(verify_installed_skill(repo, target_dir))
        _introduce_install_drift(target_dir)
        _assert_drift_payload(verify_installed_skill(repo, target_dir, expect=1))
        _assert_repair_flow(repo, target_dir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _publish_fixture_update(repo: Path) -> None:
    release_fixture(repo)
    fixture_dir = repo / "skills" / "active" / FIXTURE_NAME
    meta = json.loads((fixture_dir / "_meta.json").read_text(encoding="utf-8"))
    meta["version"] = "1.2.4"
    write_json(fixture_dir / "_meta.json", meta)
    (fixture_dir / "VERSION.txt").write_text("1.2.4\n", encoding="utf-8")
    (fixture_dir / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.2.4 - 2026-03-19\n"
        "- Prepared fixture update for stale mutation guardrail tests.\n",
        encoding="utf-8",
    )
    run(["git", "add", str(fixture_dir)], cwd=repo)
    run(["git", "commit", "-m", "fixture repo 1.2.4"], cwd=repo)
    run(["git", "push"], cwd=repo)
    run_cli(repo, ["registry", "catalog", "build"])
    seed_fresh_platform_evidence(repo, version="1.2.4")
    run(["git", "add", "catalog"], cwd=repo)
    run(["git", "commit", "-m", "build fixture catalog 1.2.4"], cwd=repo)
    run(["git", "push"], cwd=repo)
    run_cli(repo, ["release", "publish", FIXTURE_NAME, "--push-tag", "--write-attestation"])


def _create_installed_target(tmpdir: Path, repo: Path, name: str) -> Path:
    target = tmpdir / name
    target.mkdir(parents=True, exist_ok=True)
    install_fixture(repo, target)
    return target


def _assert_refresh_guidance(output: str, label: str) -> None:
    if "infinitas install report" not in output or "--refresh" not in output:
        fail(f"expected {label} to recommend integrity refresh\n{output}")


def _exercise_warn_policy(repo: Path, target: Path, *, never_verified: bool) -> None:
    write_install_integrity_policy(
        repo,
        stale_policy="warn",
        never_verified_policy="warn" if never_verified else None,
    )
    marker = mark_install_never_verified if never_verified else mark_install_stale
    marker(target, FIXTURE_NAME)
    label = "never-verified warn" if never_verified else "stale warn"
    sync = run_cli(repo, ["install", "sync", FIXTURE_NAME, str(target)])
    _assert_refresh_guidance(sync.stdout + sync.stderr, f"{label} sync")
    upgrade = run_cli(repo, ["install", "upgrade", FIXTURE_NAME, str(target), "--json"])
    _assert_refresh_guidance(upgrade.stdout + upgrade.stderr, f"{label} upgrade")
    payload = json.loads(upgrade.stdout)
    if payload.get("state") != "installed":
        fail(f"expected {label} upgrade to install, got {payload!r}")


def _assert_guard_failure(payload: dict, error_code: str) -> None:
    if payload.get("error_code") != error_code:
        fail(f"expected error_code {error_code!r}, got {payload!r}")
    if payload.get("next_step") != "refresh-installed-integrity":
        fail(f"expected refresh-installed-integrity next step, got {payload!r}")
    if "infinitas install report" not in (payload.get("freshness_warning") or ""):
        fail(f"expected failure warning to include refresh command, got {payload!r}")


def _assert_refreshed_target(repo: Path, target: Path, *, require_fresh: bool) -> None:
    refreshed = refresh_installed_integrity(repo, target)
    if refreshed.get("refreshed") is not True:
        fail(f"expected refresh payload refreshed=true, got {refreshed!r}")
    item = next(
        (item for item in (refreshed.get("skills") or []) if item.get("name") == FIXTURE_NAME),
        None,
    )
    if item is None:
        fail(f"expected refreshed payload to include {FIXTURE_NAME!r}, got {refreshed!r}")
    freshness = item.get("freshness_state")
    if (require_fresh and freshness != "fresh") or (not require_fresh and freshness == "stale"):
        fail(f"expected refresh to clear guarded state, got {item!r}")
    run_cli(repo, ["install", "sync", FIXTURE_NAME, str(target)])


def _exercise_fail_policy(repo: Path, target: Path, *, never_verified: bool) -> None:
    write_install_integrity_policy(
        repo,
        stale_policy="warn" if never_verified else "fail",
        never_verified_policy="fail" if never_verified else None,
    )
    marker = mark_install_never_verified if never_verified else mark_install_stale
    marker(target, FIXTURE_NAME)
    label = "never-verified fail" if never_verified else "stale fail"
    sync = run_cli(repo, ["install", "sync", FIXTURE_NAME, str(target)], expect=1)
    _assert_refresh_guidance(sync.stdout + sync.stderr, f"{label} sync")
    upgrade = run_cli(repo, ["install", "upgrade", FIXTURE_NAME, str(target), "--json"], expect=1)
    error_code = (
        "never-verified-installed-integrity" if never_verified else "stale-installed-integrity"
    )
    _assert_guard_failure(json.loads(upgrade.stdout), error_code)
    _assert_refreshed_target(repo, target, require_fresh=never_verified)


def _exercise_force_bypass(repo: Path, target: Path, *, never_verified: bool) -> None:
    marker = mark_install_never_verified if never_verified else mark_install_stale
    marker(target, FIXTURE_NAME)
    run_cli(repo, ["install", "sync", FIXTURE_NAME, str(target), "--force"])
    marker(target, FIXTURE_NAME)
    run_cli(repo, ["install", "upgrade", FIXTURE_NAME, str(target), "--force", "--json"])


def _assert_drift_precedence(repo: Path, target: Path, *, never_verified: bool) -> None:
    marker = mark_install_never_verified if never_verified else mark_install_stale
    marker(target, FIXTURE_NAME)
    note = "Local drift before guarded-state precedence check."
    with (target / FIXTURE_NAME / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write(f"\n{note}\n")
    commands = (
        ["install", "sync", FIXTURE_NAME, str(target)],
        ["install", "upgrade", FIXTURE_NAME, str(target), "--json"],
    )
    for command in commands:
        result = run_cli(repo, command, expect=1)
        output = result.stdout + result.stderr
        if "infinitas install verify" not in output or "infinitas install repair" not in output:
            fail(f"expected drift guidance to take precedence\n{output}")
        if "infinitas install report" in output:
            fail(f"expected drift guidance to omit refresh guidance\n{output}")


def assert_installed_integrity_stale_mutation_guardrails():
    tmpdir, repo = prepare_repo()
    try:
        _publish_fixture_update(repo)
        stale_warn = _create_installed_target(tmpdir, repo, "installed-warn")
        never_warn = _create_installed_target(tmpdir, repo, "installed-never-warn")
        stale_fail = _create_installed_target(tmpdir, repo, "installed-fail")
        never_fail = _create_installed_target(tmpdir, repo, "installed-never-fail")
        _exercise_warn_policy(repo, stale_warn, never_verified=False)
        _exercise_warn_policy(repo, never_warn, never_verified=True)
        _exercise_fail_policy(repo, stale_fail, never_verified=False)
        _exercise_fail_policy(repo, never_fail, never_verified=True)
        _exercise_force_bypass(repo, stale_fail, never_verified=False)
        _exercise_force_bypass(repo, never_fail, never_verified=True)
        _assert_drift_precedence(repo, stale_fail, never_verified=False)
        _assert_drift_precedence(repo, never_fail, never_verified=True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def assert_installed_integrity_docs_exist():
    guide = ROOT / "docs" / "reference" / "installed-skill-integrity.md"
    if not guide.exists():
        fail(f"missing installed integrity guide {guide}")
    content = guide.read_text(encoding="utf-8")
    for required in [
        "infinitas install verify",
        "infinitas install report",
        "--refresh",
        "freshness_state",
        "last_checked_at",
        "integrity_events",
        "archived_integrity_events",
        ".infinitas-skill-installed-integrity.json",
        "recommended_action",
        "infinitas install repair",
        "verified",
        "drifted",
        "unknown",
    ]:
        if required not in content:
            fail(f"expected installed integrity guide to mention {required!r}")

    distribution_docs = (ROOT / "docs" / "reference" / "distribution-manifests.md").read_text(
        encoding="utf-8"
    )
    if "infinitas install repair" not in distribution_docs:
        fail(
            "expected docs/reference/distribution-manifests.md to mention "
            "'infinitas install repair'"
        )

    compatibility_docs = (ROOT / "docs" / "reference" / "compatibility-contract.md").read_text(
        encoding="utf-8"
    )
    for required in ["integrity_capability", "integrity_reason", "integrity_events"]:
        if required not in compatibility_docs:
            fail(f"expected docs/reference/compatibility-contract.md to mention {required!r}")

    discovery_docs = (ROOT / "docs" / "reference" / "discovery-install-workflows.md").read_text(
        encoding="utf-8"
    )
    for required in [
        "infinitas install report",
        "catalog/audit-export.json",
        "target-local",
        ".infinitas-skill-installed-integrity.json",
    ]:
        if required not in discovery_docs:
            fail(f"expected docs/reference/discovery-install-workflows.md to mention {required!r}")

    federation_docs = (ROOT / "docs" / "ops" / "federation-operations.md").read_text(
        encoding="utf-8"
    )
    for required in ["infinitas install report", "catalog/audit-export.json", "target-local"]:
        if required not in federation_docs:
            fail(f"expected docs/ops/federation-operations.md to mention {required!r}")
