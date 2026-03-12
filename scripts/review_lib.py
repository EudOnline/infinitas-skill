#!/usr/bin/env python3
import json
import re
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DECISIONS = {'approved', 'rejected'}
ALLOWED_REVIEW_STATES = {'draft', 'under-review', 'approved', 'rejected'}
ALLOWED_RISK = {'low', 'medium', 'high'}
ALLOWED_STAGE = {'incubating', 'active', 'archived'}
GROUP_NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
MIN_TIME = datetime(1970, 1, 1, tzinfo=timezone.utc)


class ReviewPolicyError(Exception):
    def __init__(self, errors):
        super().__init__('invalid promotion policy')
        self.errors = errors


def unique_strings(values):
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def resolve_skill(root: Path, arg: str) -> Path:
    direct = Path(arg)
    if direct.is_dir() and (direct / '_meta.json').exists():
        return direct.resolve()
    if not direct.is_absolute():
        repo_relative = (root / direct).resolve()
        if repo_relative.is_dir() and (repo_relative / '_meta.json').exists():
            return repo_relative
    for stage in ['incubating', 'active', 'archived']:
        candidate = root / 'skills' / stage / arg
        if candidate.is_dir() and (candidate / '_meta.json').exists():
            return candidate.resolve()
    raise SystemExit(f'cannot resolve skill: {arg}')


def load_meta(skill_dir: Path):
    return load_json(skill_dir / '_meta.json')


def load_reviews(skill_dir: Path):
    path = skill_dir / 'reviews.json'
    if path.exists():
        payload = load_json(path)
    else:
        payload = {'version': 1, 'requests': [], 'entries': []}
    if not isinstance(payload, dict):
        payload = {'version': 1, 'requests': [], 'entries': []}
    if not isinstance(payload.get('version'), int):
        payload['version'] = 1
    if not isinstance(payload.get('requests'), list):
        payload['requests'] = []
    if not isinstance(payload.get('entries'), list):
        payload['entries'] = []
    return payload


def save_reviews(skill_dir: Path, reviews):
    write_json(skill_dir / 'reviews.json', reviews)


def normalize_groups(raw_groups):
    errors = []
    normalized = {}
    if raw_groups is None:
        return normalized, errors
    if not isinstance(raw_groups, dict):
        return {}, ['reviews.groups must be an object']
    for group_name, raw_group in raw_groups.items():
        if not isinstance(group_name, str) or not GROUP_NAME_RE.match(group_name):
            errors.append(f'reviews.groups contains invalid group name {group_name!r}')
            continue
        description = None
        if isinstance(raw_group, list):
            members = raw_group
        elif isinstance(raw_group, dict):
            members = raw_group.get('members', [])
            description = raw_group.get('description')
            unknown = sorted(set(raw_group) - {'members', 'description'})
            if unknown:
                errors.append(f'reviews.groups.{group_name} has unsupported keys: {", ".join(unknown)}')
        else:
            errors.append(f'reviews.groups.{group_name} must be an array or object')
            continue
        if not isinstance(members, list) or not all(isinstance(item, str) and item.strip() for item in members):
            errors.append(f'reviews.groups.{group_name}.members must be an array of non-empty strings')
            members = []
        if description is not None and not isinstance(description, str):
            errors.append(f'reviews.groups.{group_name}.description must be a string when present')
            description = None
        normalized[group_name] = {
            'members': unique_strings([item.strip() for item in members if isinstance(item, str) and item.strip()]),
            'description': description.strip() if isinstance(description, str) and description.strip() else None,
        }
    return normalized, errors


def normalize_quorum_rule(path, raw_rule):
    errors = []
    normalized = {}
    if raw_rule is None:
        return normalized, errors
    if not isinstance(raw_rule, dict):
        return {}, [f'{path} must be an object']
    unknown = sorted(set(raw_rule) - {'min_approvals', 'required_groups'})
    if unknown:
        errors.append(f'{path} has unsupported keys: {", ".join(unknown)}')
    if 'min_approvals' in raw_rule:
        min_approvals = raw_rule.get('min_approvals')
        if not isinstance(min_approvals, int) or min_approvals < 0:
            errors.append(f'{path}.min_approvals must be a non-negative integer')
        else:
            normalized['min_approvals'] = min_approvals
    if 'required_groups' in raw_rule:
        required_groups = raw_rule.get('required_groups')
        if not isinstance(required_groups, list) or not all(isinstance(item, str) and item.strip() for item in required_groups):
            errors.append(f'{path}.required_groups must be an array of non-empty strings')
        else:
            normalized['required_groups'] = unique_strings([item.strip() for item in required_groups])
    return normalized, errors


