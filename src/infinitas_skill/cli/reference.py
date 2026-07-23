"""Generate CLI reference documentation from argparse definitions."""

from __future__ import annotations

import re
from argparse import ArgumentParser
from collections.abc import Callable

from infinitas_skill.cli.main import build_parser
from infinitas_skill.compatibility.checks import build_platform_contracts_parser
from infinitas_skill.discovery.cli import (
    build_discovery_inspect_parser,
    build_discovery_parser,
    build_discovery_recommend_parser,
    build_discovery_search_parser,
)
from infinitas_skill.install.exact import build_install_exact_parser
from infinitas_skill.install.hosted_share import build_install_from_share_parser
from infinitas_skill.install.planning import (
    build_check_install_target_parser,
    build_resolve_install_plan_parser,
)
from infinitas_skill.install.resolve import (
    build_install_by_name_parser,
    build_install_resolve_skill_parser,
)
from infinitas_skill.install.rollback import build_install_rollback_parser
from infinitas_skill.install.switch import build_install_switch_parser
from infinitas_skill.install.sync import build_install_sync_parser
from infinitas_skill.install.update import build_install_check_update_parser
from infinitas_skill.install.upgrade import build_install_upgrade_parser
from infinitas_skill.openclaw.cli import (
    build_openclaw_parser,
    build_openclaw_plugin_inspect_parser,
    build_openclaw_profile_parser,
    build_openclaw_skill_validate_parser,
    build_openclaw_workspace_resolve_parser,
)
from infinitas_skill.policy.cli import (
    build_check_policy_packs_parser,
    build_check_promotion_parser,
    build_policy_parser,
)
from infinitas_skill.policy.review_commands import (
    build_recommend_reviewers_parser,
    build_review_status_parser,
)
from infinitas_skill.registry.cli import build_registry_parser
from infinitas_skill.registry.parser_reference import (
    build_registry_exposures_parser,
    build_registry_releases_parser,
    build_registry_reviews_parser,
    build_registry_shares_parser,
    build_registry_skills_parser,
    build_registry_tokens_parser,
    build_registry_versions_parser,
)
from infinitas_skill.release.cli import build_release_parser
from infinitas_skill.release.signing_bootstrap_cli import build_signing_bootstrap_parser
from infinitas_skill.release.signing_doctor import build_signing_doctor_parser
from infinitas_skill.release.signing_readiness import build_signing_readiness_parser
from infinitas_skill.release.state import build_release_check_state_parser
from infinitas_skill.server.ops import (
    build_server_backup_parser,
    build_server_healthcheck_parser,
    build_server_inspect_state_parser,
    build_server_parser,
    build_server_prune_backups_parser,
    build_server_render_systemd_parser,
    build_server_worker_healthcheck_parser,
    build_server_worker_parser,
)

GENERATED_CLI_REFERENCE_LAST_REVIEWED = "2026-07-23"
ParserFactory = Callable[..., ArgumentParser]
Section = tuple[str, ParserFactory, str]


def _render_help_block(text: str) -> str:
    return f"```text\n{text.rstrip()}\n```\n"


def _stable_help(parser: ArgumentParser) -> str:
    help_text = parser.format_help()
    usage_block, separator, remainder = help_text.partition("\n\n")
    usage_block = re.sub(r"\n([ ]+)\.\.\.$", r" ...", usage_block)
    split_option = re.compile(
        r"(?m)^(?P<line>.*) (?P<option>--[a-z0-9-]+)\n"
        r"(?P<indent> +)(?P<metavar>[A-Z][A-Z0-9_-]+)(?P<rest>.*)$"
    )
    while match := split_option.search(usage_block):
        replacement = (
            f"{match.group('line')}\n{match.group('indent')}"
            f"{match.group('option')} {match.group('metavar')}{match.group('rest')}"
        )
        usage_block = usage_block[: match.start()] + replacement + usage_block[match.end() :]
    normalized_lines: list[str] = []
    continuation_indent = " " * (len("usage: ") + len(parser.prog) + 1)
    for line in usage_block.splitlines():
        while len(line) > 80:
            split_at = max(line.rfind(" --"), line.rfind(" [--"))
            indent = line[: len(line) - len(line.lstrip())]
            if split_at <= len(indent):
                break
            normalized_lines.append(line[:split_at])
            line = (indent or continuation_indent) + line[split_at + 1 :]
        normalized_lines.append(line)
    usage_block = "\n".join(normalized_lines)
    return usage_block + (separator + remainder if separator else "\n")


def _discovery_and_install_sections() -> list[Section]:
    return [
        (
            "infinitas compatibility check-platform-contracts",
            build_platform_contracts_parser,
            "infinitas compatibility check-platform-contracts",
        ),
        ("infinitas discovery", build_discovery_parser, "infinitas discovery"),
        ("infinitas discovery search", build_discovery_search_parser, "infinitas discovery search"),
        (
            "infinitas discovery recommend",
            build_discovery_recommend_parser,
            "infinitas discovery recommend",
        ),
        (
            "infinitas discovery inspect",
            build_discovery_inspect_parser,
            "infinitas discovery inspect",
        ),
        (
            "infinitas install resolve-plan",
            build_resolve_install_plan_parser,
            "infinitas install resolve-plan",
        ),
        (
            "infinitas install check-target",
            build_check_install_target_parser,
            "infinitas install check-target",
        ),
        (
            "infinitas install resolve-skill",
            build_install_resolve_skill_parser,
            "infinitas install resolve-skill",
        ),
        ("infinitas install exact", build_install_exact_parser, "infinitas install exact"),
        (
            "infinitas install from-share",
            build_install_from_share_parser,
            "infinitas install from-share",
        ),
        ("infinitas install by-name", build_install_by_name_parser, "infinitas install by-name"),
        ("infinitas install sync", build_install_sync_parser, "infinitas install sync"),
        (
            "infinitas install check-update",
            build_install_check_update_parser,
            "infinitas install check-update",
        ),
        ("infinitas install switch", build_install_switch_parser, "infinitas install switch"),
        ("infinitas install rollback", build_install_rollback_parser, "infinitas install rollback"),
        ("infinitas install upgrade", build_install_upgrade_parser, "infinitas install upgrade"),
    ]


