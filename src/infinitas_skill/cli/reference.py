"""Generate CLI reference documentation from argparse definitions."""

from infinitas_skill.cli.main import build_parser
from infinitas_skill.compatibility.checks import build_platform_contracts_parser
from infinitas_skill.release.state import build_release_check_state_parser

GENERATED_CLI_REFERENCE_LAST_REVIEWED = '2026-03-30'


def _render_help_block(text: str) -> str:
    return f'```text\n{text.rstrip()}\n```\n'


def render_cli_reference() -> str:
    top_level_help = build_parser().format_help()
    compatibility_help = build_platform_contracts_parser(
        prog='infinitas compatibility check-platform-contracts'
    ).format_help()
    release_help = build_release_check_state_parser(prog='infinitas release check-state').format_help()
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
        '## `infinitas release check-state`',
        '',
        _render_help_block(release_help).rstrip(),
        '',
    ]
    return '\n'.join(lines)


def main() -> int:
    print(render_cli_reference(), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
