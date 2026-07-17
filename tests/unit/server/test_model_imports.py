from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run_in_clean_interpreter(source: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "src")])
    return subprocess.run(
        [sys.executable, "-W", "error", "-c", source],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def test_models_import_directly_from_their_owners() -> None:
    result = _run_in_clean_interpreter(
        """
from server.modules.access.models import AccessGrant
from server.modules.audit.models import AuditEvent
from server.modules.authoring.models import Skill, SkillVersion
from server.modules.exposure.models import Exposure
from server.modules.identity.models import (
    Credential,
    Principal,
    ServicePrincipal,
    Team,
    TeamMembership,
    User,
)
from server.modules.jobs.models import Job
from server.modules.release.models import Artifact, Release
from server.modules.review.models import ReviewCase, ReviewDecision, ReviewPolicy
from server.rate_limit import RateLimitEntry

expected_owners = {
    User: "server.modules.identity.models",
    Principal: "server.modules.identity.models",
    Credential: "server.modules.identity.models",
    Team: "server.modules.identity.models",
    TeamMembership: "server.modules.identity.models",
    ServicePrincipal: "server.modules.identity.models",
    Job: "server.modules.jobs.models",
    AccessGrant: "server.modules.access.models",
    AuditEvent: "server.modules.audit.models",
    Skill: "server.modules.authoring.models",
    SkillVersion: "server.modules.authoring.models",
    Exposure: "server.modules.exposure.models",
    Artifact: "server.modules.release.models",
    Release: "server.modules.release.models",
    ReviewCase: "server.modules.review.models",
    ReviewDecision: "server.modules.review.models",
    ReviewPolicy: "server.modules.review.models",
    RateLimitEntry: "server.rate_limit",
}
for model, expected_owner in expected_owners.items():
    assert model.__module__ == expected_owner, (model, model.__module__)
"""
    )

    assert result.returncode == 0, result.stderr


def test_model_registry_populates_metadata_without_public_model_facade() -> None:
    result = _run_in_clean_interpreter(
        """
from server.model_base import Base
import server.model_registry as model_registry

assert model_registry.__all__ == ()
assert {
    "access_grants",
    "artifacts",
    "audit_events",
    "credentials",
    "exposures",
    "jobs",
    "principals",
    "rate_limit_entries",
    "releases",
    "review_cases",
    "review_decisions",
    "review_policies",
    "service_principals",
    "skill_contents",
    "skill_versions",
    "skills",
    "team_memberships",
    "teams",
    "users",
} == set(Base.metadata.tables)
"""
    )

    assert result.returncode == 0, result.stderr


def test_access_authz_imports_in_clean_interpreter() -> None:
    result = _run_in_clean_interpreter("import server.modules.access.authz")

    assert result.returncode == 0, result.stderr


def test_all_domain_routers_import_in_clean_interpreter() -> None:
    result = _run_in_clean_interpreter(
        """
import server.modules.access.router
import server.modules.audit.router
import server.modules.authoring.router
import server.modules.discovery.router
import server.modules.exposure.router
import server.modules.identity.router
import server.modules.library.router
import server.modules.registry.router
import server.modules.release.router
import server.modules.review.router
import server.modules.system.router
"""
    )

    assert result.returncode == 0, result.stderr


def test_all_page_routers_import_in_clean_interpreter() -> None:
    result = _run_in_clean_interpreter(
        """
import server.ui.routes.home
import server.ui.routes.library
import server.ui.routes.profile
import server.ui.routes.settings
"""
    )

    assert result.returncode == 0, result.stderr


def test_api_routes_are_owned_by_domain_modules() -> None:
    assert not (ROOT / "server" / "api").exists()
    app_source = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
    assert "server.api" not in app_source


def test_identity_service_owns_identity_and_credential_lifecycle() -> None:
    identity_service = ROOT / "server" / "modules" / "identity" / "service.py"
    assert identity_service.is_file()
    access_service = ROOT / "server" / "modules" / "access" / "service.py"
    tree = ast.parse(access_service.read_text(encoding="utf-8"), filename=str(access_service))
    access_functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    identity_functions = {
        "create_fresh_session_credential",
        "ensure_personal_credential_for_user",
        "ensure_session_credential",
        "ensure_user_principal",
        "get_personal_credential",
        "get_principal",
        "get_principal_for_user",
        "get_user_for_principal",
        "resolve_credential_by_id",
        "resolve_credential_by_token",
        "resolve_user_by_password",
    }
    assert not access_functions.intersection(identity_functions)


def test_library_has_ui_neutral_typed_read_models() -> None:
    from server.modules.library.read_models import (
        LibraryObjectDetailReadModel,
        LibraryObjectReadModel,
    )

    assert LibraryObjectReadModel.__module__ == "server.modules.library.read_models"
    assert LibraryObjectDetailReadModel.__module__ == "server.modules.library.read_models"
