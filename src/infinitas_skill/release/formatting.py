"""Formatting helpers for maintained release state output."""


def format_release_state(state):
    lines = [
        f"skill: {state['skill']['name']}",
        f"version: {state['skill']['version']}",
        f"qualified_name: {state['skill'].get('qualified_name') or '-'}",
        f"mode: {state['mode']}",
        f"branch: {state['git']['branch'] or '-'}",
        f"upstream: {state['git']['upstream'] or '-'}",
        f"head: {state['git']['head_commit']}",
        f"expected_tag: {state['git']['expected_tag']}",
        f"releaser: {(state.get('release') or {}).get('releaser_identity') or '-'}",
        f"release_ready: {'yes' if state['release_ready'] else 'no'}",
    ]
    if state['warnings']:
        lines.append('warnings:')
        lines.extend(f'- {item}' for item in state['warnings'])
    if state['errors']:
        lines.append('errors:')
        lines.extend(f'- {item}' for item in state['errors'])
    return '\n'.join(lines)
