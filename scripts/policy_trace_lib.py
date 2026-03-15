#!/usr/bin/env python3


def _dedupe_strings(values):
    seen = []
    for value in values or []:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _clean_rule_list(values):
    result = []
    for value in values or []:
        if isinstance(value, dict):
            item = {}
            for key, raw in value.items():
                if isinstance(raw, str):
                    cleaned = raw.strip()
                    if cleaned:
                        item[key] = cleaned
                elif raw is not None:
                    item[key] = raw
            if item:
                result.append(item)
            continue
        if isinstance(value, str) and value.strip():
            result.append({'rule': value.strip()})
    return result


def build_policy_trace(
    *,
    domain,
    decision,
    summary,
    effective_sources=None,
    applied_rules=None,
    blocking_rules=None,
    reasons=None,
    next_actions=None,
    exceptions=None,
):
    return {
        'domain': domain,
        'decision': decision,
        'summary': summary.strip() if isinstance(summary, str) and summary.strip() else '',
        'effective_sources': list(effective_sources or []),
        'applied_rules': _clean_rule_list(applied_rules),
        'blocking_rules': _clean_rule_list(blocking_rules),
        'reasons': _dedupe_strings(reasons),
        'next_actions': _dedupe_strings(next_actions),
        'exceptions': _clean_rule_list(exceptions),
    }


def render_policy_trace(trace):
    trace = trace if isinstance(trace, dict) else {}
    lines = [
        f"policy domain: {trace.get('domain') or '-'}",
        f"decision: {trace.get('decision') or '-'}",
        f"summary: {trace.get('summary') or '-'}",
    ]
    sources = trace.get('effective_sources') or []
    if sources:
        lines.append('effective_sources:')
        for source in sources:
            label = source.get('name') or source.get('path') or source.get('kind') or 'source'
            path = source.get('path')
            if path and path != label:
                lines.append(f"- {label} ({path})")
            else:
                lines.append(f"- {label}")
    for field in ['applied_rules', 'blocking_rules']:
        values = trace.get(field) or []
        if not values:
            continue
        lines.append(f'{field}:')
        for item in values:
            if isinstance(item, dict):
                text = item.get('rule') or item.get('message') or str(item)
            else:
                text = str(item)
            lines.append(f'- {text}')
    exceptions = trace.get('exceptions') or []
    if exceptions:
        lines.append('exceptions:')
        for item in exceptions:
            if isinstance(item, dict):
                text = item.get('id') or item.get('rule') or item.get('message') or str(item)
                justification = item.get('justification')
                expires_at = item.get('expires_at')
                detail = []
                if justification:
                    detail.append(f'justification={justification}')
                if expires_at:
                    detail.append(f'expires_at={expires_at}')
                if detail:
                    text = f'{text} ({", ".join(detail)})'
            else:
                text = str(item)
            lines.append(f'- {text}')
    for field in ['reasons', 'next_actions']:
        values = trace.get(field) or []
        if not values:
            continue
        lines.append(f'{field}:')
        lines.extend(f'- {item}' for item in values)
    return '\n'.join(lines)
