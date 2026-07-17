from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REMOVED_CLI_SHIMS = [
    "scripts/check-platform-contracts.py",
    "scripts/resolve-install-plan.py",
    "scripts/check-install-target.py",
    "scripts/check-policy-packs.py",
    "scripts/check-promotion-policy.py",
    "scripts/registryctl.py",
    "scripts/check-release-state.py",
    "scripts/resolve-skill.sh",
    "scripts/install-by-name.sh",
    "scripts/check-skill-update.sh",
    "scripts/upgrade-skill.sh",
    "scripts/install-skill.sh",
    "scripts/sync-skill.sh",
    "scripts/switch-installed-skill.sh",
    "scripts/rollback-installed-skill.sh",
    "scripts/search-skills.sh",
    "scripts/recommend-skill.sh",
    "scripts/inspect-skill.sh",
    "scripts/ai_index_lib.py",
    "scripts/discovery_index_lib.py",
    "scripts/discovery_resolver_lib.py",
    "scripts/explain_install_lib.py",
    "scripts/search_inspect_lib.py",
    "scripts/recommend_skill_lib.py",
    # Phase 5 shim deletion (ADR 0001/0002 migration complete)
    "scripts/attestation_lib.py",
    "scripts/canonical_skill_lib.py",
    "scripts/compatibility_evidence_lib.py",
    "scripts/compatibility_policy_lib.py",
    "scripts/decision_metadata_lib.py",
    "scripts/dependency_lib.py",
    "scripts/distribution_lib.py",
    "scripts/exception_policy_lib.py",
    "scripts/http_registry_lib.py",
    "scripts/install_integrity_policy_lib.py",
    "scripts/install_manifest_lib.py",
    "scripts/installed_integrity_lib.py",
    "scripts/installed_skill_lib.py",
    "scripts/openclaw_bridge_lib.py",
    "scripts/platform_contract_lib.py",
    "scripts/policy_pack_lib.py",
    "scripts/policy_trace_lib.py",
    "scripts/provenance_payload_lib.py",
    "scripts/registry_refresh_state_lib.py",
    "scripts/registry_snapshot_lib.py",
    "scripts/registry_source_lib.py",
    "scripts/release_lib.py",
    "scripts/render_skill_lib.py",
    "scripts/result_schema_lib.py",
    "scripts/review_evidence_lib.py",
    "scripts/review_lib.py",
    "scripts/reviewer_rotation_lib.py",
    "scripts/schema_version_lib.py",
    "scripts/signing_bootstrap_lib.py",
    "scripts/skill_identity_lib.py",
    "scripts/team_policy_lib.py",
    "scripts/transparency_log_lib.py",
]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_make_targets_and_docs_expose_dev_workflow_entrypoints() -> None:
    makefile = _read("Makefile")
    lint_command = ".venv/bin/ruff check ."
    fmt_command = ".venv/bin/ruff format ."
    required_targets = [
        "bootstrap",
        "test-fast",
        "test-full",
        "lint-maintained",
        "fmt-maintained",
        "doctor",
    ]
    for target in required_targets:
        assert re.search(rf"^{re.escape(target)}\s*:", makefile, flags=re.MULTILINE), (
            f"expected Makefile target '{target}'"
        )
    assert (f"lint-maintained:\n\t{lint_command}\n") in makefile, (
        "Makefile lint-maintained should match requested command exactly"
    )
    assert (f"fmt-maintained:\n\t{fmt_command}\n") in makefile, (
        "Makefile fmt-maintained should match requested command exactly"
    )

    readme = _read("README.md")
    assert "make test-fast" in readme, "README.md should mention make test-fast"
    assert "make test-full" in readme, "README.md should mention make test-full"
    assert "make lint-budgets" not in readme, "README.md should not advertise removed debt budgets"
    assert lint_command in readme, "README.md should include raw lint-maintained fallback command"

    testing_doc = _read("docs/reference/testing.md")
    assert "make lint-maintained" in testing_doc, (
        "docs/reference/testing.md should mention make lint-maintained"
    )
    assert "make lint-budgets" not in testing_doc
    assert "uv sync" in testing_doc, (
        "docs/reference/testing.md should include bootstrap raw fallback (uv sync)"
    )
    assert lint_command in testing_doc, (
        "docs/reference/testing.md should include lint-maintained raw fallback"
    )

    pyproject = _read("pyproject.toml")
    assert '"E"' in pyproject and '"F"' in pyproject and '"I"' in pyproject, (
        "pyproject.toml should configure Ruff lint select with E, F, I"
    )
    assert 'ignore = ["E501"]' not in pyproject, (
        "pyproject.toml should not disable E501 globally for all maintained files"
    )
    assert re.search(
        r'"src/infinitas_skill/install/service\.py"\s*=\s*\[[^\]]*"E402"[^\]]*"E501"[^\]]*\]',
        pyproject,
    ), "install service should keep targeted E402/E501 carveouts"
    assert re.search(
        r'"src/infinitas_skill/policy/service\.py"\s*=\s*\[[^\]]*"E501"[^\]]*\]',
        pyproject,
    ), "policy service should keep the targeted E501 carveout"
    assert re.search(
        r'"src/infinitas_skill/release/service\.py"\s*=\s*\[[^\]]*"E501"[^\]]*\]',
        pyproject,
    ), "release service should keep the targeted E501 carveout"
    for path in [
        "server/app.py",
        "src/infinitas_skill/server/ops.py",
    ]:
        assert re.search(rf'"{re.escape(path)}"\s*=\s*\[[^\]]*"E501"[^\]]*\]', pyproject), (
            f"pyproject.toml should scope E501 deferrals to the current debt file {path}"
        )
    assert '"I001"' not in pyproject, (
        "pyproject.toml should keep import sorting in the maintained lint baseline"
    )


