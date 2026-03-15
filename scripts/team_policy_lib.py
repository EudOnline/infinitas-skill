#!/usr/bin/env python3
import re
from pathlib import Path

from policy_pack_lib import PolicyPackError, load_policy_domain_resolution

ROOT = Path(__file__).resolve().parent.parent
TEAM_NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


class TeamPolicyError(Exception):
    def __init__(self, errors):
        super().__init__('invalid team policy')
        self.errors = errors


def unique_strings(values):
    seen = set()
    result = []
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_actor_list(values):
    if values is None:
        return []
    if not isinstance(values, list):
        return []
    return unique_strings([item.strip() for item in values if isinstance(item, str) and item.strip()])


def validate_team_policy(payload):
    errors = []
    if not isinstance(payload, dict):
        return ['team policy must be a JSON object']

    unknown_root = sorted(set(payload) - {'$schema', 'version', 'teams'})
    if unknown_root:
        errors.append(f'team-policy has unsupported keys: {", ".join(unknown_root)}')
    if '$schema' in payload and not isinstance(payload.get('$schema'), str):
        errors.append('team-policy $schema must be a string when present')
    version = payload.get('version')
    if not isinstance(version, int) or version < 1:
        errors.append('team-policy version must be an integer >= 1')

    raw_teams = payload.get('teams', {})
    if not isinstance(raw_teams, dict):
        errors.append('team-policy teams must be an object')
        raw_teams = {}

    normalized = {}
    for team_name, raw_team in raw_teams.items():
        if not isinstance(team_name, str) or not TEAM_NAME_RE.match(team_name):
            errors.append(f'team-policy teams contains invalid team name {team_name!r}')
            continue
        if not isinstance(raw_team, dict):
            errors.append(f'team-policy teams.{team_name} must be an object')
            continue
        unknown = sorted(set(raw_team) - {'members', 'delegates', 'description'})
        if unknown:
            errors.append(f'team-policy teams.{team_name} has unsupported keys: {", ".join(unknown)}')
        members = normalize_actor_list(raw_team.get('members'))
        delegates = normalize_actor_list(raw_team.get('delegates'))
        if raw_team.get('members') is not None and not isinstance(raw_team.get('members'), list):
            errors.append(f'team-policy teams.{team_name}.members must be an array when present')
        if raw_team.get('delegates') is not None and not isinstance(raw_team.get('delegates'), list):
            errors.append(f'team-policy teams.{team_name}.delegates must be an array when present')
        description = raw_team.get('description')
        if description is not None and not isinstance(description, str):
            errors.append(f'team-policy teams.{team_name}.description must be a string when present')
            description = None
        normalized[team_name] = {
            'members': members,
            'delegates': delegates,
            'description': description.strip() if isinstance(description, str) and description.strip() else None,
        }

    return errors, normalized


def load_team_policy(root=ROOT):
    root = Path(root).resolve()
    path = root / 'policy' / 'team-policy.json'
    try:
        resolution = load_policy_domain_resolution(root, 'team_policy')
    except PolicyPackError as exc:
        if exc.errors and all(error.startswith("missing policy source for domain 'team_policy'") for error in exc.errors):
            return {
                'path': path,
                'version': 1,
                'teams': {},
                'effective_sources': [],
            }
        raise TeamPolicyError(exc.errors) from exc

    payload = resolution.get('effective') or {}
    errors, teams = validate_team_policy(payload)
    if errors:
        raise TeamPolicyError(errors)
    return {
        'path': path,
        'version': payload.get('version'),
        'teams': teams,
        'effective_sources': resolution.get('effective_sources', []),
    }


def resolve_team(team_name, policy):
    policy = policy if isinstance(policy, dict) else {}
    teams = policy.get('teams') or {}
    return teams.get(team_name)


def expand_team_refs(team_names, policy):
    policy = policy if isinstance(policy, dict) else {}
    teams = policy.get('teams') or {}
    resolved_teams = []
    actors = []
    missing = []
    for raw_name in team_names or []:
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        team_name = raw_name.strip()
        team = teams.get(team_name)
        if not team:
            missing.append(team_name)
            continue
        if team_name not in resolved_teams:
            resolved_teams.append(team_name)
        actors.extend(team.get('members', []))
        actors.extend(team.get('delegates', []))
    return {
        'actors': unique_strings(actors),
        'resolved_teams': resolved_teams,
        'missing_teams': unique_strings(missing),
    }
