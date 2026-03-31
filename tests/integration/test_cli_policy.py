from __future__ import annotations

from tests.helpers.cli_policy import (
    assert_policy_check_packs_matches_legacy,
    assert_policy_check_promotion_matches_legacy,
    assert_policy_cli_help_lists_maintained_subcommands,
    assert_policy_routes_through_package_service,
)


def test_policy_cli_help_lists_maintained_subcommands() -> None:
    assert_policy_cli_help_lists_maintained_subcommands()


def test_policy_check_packs_matches_legacy() -> None:
    assert_policy_check_packs_matches_legacy()


def test_policy_check_promotion_matches_legacy() -> None:
    assert_policy_check_promotion_matches_legacy()


def test_policy_routes_through_package_service() -> None:
    assert_policy_routes_through_package_service()


def main() -> None:
    assert_policy_cli_help_lists_maintained_subcommands()
    assert_policy_check_packs_matches_legacy()
    assert_policy_check_promotion_matches_legacy()
    assert_policy_routes_through_package_service()