def normalize_quorum(reviews_cfg):
    errors = []
    normalized = {
        'defaults': {},
        'stage_overrides': {},
        'risk_overrides': {},
        'stage_risk_overrides': {},
    }

    if 'default_min_approvals' in reviews_cfg:
        default_min = reviews_cfg.get('default_min_approvals')
        if not isinstance(default_min, int) or default_min < 0:
            errors.append('reviews.default_min_approvals must be a non-negative integer')
        else:
            normalized['defaults']['min_approvals'] = default_min

    legacy_risk_overrides = reviews_cfg.get('risk_overrides')
    if legacy_risk_overrides is not None:
        if not isinstance(legacy_risk_overrides, dict):
            errors.append('reviews.risk_overrides must be an object when present')
        else:
            for risk_level, raw_rule in legacy_risk_overrides.items():
                if risk_level not in ALLOWED_RISK:
                    errors.append(f'reviews.risk_overrides contains invalid risk level {risk_level!r}')
                    continue
                if isinstance(raw_rule, int):
                    if raw_rule < 0:
                        errors.append(f'reviews.risk_overrides.{risk_level} must be non-negative')
                    else:
                        normalized['risk_overrides'][risk_level] = {'min_approvals': raw_rule}
                    continue
                rule, rule_errors = normalize_quorum_rule(f'reviews.risk_overrides.{risk_level}', raw_rule)
                normalized['risk_overrides'][risk_level] = rule
                errors.extend(rule_errors)

    raw_quorum = reviews_cfg.get('quorum')
    if raw_quorum is None:
        return normalized, errors
    if not isinstance(raw_quorum, dict):
        errors.append('reviews.quorum must be an object when present')
        return normalized, errors

    defaults, default_errors = normalize_quorum_rule('reviews.quorum.defaults', raw_quorum.get('defaults', {}))
    normalized['defaults'].update(defaults)
    errors.extend(default_errors)

    stage_overrides = raw_quorum.get('stage_overrides', {})
    if not isinstance(stage_overrides, dict):
        errors.append('reviews.quorum.stage_overrides must be an object')
    else:
        for stage, raw_rule in stage_overrides.items():
            if stage not in ALLOWED_STAGE:
                errors.append(f'reviews.quorum.stage_overrides contains invalid stage {stage!r}')
                continue
            rule, rule_errors = normalize_quorum_rule(f'reviews.quorum.stage_overrides.{stage}', raw_rule)
            normalized['stage_overrides'][stage] = rule
            errors.extend(rule_errors)

    risk_overrides = raw_quorum.get('risk_overrides', {})
    if not isinstance(risk_overrides, dict):
        errors.append('reviews.quorum.risk_overrides must be an object')
    else:
        for risk_level, raw_rule in risk_overrides.items():
            if risk_level not in ALLOWED_RISK:
                errors.append(f'reviews.quorum.risk_overrides contains invalid risk level {risk_level!r}')
                continue
            rule, rule_errors = normalize_quorum_rule(f'reviews.quorum.risk_overrides.{risk_level}', raw_rule)
            normalized['risk_overrides'][risk_level] = rule
            errors.extend(rule_errors)

    stage_risk_overrides = raw_quorum.get('stage_risk_overrides', {})
    if not isinstance(stage_risk_overrides, dict):
        errors.append('reviews.quorum.stage_risk_overrides must be an object')
    else:
        for stage, raw_risk_map in stage_risk_overrides.items():
            if stage not in ALLOWED_STAGE:
                errors.append(f'reviews.quorum.stage_risk_overrides contains invalid stage {stage!r}')
                continue
            if not isinstance(raw_risk_map, dict):
                errors.append(f'reviews.quorum.stage_risk_overrides.{stage} must be an object')
                continue
            normalized['stage_risk_overrides'].setdefault(stage, {})
            for risk_level, raw_rule in raw_risk_map.items():
                if risk_level not in ALLOWED_RISK:
                    errors.append(f'reviews.quorum.stage_risk_overrides.{stage} contains invalid risk level {risk_level!r}')
                    continue
                rule, rule_errors = normalize_quorum_rule(f'reviews.quorum.stage_risk_overrides.{stage}.{risk_level}', raw_rule)
                normalized['stage_risk_overrides'][stage][risk_level] = rule
                errors.extend(rule_errors)

    return normalized, errors


