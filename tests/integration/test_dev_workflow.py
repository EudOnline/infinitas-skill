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
]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_make_targets_and_docs_expose_dev_workflow_entrypoints() -> None:
    makefile = _read("Makefile")
    lint_command = (
        "uv run ruff check src/infinitas_skill server/ui server/app.py tests/integration tests/unit"
    )
    fmt_command = (
        "uv run ruff format src/infinitas_skill server/ui server/app.py "
        "tests/integration tests/unit"
    )
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
    assert lint_command in readme, "README.md should include raw lint-maintained fallback command"

    testing_doc = _read("docs/reference/testing.md")
    assert "make lint-maintained" in testing_doc, (
        "docs/reference/testing.md should mention make lint-maintained"
    )
    assert "uv sync" in testing_doc, (
        "docs/reference/testing.md should include bootstrap raw fallback (uv sync)"
    )
    assert lint_command in testing_doc, (
        "docs/reference/testing.md should include lint-maintained raw fallback"
    )

    pyproject = _read("pyproject.toml")
    assert 'select = ["E", "F", "I"]' in pyproject, (
        "pyproject.toml should configure Ruff lint select"
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
        "server/ui/lifecycle.py",
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


def test_installed_integrity_script_libs_stay_thin_wrappers() -> None:
    expected_wrappers = {
        "scripts/install_integrity_policy_lib.py": (
            "from infinitas_skill.install.integrity_policy import *"
        ),
        "scripts/installed_skill_lib.py": "from infinitas_skill.install.installed_skill import *",
        "scripts/installed_integrity_lib.py": (
            "from infinitas_skill.install.installed_integrity import *"
        ),
    }
    forbidden_markers = [
        "def default_install_integrity_policy",
        "def load_installed_skill",
        "def default_integrity_record",
        "class InstalledIntegrityError",
    ]

    for rel_path, wrapper_import in expected_wrappers.items():
        text = _read(rel_path)
        assert wrapper_import in text, (
            f"{rel_path} should stay a thin wrapper around the package module"
        )
        for marker in forbidden_markers:
            assert marker not in text, (
                f"{rel_path} should not keep duplicated installed-integrity "
                f"implementation: {marker}"
            )


def test_discovery_script_libs_stay_thin_wrappers() -> None:
    expected_wrappers = {
        "scripts/ai_index_lib.py": "from infinitas_skill.discovery.ai_index import *",
        "scripts/discovery_index_lib.py": "from infinitas_skill.discovery.index import *",
        "scripts/discovery_resolver_lib.py": "from infinitas_skill.discovery.resolver import *",
        "scripts/recommend_skill_lib.py": "from infinitas_skill.discovery.recommendation import *",
        "scripts/explain_install_lib.py": (
            "from infinitas_skill.discovery.install_explanation import *"
        ),
    }
    forbidden_markers = [
        "def build_ai_index",
        "def build_discovery_index",
        "def load_discovery_index",
        "def recommend_skills",
        "def build_install_explanation",
    ]

    for rel_path, wrapper_import in expected_wrappers.items():
        text = _read(rel_path)
        assert wrapper_import in text, (
            f"{rel_path} should stay a thin wrapper around the package module"
        )
        for marker in forbidden_markers:
            assert marker not in text, (
                f"{rel_path} should not keep duplicated discovery-chain implementation: {marker}"
            )


def test_release_fixture_scripts_share_python_env_helper() -> None:
    expected_marker = "build_regression_test_env"
    script_paths = [
        "scripts/test-ai-index.py",
        "scripts/test-attestation-verification.py",
        "scripts/test-discovery-index.py",
        "scripts/test-distribution-install.py",
        "scripts/test-explain-install.py",
        "scripts/test-install-by-name.py",
        "scripts/test-installed-integrity-history-retention.py",
        "scripts/test-installed-integrity-report.py",
        "scripts/test-openclaw-export.py",
        "scripts/test-record-verified-support.py",
        "scripts/test-release-reproducibility.py",
        "scripts/test-release-invariants.py",
        "scripts/test-signing-readiness-report.py",
        "scripts/test-skill-update.py",
        "scripts/test-transparency-log.py",
    ]
    forbidden_markers = [
        "def _preferred_python_bin",
        "from alembic import command; import pytest",
        "Path(tempfile.gettempdir())",
    ]
    forbidden_patterns = [
        r"REQUIRE_TEST_FLAGS\s*=",
        r"env\[['\"]INFINITAS_SKIP_RELEASE_TESTS['\"]\]\s*=",
        r"env\[['\"]INFINITAS_SKIP_ATTESTATION_TESTS['\"]\]\s*=",
        r"env\[['\"]INFINITAS_SKIP_DISTRIBUTION_TESTS['\"]\]\s*=",
        r"env\[['\"]INFINITAS_SKIP_BOOTSTRAP_TESTS['\"]\]\s*=",
        r"env\[['\"]INFINITAS_SKIP_AI_WRAPPER_TESTS['\"]\]\s*=",
        r"env\[['\"]INFINITAS_SKIP_COMPAT_PIPELINE_TESTS['\"]\]\s*=",
        r"env\[['\"]INFINITAS_SKIP_INSTALLED_INTEGRITY_TESTS['\"]\]\s*=",
        r"for key in REQUIRE_TEST_FLAGS:",
    ]

    helper_text = _read("src/infinitas_skill/testing/env.py")
    assert "def build_regression_test_env(" in helper_text, (
        "shared regression test environment builder should live under "
        "src/infinitas_skill/testing/env.py"
    )
    assert "def prepend_preferred_python_bin_to_path(" in helper_text, (
        "shared test environment helper should live under src/infinitas_skill/testing/env.py"
    )
    assert "INFINITAS_RELEASE_HELPER_CHECK_ALL_BLOCKS" in helper_text, (
        "shared regression env helper should centralize the nested "
        "release-helper check-all override"
    )

    for rel_path in script_paths:
        text = _read(rel_path)
        assert expected_marker in text, (
            f"{rel_path} should use the shared regression test environment builder"
        )
        for marker in forbidden_markers:
            assert marker not in text, (
                f"{rel_path} should not keep duplicated regression env boilerplate: {marker}"
            )
        for pattern in forbidden_patterns:
            assert not re.search(pattern, text), (
                f"{rel_path} should not keep duplicated regression env boilerplate: {pattern}"
            )


def test_discovery_consumer_script_libs_stay_thin_wrappers() -> None:
    expected_wrapper_markers = {
        "scripts/decision_metadata_lib.py": [
            "from infinitas_skill.discovery.decision_metadata import *",
        ],
        "scripts/search_inspect_lib.py": [
            "from infinitas_skill.discovery.search import *",
            "from infinitas_skill.discovery.inspect import *",
        ],
        "scripts/result_schema_lib.py": [
            "from infinitas_skill.discovery.result_schema import *",
        ],
    }
    forbidden_markers = [
        "def canonical_decision_metadata",
        "def search_skills",
        "def inspect_skill",
        "def validate_pull_result",
        "def validate_publish_result",
    ]

    for rel_path, wrapper_markers in expected_wrapper_markers.items():
        text = _read(rel_path)
        for marker in wrapper_markers:
            assert marker in text, (
                f"{rel_path} should stay a thin wrapper around package-native "
                "discovery consumer modules"
            )
        for marker in forbidden_markers:
            assert marker not in text, (
                f"{rel_path} should not keep duplicated discovery consumer logic: {marker}"
            )


def test_skill_surface_script_libs_stay_thin_wrappers() -> None:
    expected_wrapper_markers = {
        "scripts/schema_version_lib.py": [
            "from infinitas_skill.skills.schema_version import *",
        ],
        "scripts/canonical_skill_lib.py": [
            "from infinitas_skill.skills.canonical import *",
        ],
        "scripts/render_skill_lib.py": [
            "from infinitas_skill.skills.render import *",
        ],
        "scripts/openclaw_bridge_lib.py": [
            "from infinitas_skill.skills.openclaw import *",
        ],
    }
    forbidden_markers = [
        "def validate_schema_version",
        "def load_skill_source",
        "def render_skill",
        "def render_skill_from_dir",
        "def validate_exported_openclaw_dir",
    ]

    for rel_path, wrapper_markers in expected_wrapper_markers.items():
        text = _read(rel_path)
        for marker in wrapper_markers:
            assert marker in text, (
                f"{rel_path} should stay a thin wrapper around package-native skill-surface modules"
            )
        for marker in forbidden_markers:
            assert marker not in text, (
                f"{rel_path} should not keep duplicated skill-surface logic: {marker}"
            )


def test_registry_script_libs_stay_thin_wrappers() -> None:
    expected_wrapper_markers = {
        "scripts/registry_refresh_state_lib.py": [
            "from infinitas_skill.registry.refresh_state import *",
        ],
        "scripts/registry_snapshot_lib.py": [
            "from infinitas_skill.registry.snapshot import *",
        ],
    }
    forbidden_markers = [
        "def write_refresh_state",
        "def evaluate_refresh_status",
        "def create_snapshot",
        "def resolve_snapshot_selector",
    ]

    for rel_path, wrapper_markers in expected_wrapper_markers.items():
        text = _read(rel_path)
        for marker in wrapper_markers:
            assert marker in text, (
                f"{rel_path} should stay a thin wrapper around package-native registry modules"
            )
        for marker in forbidden_markers:
            assert marker not in text, (
                f"{rel_path} should not keep duplicated registry logic: {marker}"
            )


def test_signing_and_review_script_libs_stay_thin_wrappers() -> None:
    expected_wrapper_markers = {
        "scripts/signing_bootstrap_lib.py": [
            "from infinitas_skill.release.signing_bootstrap import *",
        ],
        "scripts/provenance_payload_lib.py": [
            "from infinitas_skill.release.provenance_payload import *",
        ],
        "scripts/reviewer_rotation_lib.py": [
            "from infinitas_skill.policy.reviewer_rotation import *",
        ],
    }
    forbidden_markers = [
        "def parse_allowed_signers",
        "def build_common_payload",
        "def recommend_reviewers",
        "class SigningBootstrapError",
    ]

    for rel_path, wrapper_markers in expected_wrapper_markers.items():
        text = _read(rel_path)
        for marker in wrapper_markers:
            assert marker in text, (
                f"{rel_path} should stay a thin wrapper around package-native "
                "signing/review modules"
            )
        for marker in forbidden_markers:
            assert marker not in text, (
                f"{rel_path} should not keep duplicated signing/review logic: {marker}"
            )


def test_signing_operator_scripts_stay_package_owned() -> None:
    expected_wrapper_markers = {
        "scripts/bootstrap-signing.py": [
            "from infinitas_skill.release.signing_bootstrap_cli import signing_bootstrap_cli_main",
        ],
        "scripts/doctor-signing.py": [
            "from infinitas_skill.release.signing_doctor import signing_doctor_main",
        ],
        "scripts/report-signing-readiness.py": [
            "from infinitas_skill.release.signing_readiness import signing_readiness_main",
        ],
    }
    forbidden_markers = [
        "def run_init_key",
        "def run_add_allowed_signer",
        "def run_configure_git",
        "def run_authorize_publisher",
        "def release_fix_suggestions",
        "def summarize_trusted_signers",
        "def summarize_skill",
        "def build_report",
        "def render_human",
        "def make_check",
    ]

    for rel_path, wrapper_markers in expected_wrapper_markers.items():
        text = _read(rel_path)
        for marker in wrapper_markers:
            assert marker in text, (
                f"{rel_path} should stay a thin wrapper around package-native "
                "signing operator modules"
            )
        for marker in forbidden_markers:
            assert marker not in text, (
                f"{rel_path} should not keep duplicated signing operator logic: {marker}"
            )


def test_review_operator_scripts_stay_package_owned() -> None:
    expected_wrapper_markers = {
        "scripts/recommend-reviewers.py": [
            "from infinitas_skill.policy.review_commands import recommend_reviewers_main",
        ],
        "scripts/review-status.py": [
            "from infinitas_skill.policy.review_commands import review_status_main",
        ],
    }
    forbidden_markers = [
        "def print_csv_list",
        "def parse_args",
        "def main",
        "render_reviewer_recommendations",
        "evaluate_review_state",
    ]

    for rel_path, wrapper_markers in expected_wrapper_markers.items():
        text = _read(rel_path)
        for marker in wrapper_markers:
            assert marker in text, (
                f"{rel_path} should stay a thin wrapper around package-native "
                "review command modules"
            )
        for marker in forbidden_markers:
            assert marker not in text, (
                f"{rel_path} should not keep duplicated review command logic: {marker}"
            )
