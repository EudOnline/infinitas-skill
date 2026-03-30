"""Generate CLI reference documentation from argparse definitions."""

from infinitas_skill.cli.main import build_parser
from infinitas_skill.compatibility.checks import build_platform_contracts_parser
from infinitas_skill.install.planning import (
    build_check_install_target_parser,
    build_resolve_install_plan_parser,
)
from infinitas_skill.policy.cli import (
    build_check_policy_packs_parser,
    build_check_promotion_parser,
    build_policy_parser,
)
from infinitas_skill.registry.cli import build_registry_parser
from infinitas_skill.release.state import build_release_check_state_parser
from infinitas_skill.server.ops import (
    build_server_backup_parser,
    build_server_healthcheck_parser,
    build_server_inspect_state_parser,
    build_server_parser,
    build_server_prune_backups_parser,
    build_server_render_systemd_parser,
    build_server_worker_parser,
)

GENERATED_CLI_REFERENCE_LAST_REVIEWED = '2026-03-30'


def _render_help_block(text: str) -> str:
    return f'```text\n{text.rstrip()}\n```\n'


def render_cli_reference() -> str:
    top_level_help = build_parser().format_help()
    compatibility_help = build_platform_contracts_parser(
        prog='infinitas compatibility check-platform-contracts'
    ).format_help()
    install_resolve_plan_help = build_resolve_install_plan_parser(prog='infinitas install resolve-plan').format_help()
    install_check_target_help = build_check_install_target_parser(prog='infinitas install check-target').format_help()
    policy_help = build_policy_parser(prog='infinitas policy').format_help()
    policy_check_packs_help = build_check_policy_packs_parser(prog='infinitas policy check-packs').format_help()
    policy_check_promotion_help = build_check_promotion_parser(prog='infinitas policy check-promotion').format_help()
    registry_help = build_registry_parser(prog='infinitas registry').format_help()
    release_help = build_release_check_state_parser(prog='infinitas release check-state').format_help()
    server_help = build_server_parser(prog='infinitas server').format_help()
    server_healthcheck_help = build_server_healthcheck_parser(prog='infinitas server healthcheck').format_help()
    server_backup_help = build_server_backup_parser(prog='infinitas server backup').format_help()
    server_inspect_state_help = build_server_inspect_state_parser(prog='infinitas server inspect-state').format_help()
    server_render_systemd_help = build_server_render_systemd_parser(prog='infinitas server render-systemd').format_help()
    server_prune_backups_help = build_server_prune_backups_parser(prog='infinitas server prune-backups').format_help()
    server_worker_help = build_server_worker_parser(prog='infinitas server worker').format_help()
    lines = [
        '---',
        'audience: contributors, integrators, operators',
        'owner: repository maintainers',
        'source_of_truth: generated from argparse definitions in src/infinitas_skill',
        f'last_reviewed: {GENERATED_CLI_REFERENCE_LAST_REVIEWED}',
        'status: maintained',
        '---',
        '',
        '# CLI Reference',
        '',
        'This file is generated from the maintained argparse definitions under `src/infinitas_skill/`.',
        '',
        'Regenerate and review it with:',
        '',
        '```bash',
        'uv run python3 -m infinitas_skill.cli.reference',
        '```',
        '',
        '## Top-level CLI',
        '',
        _render_help_block(top_level_help).rstrip(),
        '',
        '## `infinitas compatibility check-platform-contracts`',
        '',
        _render_help_block(compatibility_help).rstrip(),
        '',
        '## `infinitas install resolve-plan`',
        '',
        _render_help_block(install_resolve_plan_help).rstrip(),
        '',
        '## `infinitas install check-target`',
        '',
        _render_help_block(install_check_target_help).rstrip(),
        '',
        '## `infinitas policy`',
        '',
        _render_help_block(policy_help).rstrip(),
        '',
        '## `infinitas policy check-packs`',
        '',
        _render_help_block(policy_check_packs_help).rstrip(),
        '',
        '## `infinitas policy check-promotion`',
        '',
        _render_help_block(policy_check_promotion_help).rstrip(),
        '',
        '## `infinitas registry`',
        '',
        _render_help_block(registry_help).rstrip(),
        '',
        '## `infinitas release check-state`',
        '',
        _render_help_block(release_help).rstrip(),
        '',
        '## `infinitas server`',
        '',
        _render_help_block(server_help).rstrip(),
        '',
        '## `infinitas server healthcheck`',
        '',
        _render_help_block(server_healthcheck_help).rstrip(),
        '',
        '## `infinitas server backup`',
        '',
        _render_help_block(server_backup_help).rstrip(),
        '',
        '## `infinitas server inspect-state`',
        '',
        _render_help_block(server_inspect_state_help).rstrip(),
        '',
        '## `infinitas server render-systemd`',
        '',
        _render_help_block(server_render_systemd_help).rstrip(),
        '',
        '## `infinitas server prune-backups`',
        '',
        _render_help_block(server_prune_backups_help).rstrip(),
        '',
        '## `infinitas server worker`',
        '',
        _render_help_block(server_worker_help).rstrip(),
        '',
    ]
    return '\n'.join(lines)


def main() -> int:
    print(render_cli_reference(), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