def configured_reviewers(policy):
    reviews_cfg = policy.get('reviews', {}) if isinstance(policy, dict) else {}
    groups, _ = normalize_groups(reviews_cfg.get('groups', {}))
    reviewers = {}
    for group_name, group_data in groups.items():
        for reviewer in group_data.get('members', []):
            reviewers.setdefault(reviewer, {'groups': []})['groups'].append(group_name)
    for reviewer_data in reviewers.values():
        reviewer_data['groups'] = unique_strings(reviewer_data.get('groups', []))
    return groups, reviewers


def effective_quorum_rule(policy, stage, risk_level):
    reviews_cfg = policy.get('reviews', {}) if isinstance(policy, dict) else {}
    quorum, _ = normalize_quorum(reviews_cfg)
    rule = {'min_approvals': 0, 'required_groups': []}

    def apply(raw_rule):
        if 'min_approvals' in raw_rule:
            rule['min_approvals'] = raw_rule['min_approvals']
        if 'required_groups' in raw_rule:
            rule['required_groups'] = unique_strings(raw_rule['required_groups'])

    apply(quorum.get('defaults', {}))
    apply(quorum.get('stage_overrides', {}).get(stage, {}))
    apply(quorum.get('risk_overrides', {}).get(risk_level, {}))
    apply(quorum.get('stage_risk_overrides', {}).get(stage, {}).get(risk_level, {}))
    return rule


def owner_review_unavoidable(owner, reviewers, required_groups, min_approvals):
    if not owner:
        return False
    non_owner_reviewers = {
        reviewer: data
        for reviewer, data in (reviewers or {}).items()
        if reviewer != owner
    }
    if len(non_owner_reviewers) < (min_approvals or 0):
        return True
    if required_groups:
        covered_groups = set()
        for reviewer_data in non_owner_reviewers.values():
            covered_groups.update(reviewer_data.get('groups', []))
        if any(group_name not in covered_groups for group_name in required_groups):
            return True
    return False


def validate_promotion_policy(policy):
    errors = []
    if not isinstance(policy, dict):
        return ['promotion policy must be a JSON object']
    if 'version' in policy and (not isinstance(policy.get('version'), int) or policy.get('version') < 1):
        errors.append('version must be a positive integer')

    active_requires = policy.get('active_requires')
    if not isinstance(active_requires, dict):
        errors.append('active_requires must be an object')
    else:
        review_states = active_requires.get('review_state', [])
        if not isinstance(review_states, list) or not review_states:
            errors.append('active_requires.review_state must be a non-empty array')
        elif any(state not in ALLOWED_REVIEW_STATES for state in review_states):
            errors.append(f'active_requires.review_state must contain only {sorted(ALLOWED_REVIEW_STATES)}')
        for key in ['require_changelog', 'require_smoke_test', 'require_owner']:
            if key in active_requires and not isinstance(active_requires.get(key), bool):
                errors.append(f'active_requires.{key} must be boolean when present')

    reviews_cfg = policy.get('reviews')
    if not isinstance(reviews_cfg, dict):
        errors.append('reviews must be an object')
        return errors

    for key in ['require_reviews_file', 'reviewer_must_differ_from_owner', 'allow_owner_when_no_distinct_reviewer', 'block_on_rejection']:
        if key in reviews_cfg and not isinstance(reviews_cfg.get(key), bool):
            errors.append(f'reviews.{key} must be boolean when present')

    groups, group_errors = normalize_groups(reviews_cfg.get('groups', {}))
    errors.extend(group_errors)
    quorum, quorum_errors = normalize_quorum(reviews_cfg)
    errors.extend(quorum_errors)

    def validate_rule_groups(path, rule):
        for group_name in rule.get('required_groups', []):
            if group_name not in groups:
                errors.append(f'{path}.required_groups references unknown reviewer group {group_name!r}')

    validate_rule_groups('reviews.quorum.defaults', quorum.get('defaults', {}))
    for stage, rule in quorum.get('stage_overrides', {}).items():
        validate_rule_groups(f'reviews.quorum.stage_overrides.{stage}', rule)
    for risk_level, rule in quorum.get('risk_overrides', {}).items():
        validate_rule_groups(f'reviews.quorum.risk_overrides.{risk_level}', rule)
    for stage, risk_map in quorum.get('stage_risk_overrides', {}).items():
        for risk_level, rule in risk_map.items():
            validate_rule_groups(f'reviews.quorum.stage_risk_overrides.{stage}.{risk_level}', rule)

    high_risk = policy.get('high_risk_active_requires', {})
    if high_risk and not isinstance(high_risk, dict):
        errors.append('high_risk_active_requires must be an object when present')
    elif isinstance(high_risk, dict):
        if 'min_maintainers' in high_risk and (not isinstance(high_risk.get('min_maintainers'), int) or high_risk.get('min_maintainers') < 0):
            errors.append('high_risk_active_requires.min_maintainers must be a non-negative integer when present')
        if 'require_requires_block' in high_risk and not isinstance(high_risk.get('require_requires_block'), bool):
            errors.append('high_risk_active_requires.require_requires_block must be boolean when present')

    return errors