def test_removed_cli_shims_are_not_supported_entrypoints() -> None:
    for rel_path in REMOVED_CLI_SHIMS:
        assert not (ROOT / rel_path).exists(), (
            f"expected removed CLI shim to stay deleted: {rel_path}"
        )

    for rel_path in [
        "README.md",
        "docs/reference/testing.md",
        "docs/reference/cli-reference.md",
    ]:
        text = _read(rel_path)
        for shim_path in REMOVED_CLI_SHIMS:
            assert shim_path not in text, (
                f"{rel_path} should not mention removed CLI shim entrypoint {shim_path}"
            )


def test_policy_and_release_services_do_not_bridge_back_to_scripts() -> None:
    for rel_path in [
        "src/infinitas_skill/policy/service.py",
        "src/infinitas_skill/release/policy_state.py",
        "src/infinitas_skill/release/service.py",
        "src/infinitas_skill/install/source_resolution.py",
        "src/infinitas_skill/install/target_validation.py",
        "src/infinitas_skill/release/platform_state.py",
        "src/infinitas_skill/release/attestation_state.py",
    ]:
        text = _read(rel_path)
        assert "ensure_legacy_scripts_on_path" not in text, (
            f"{rel_path} should not reintroduce scripts/ path bridging"
        )
        assert "_lib" not in text, (
            f"{rel_path} should import package modules instead of scripts/*_lib.py"
        )


def test_legacy_bridge_module_stays_deleted() -> None:
    assert not (ROOT / "src/infinitas_skill/legacy.py").exists(), (
        "legacy bridge module should stay deleted once package-native root resolution exists"
    )


def test_installed_integrity_script_libs_stay_deleted() -> None:
    """Phase 5 shim deletion: installed-integrity _lib files must stay deleted."""
    deleted_libs = [
        "scripts/install_integrity_policy_lib.py",
        "scripts/installed_skill_lib.py",
        "scripts/installed_integrity_lib.py",
    ]
    for rel_path in deleted_libs:
        assert not (ROOT / rel_path).exists(), (
            f"expected deleted _lib shim to stay deleted: {rel_path}"
        )


