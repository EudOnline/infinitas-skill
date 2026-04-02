from __future__ import annotations

from tests.helpers.cli_policy import (
    assert_policy_check_packs_reports_success,
    assert_policy_check_promotion_returns_expected_json,
    assert_policy_cli_help_lists_maintained_subcommands,
    assert_policy_recommend_reviewers_returns_expected_json,
    assert_policy_review_commands_route_through_package_modules,
    assert_policy_review_status_returns_expected_json,
    assert_policy_routes_through_package_service,
)


def test_policy_cli_help_lists_maintained_subcommands() -> None:
    assert_policy_cli_help_lists_maintained_subcommands()


def test_policy_check_packs_reports_success() -> None:
    assert_policy_check_packs_reports_success()


def test_policy_check_promotion_returns_expected_json() -> None:
    assert_policy_check_promotion_returns_expected_json()


def test_policy_routes_through_package_service() -> None:
    assert_policy_routes_through_package_service()


def test_policy_recommend_reviewers_returns_expected_json() -> None:
    assert_policy_recommend_reviewers_returns_expected_json()


def test_policy_review_status_returns_expected_json() -> None:
    assert_policy_review_status_returns_expected_json()


def test_policy_review_commands_route_through_package_modules() -> None:
    assert_policy_review_commands_route_through_package_modules()


def main() -> None:
    assert_policy_cli_help_lists_maintained_subcommands()
    assert_policy_check_packs_reports_success()
    assert_policy_check_promotion_returns_expected_json()
    assert_policy_routes_through_package_service()
    assert_policy_recommend_reviewers_returns_expected_json()
    assert_policy_review_status_returns_expected_json()
    assert_policy_review_commands_route_through_package_modules()