def _openclaw_and_policy_sections() -> list[Section]:
    return [
        ("infinitas openclaw", build_openclaw_parser, "infinitas openclaw"),
        ("infinitas openclaw profile", build_openclaw_profile_parser, "infinitas openclaw profile"),
        (
            "infinitas openclaw workspace resolve",
            build_openclaw_workspace_resolve_parser,
            "infinitas openclaw workspace resolve",
        ),
        (
            "infinitas openclaw skill validate",
            build_openclaw_skill_validate_parser,
            "infinitas openclaw skill validate",
        ),
        (
            "infinitas openclaw plugin inspect",
            build_openclaw_plugin_inspect_parser,
            "infinitas openclaw plugin inspect",
        ),
        ("infinitas policy", build_policy_parser, "infinitas policy"),
        (
            "infinitas policy check-packs",
            build_check_policy_packs_parser,
            "infinitas policy check-packs",
        ),
        (
            "infinitas policy check-promotion",
            build_check_promotion_parser,
            "infinitas policy check-promotion",
        ),
        (
            "infinitas policy recommend-reviewers",
            build_recommend_reviewers_parser,
            "infinitas policy recommend-reviewers",
        ),
        (
            "infinitas policy review-status",
            build_review_status_parser,
            "infinitas policy review-status",
        ),
    ]


def _registry_sections() -> list[Section]:
    return [
        ("infinitas registry", build_registry_parser, "infinitas registry"),
        ("infinitas registry skills", build_registry_skills_parser, "infinitas registry skills"),
        (
            "infinitas registry versions",
            build_registry_versions_parser,
            "infinitas registry versions",
        ),
        (
            "infinitas registry releases",
            build_registry_releases_parser,
            "infinitas registry releases",
        ),
        (
            "infinitas registry exposures",
            build_registry_exposures_parser,
            "infinitas registry exposures",
        ),
        ("infinitas registry shares", build_registry_shares_parser, "infinitas registry shares"),
        ("infinitas registry tokens", build_registry_tokens_parser, "infinitas registry tokens"),
        ("infinitas registry reviews", build_registry_reviews_parser, "infinitas registry reviews"),
    ]


def _release_and_server_sections() -> list[Section]:
    return [
        ("infinitas release", build_release_parser, "infinitas release"),
        (
            "infinitas release check-state",
            build_release_check_state_parser,
            "infinitas release check-state",
        ),
        (
            "infinitas release signing-readiness",
            build_signing_readiness_parser,
            "infinitas release signing-readiness",
        ),
        (
            "infinitas release doctor-signing",
            build_signing_doctor_parser,
            "infinitas release doctor-signing",
        ),
        (
            "infinitas release bootstrap-signing",
            build_signing_bootstrap_parser,
            "infinitas release bootstrap-signing",
        ),
        ("infinitas server", build_server_parser, "infinitas server"),
        (
            "infinitas server healthcheck",
            build_server_healthcheck_parser,
            "infinitas server healthcheck",
        ),
        ("infinitas server backup", build_server_backup_parser, "infinitas server backup"),
        (
            "infinitas server inspect-state",
            build_server_inspect_state_parser,
            "infinitas server inspect-state",
        ),
        (
            "infinitas server render-systemd",
            build_server_render_systemd_parser,
            "infinitas server render-systemd",
        ),
        (
            "infinitas server prune-backups",
            build_server_prune_backups_parser,
            "infinitas server prune-backups",
        ),
        ("infinitas server worker", build_server_worker_parser, "infinitas server worker"),
        (
            "infinitas server worker-healthcheck",
            build_server_worker_healthcheck_parser,
            "infinitas server worker-healthcheck",
        ),
    ]


def _sections() -> list[Section]:
    return (
        _discovery_and_install_sections()
        + _openclaw_and_policy_sections()
        + _registry_sections()
        + _release_and_server_sections()
    )


def _document_header() -> list[str]:
    return [
        "---",
        "audience: contributors, integrators, operators",
        "owner: repository maintainers",
        "source_of_truth: generated from argparse definitions in src/infinitas_skill",
        f"last_reviewed: {GENERATED_CLI_REFERENCE_LAST_REVIEWED}",
        "status: maintained",
        "---",
        "",
        "# CLI Reference",
        "",
        "This file is generated from the maintained argparse definitions under `src/infinitas_skill/`.",
        "",
        "Regenerate and review it with:",
        "",
        "```bash",
        "uv run python3 -m infinitas_skill.cli.reference",
        "```",
        "",
    ]


def render_cli_reference() -> str:
    lines = _document_header()
    lines.extend(
        ["## Top-level CLI", "", _render_help_block(_stable_help(build_parser())).rstrip(), ""]
    )
    for title, factory, prog in _sections():
        lines.extend(
            [
                f"## `{title}`",
                "",
                _render_help_block(_stable_help(factory(prog=prog))).rstrip(),
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    print(render_cli_reference(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