def load_promotion_policy(root: Path = ROOT):
    path = root / 'policy' / 'promotion-policy.json'
    policy = load_json(path)
    errors = validate_promotion_policy(policy)
    if errors:
        raise ReviewPolicyError(errors)
    return policy


def latest_distinct_entries(entries):
    latest = {}
    for index, raw_entry in enumerate(entries or []):
        if not isinstance(raw_entry, dict):
            continue
        reviewer = raw_entry.get('reviewer')
        if not isinstance(reviewer, str) or not reviewer.strip():
            continue
        timestamp = parse_timestamp(raw_entry.get('at')) or MIN_TIME
        rank = (timestamp, index)
        stored = latest.get(reviewer)
        if stored is None or rank >= stored[0]:
            latest[reviewer] = (rank, dict(raw_entry))
    return {reviewer: entry for reviewer, (_, entry) in sorted(latest.items())}


def evaluate_review_state(skill_dir: Path, root: Path = ROOT, stage: Optional[str] = None, as_active: bool = False, policy=None):
    skill_dir = Path(skill_dir).resolve()
    policy = policy or load_promotion_policy(root)
    meta = load_meta(skill_dir)
    reviews = load_reviews(skill_dir)
    latest = latest_distinct_entries(reviews.get('entries', []))
    groups, reviewers = configured_reviewers(policy)
    reviews_cfg = policy.get('reviews', {})
    actual_stage = meta.get('status') or skill_dir.parent.name
    evaluated_stage = 'active' if as_active else (stage or actual_stage)
    risk_level = meta.get('risk_level')
    owner = meta.get('owner')
    quorum_rule = effective_quorum_rule(policy, evaluated_stage, risk_level)
    owner_fallback_allowed = (
        reviews_cfg.get('allow_owner_when_no_distinct_reviewer')
        and owner_review_unavoidable(
            owner,
            reviewers,
            quorum_rule.get('required_groups', []),
            quorum_rule.get('min_approvals', 0),
        )
    )

    approvals = []
    rejections = []
    latest_decisions = []
    ignored_decisions = []
    covered_groups = []
    covered_group_set = set()

    for reviewer, entry in sorted(latest.items()):
        reviewer_groups = reviewers.get(reviewer, {}).get('groups', [])
        reasons = []
        decision = entry.get('decision')
        if reviewer not in reviewers:
            reasons.append('unconfigured reviewer')
        if decision not in ALLOWED_DECISIONS:
            reasons.append('invalid decision')
        if reviewer == owner and reviews_cfg.get('reviewer_must_differ_from_owner') and not owner_fallback_allowed:
            reasons.append('reviewer is owner')
        counted = not reasons
        item = {
            'reviewer': reviewer,
            'decision': decision,
            'at': entry.get('at'),
            'note': entry.get('note'),
            'groups': reviewer_groups,
            'counted': counted,
            'reasons': reasons,
        }
        latest_decisions.append(item)
        if not counted:
            ignored_decisions.append(item)
            continue
        if decision == 'approved':
            approvals.append(item)
            for group_name in reviewer_groups:
                if group_name in covered_group_set:
                    continue
                covered_group_set.add(group_name)
                covered_groups.append(group_name)
        elif decision == 'rejected':
            rejections.append(item)

    required_groups = quorum_rule.get('required_groups', [])
    missing_groups = [group_name for group_name in required_groups if group_name not in covered_group_set]
    quorum_met = len(approvals) >= quorum_rule.get('min_approvals', 0) and not missing_groups
    reviews_file_present = (skill_dir / 'reviews.json').is_file()
    has_activity = bool(reviews.get('requests') or reviews.get('entries'))
    blocking_rejection_count = len(rejections) if reviews_cfg.get('block_on_rejection', False) else 0
    review_gate_pass = (not reviews_cfg.get('require_reviews_file') or reviews_file_present) and quorum_met and blocking_rejection_count == 0

    if blocking_rejection_count:
        effective_review_state = 'rejected'
    elif review_gate_pass:
        effective_review_state = 'approved'
    elif has_activity:
        effective_review_state = 'under-review'
    else:
        effective_review_state = 'draft'

    return {
        'skill': meta.get('name', skill_dir.name),
        'version': meta.get('version'),
        'owner': owner,
        'risk_level': risk_level,
        'actual_stage': actual_stage,
        'evaluated_stage': evaluated_stage,
        'declared_review_state': meta.get('review_state'),
        'effective_review_state': effective_review_state,
        'reviews_file_present': reviews_file_present,
        'review_request_count': len(reviews.get('requests', [])),
        'required_approvals': quorum_rule.get('min_approvals', 0),
        'required_groups': required_groups,
        'covered_groups': covered_groups,
        'missing_groups': missing_groups,
        'approval_count': len(approvals),
        'rejection_count': len(rejections),
        'blocking_rejection_count': blocking_rejection_count,
        'quorum_met': quorum_met,
        'review_gate_pass': review_gate_pass,
        'latest_decisions': latest_decisions,
        'ignored_decisions': ignored_decisions,
        'configured_groups': groups,
        'configured_reviewers': sorted(reviewers),
    }


