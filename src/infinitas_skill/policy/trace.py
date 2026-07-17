from typing import Any

JsonDict = dict[str, Any]


def _dedupe_strings(values: object) -> list[str]:
    seen: list[str] = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _clean_rule_list(values: object) -> list[JsonDict]:
    result: list[JsonDict] = []
    for value in values if isinstance(values, list) else []:
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
            result.append({"rule": value.strip()})
    return result


def build_policy_trace(
    *,
    domain: str,
    decision: str,
    summary: str,
    effective_sources: list[JsonDict] | None = None,
    applied_rules: object = None,
    blocking_rules: object = None,
    reasons: object = None,
    next_actions: object = None,
    exceptions: object = None,
) -> JsonDict:
    return {
        "domain": domain,
        "decision": decision,
        "summary": summary.strip() if isinstance(summary, str) and summary.strip() else "",
        "effective_sources": list(effective_sources or []),
        "applied_rules": _clean_rule_list(applied_rules),
        "blocking_rules": _clean_rule_list(blocking_rules),
        "reasons": _dedupe_strings(reasons),
        "next_actions": _dedupe_strings(next_actions),
        "exceptions": _clean_rule_list(exceptions),
    }


def render_policy_trace(trace: object) -> str:
    trace = trace if isinstance(trace, dict) else {}
    lines = [
        f"policy domain: {trace.get('domain') or '-'}",
        f"decision: {trace.get('decision') or '-'}",
        f"summary: {trace.get('summary') or '-'}",
    ]
    lines.extend(_render_sources(trace.get("effective_sources")))
    for field in ["applied_rules", "blocking_rules"]:
        lines.extend(_render_items(field, trace.get(field)))
    lines.extend(_render_exceptions(trace.get("exceptions")))
    for field in ["reasons", "next_actions"]:
        lines.extend(_render_items(field, trace.get(field)))
    return "\n".join(lines)


def _render_sources(values: object) -> list[str]:
    sources = values if isinstance(values, list) else []
    if not sources:
        return []
    lines = ["effective_sources:"]
    for source in sources:
        if not isinstance(source, dict):
            lines.append(f"- {source}")
            continue
        label = source.get("name") or source.get("path") or source.get("kind") or "source"
        path = source.get("path")
        lines.append(f"- {label} ({path})" if path and path != label else f"- {label}")
    return lines


def _render_items(field: str, values: object) -> list[str]:
    items = values if isinstance(values, list) else []
    if not items:
        return []
    lines = [f"{field}:"]
    for item in items:
        text = (
            item.get("rule") or item.get("message") or str(item)
            if isinstance(item, dict)
            else str(item)
        )
        lines.append(f"- {text}")
    return lines


def _render_exceptions(values: object) -> list[str]:
    items = values if isinstance(values, list) else []
    if not items:
        return []
    lines = ["exceptions:"]
    for item in items:
        if not isinstance(item, dict):
            lines.append(f"- {item}")
            continue
        text = item.get("id") or item.get("rule") or item.get("message") or str(item)
        detail = [f"{key}={item[key]}" for key in ["justification", "expires_at"] if item.get(key)]
        lines.append(f"- {text} ({', '.join(detail)})" if detail else f"- {text}")
    return lines