def test_script_tests_are_replaced_by_pytest_modules() -> None:
    helper_text = _read("src/infinitas_skill/testing/env.py")
    assert "def build_regression_test_env(" in helper_text, (
        "shared regression test environment builder should live under "
        "src/infinitas_skill/testing/env.py"
    )
    assert not list((ROOT / "scripts").glob("test-*.py"))


def test_discovery_consumer_script_libs_stay_deleted() -> None:
    """Phase 5 shim deletion: discovery consumer _lib files must stay deleted."""
    deleted_libs = [
        "scripts/decision_metadata_lib.py",
        "scripts/result_schema_lib.py",
    ]
    for rel_path in deleted_libs:
        assert not (ROOT / rel_path).exists(), (
            f"expected deleted _lib shim to stay deleted: {rel_path}"
        )


def test_skill_surface_script_libs_stay_deleted() -> None:
    """Phase 5 shim deletion: skill-surface _lib files must stay deleted."""
    deleted_libs = [
        "scripts/schema_version_lib.py",
        "scripts/canonical_skill_lib.py",
        "scripts/render_skill_lib.py",
        "scripts/openclaw_bridge_lib.py",
    ]
    for rel_path in deleted_libs:
        assert not (ROOT / rel_path).exists(), (
            f"expected deleted _lib shim to stay deleted: {rel_path}"
        )


def test_skill_renderer_accepts_only_canonical_sources() -> None:
    render_helpers = _read("src/infinitas_skill/skills/render.py")

    assert "legacy-migration" not in render_helpers
    assert "_copy_legacy_entries" not in render_helpers


def test_registry_script_libs_stay_deleted() -> None:
    """Phase 5 shim deletion: registry _lib files must stay deleted."""
    deleted_libs = [
        "scripts/registry_refresh_state_lib.py",
        "scripts/registry_snapshot_lib.py",
    ]
    for rel_path in deleted_libs:
        assert not (ROOT / rel_path).exists(), (
            f"expected deleted _lib shim to stay deleted: {rel_path}"
        )


def test_signing_and_review_script_libs_stay_deleted() -> None:
    """Phase 5 shim deletion: signing/review _lib files must stay deleted."""
    deleted_libs = [
        "scripts/signing_bootstrap_lib.py",
        "scripts/provenance_payload_lib.py",
        "scripts/reviewer_rotation_lib.py",
    ]
    for rel_path in deleted_libs:
        assert not (ROOT / rel_path).exists(), (
            f"expected deleted _lib shim to stay deleted: {rel_path}"
        )


def test_signing_operator_scripts_stay_package_owned() -> None:
    removed_scripts = (
        "scripts/bootstrap-signing.py",
        "scripts/doctor-signing.py",
        "scripts/report-signing-readiness.py",
    )
    assert all(not (ROOT / path).exists() for path in removed_scripts)
    release_cli = _read("src/infinitas_skill/release/cli.py")
    for command in ("bootstrap-signing", "doctor-signing", "signing-readiness"):
        assert command in release_cli


def test_review_operator_scripts_stay_package_owned() -> None:
    removed_scripts = ("scripts/recommend-reviewers.py", "scripts/review-status.py")
    assert all(not (ROOT / path).exists() for path in removed_scripts)
    policy_cli = _read("src/infinitas_skill/policy/cli.py")
    for command in ("recommend-reviewers", "review-status"):
        assert command in policy_cli


def test_share_links_module_is_consolidated_into_access() -> None:
    """Complexity reduction: share links must not keep a standalone module."""
    assert not (ROOT / "server/modules/shares").exists(), (
        "server/modules/shares should be consolidated into server/modules/access"
    )
    for rel_path in [
        "server/app.py",
        "server/modules/access/share_links.py",
        "server/modules/access/share_links_router.py",
        "server/modules/library/shares.py",
    ]:
        text = _read(rel_path)
        assert "server.modules.shares" not in text, (
            f"{rel_path} should not import the deleted server.modules.shares package"
        )