def sync_declared_review_state(skill_dir: Path, evaluation=None, root: Path = ROOT, stage: Optional[str] = None, as_active: bool = False, policy=None):
    skill_dir = Path(skill_dir).resolve()
    evaluation = evaluation or evaluate_review_state(skill_dir, root=root, stage=stage, as_active=as_active, policy=policy)
    meta_path = skill_dir / '_meta.json'
    meta = load_json(meta_path)
    meta['review_state'] = evaluation['effective_review_state']
    write_json(meta_path, meta)
    return evaluation


def request_review(skill_dir: Path, note: str = '', root: Path = ROOT):
    skill_dir = Path(skill_dir).resolve()
    policy = load_promotion_policy(root)
    reviews = load_reviews(skill_dir)
    reviews['requests'].append({
        'requested_at': utc_now_iso(),
        'note': note or None,
    })
    save_reviews(skill_dir, reviews)
    evaluation = evaluate_review_state(skill_dir, root=root, policy=policy)
    sync_declared_review_state(skill_dir, evaluation=evaluation, root=root, policy=policy)
    return evaluation


def record_review_decision(skill_dir: Path, reviewer: str, decision: str, note: str = '', root: Path = ROOT):
    skill_dir = Path(skill_dir).resolve()
    policy = load_promotion_policy(root)
    _, reviewers = configured_reviewers(policy)
    if reviewer not in reviewers:
        configured = ', '.join(sorted(reviewers)) if reviewers else '(none configured)'
        raise ValueError(f'unknown reviewer: {reviewer} (configured reviewers: {configured})')
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f'invalid decision: {decision}')
    reviews = load_reviews(skill_dir)
    reviews['entries'].append({
        'reviewer': reviewer,
        'decision': decision,
        'note': note or None,
        'at': utc_now_iso(),
    })
    save_reviews(skill_dir, reviews)
    evaluation = evaluate_review_state(skill_dir, root=root, policy=policy)
    sync_declared_review_state(skill_dir, evaluation=evaluation, root=root, policy=policy)
    return evaluation
