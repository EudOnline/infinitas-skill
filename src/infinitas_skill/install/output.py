from __future__ import annotations


def error_to_payload(error):
    payload = {"error": error.message}
    payload.update(error.details or {})
    return payload


def plan_to_text(plan):
    lines = []
    root = plan.get("root") or {}
    root_display = root.get("qualified_name") or root.get("name")
    lines.append(f"resolution plan: {root_display}@{root.get('version')} from {root.get('registry')}")
    for step in plan.get("steps", []):
        action = step.get("action")
        stage = step.get("stage")
        registry = step.get("registry")
        display = step.get("qualified_name") or step.get("name")
        head = f"- [{action}] {display}@{step.get('version')} ({stage}) from {registry}"
        if step.get("source_commit"):
            head += f" @{step.get('source_commit')[:12]}"
        elif step.get("source_tag"):
            head += f" tag={step.get('source_tag')}"
        elif step.get("source_ref"):
            head += f" ref={step.get('source_ref')}"
        lines.append(head)
        for requester in step.get("requested_by", []):
            requester_name = requester.get("by_qualified_name") or requester.get("by")
            lines.append(
                f"    requested by {requester_name}@{requester.get('version')} -> {requester.get('constraint')}"
                + (f" [{requester.get('registry')}]" if requester.get("registry") else "")
                + (" +incubating" if requester.get("allow_incubating") else "")
            )
    return "\n".join(lines)
