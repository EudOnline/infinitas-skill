from __future__ import annotations


def candidate_view(candidate):
    return {
        "name": candidate.get("name"),
        "publisher": candidate.get("publisher"),
        "qualified_name": candidate.get("qualified_name"),
        "version": candidate.get("version"),
        "registry": candidate.get("registry_name"),
        "stage": candidate.get("stage"),
        "path": candidate.get("path"),
        "source_type": candidate.get("source_type"),
        "distribution_manifest": candidate.get("distribution_manifest"),
        "source_snapshot_tag": candidate.get("source_snapshot_tag"),
        "source_snapshot_commit": candidate.get("source_snapshot_commit"),
    }


def installed_view(installed):
    return {
        "name": installed.get("name"),
        "publisher": installed.get("publisher"),
        "qualified_name": installed.get("qualified_name"),
        "version": installed.get("version"),
        "locked_version": installed.get("locked_version"),
        "registry": installed.get("source_registry"),
        "path": installed.get("path"),
    }


def plan_action(identity_key, candidate, installed_item, root_candidate, mode):
    root_identity = root_candidate.get("identity_key") or root_candidate.get("name")
    if not installed_item:
        return "sync" if identity_key == root_identity and mode == "sync" else "install"
    same_version = installed_item.get("version") == candidate.get("version") or installed_item.get(
        "locked_version"
    ) == candidate.get("version")
    same_registry = not installed_item.get("source_registry") or installed_item.get("source_registry") == candidate.get(
        "registry_name"
    )
    if identity_key == root_identity and mode == "sync":
        return "sync" if not (same_version and same_registry) else "keep"
    if same_version and same_registry:
        return "keep"
    if same_version and not same_registry:
        return "switch"
    if not same_version and same_registry:
        return "upgrade"
    return "switch-upgrade"


def build_plan(root_candidate, selected, installed, catalog, mode):
    apply_order = []
    visited = set()

    def visit(identity_key):
        if identity_key in visited:
            return
        visited.add(identity_key)
        candidate = selected[identity_key]
        deps = sorted(
            candidate.get("depends_on", []),
            key=lambda item: (item.get("name") or "", item.get("version") or "*"),
        )
        for dep in deps:
            dep_key = dep.get("identity_key") or dep.get("name")
            if dep_key in selected:
                visit(dep_key)
        apply_order.append(identity_key)

    root_identity = root_candidate.get("identity_key") or root_candidate.get("name")
    visit(root_identity)
    requesters = {}
    for candidate in selected.values():
        for dep in candidate.get("depends_on", []):
            dep_key = dep.get("identity_key") or dep.get("name")
            requesters.setdefault(dep_key, []).append(
                {
                    "by": candidate.get("name"),
                    "by_qualified_name": candidate.get("qualified_name"),
                    "version": candidate.get("version"),
                    "registry": dep.get("registry"),
                    "constraint": dep.get("version"),
                    "allow_incubating": dep.get("allow_incubating", False),
                }
            )

    steps = []
    for index, identity_key in enumerate(apply_order, start=1):
        candidate = selected[identity_key]
        installed_item = installed.get(identity_key)
        action = plan_action(identity_key, candidate, installed_item, root_candidate, mode)
        steps.append(
            {
                "order": index,
                "name": candidate.get("name"),
                "publisher": candidate.get("publisher"),
                "qualified_name": candidate.get("qualified_name"),
                "identity_mode": candidate.get("identity_mode"),
                "version": candidate.get("version"),
                "registry": candidate.get("registry_name"),
                "stage": candidate.get("stage"),
                "path": candidate.get("path"),
                "skill_path": candidate.get("skill_path"),
                "relative_path": candidate.get("relative_path"),
                "source_type": candidate.get("source_type"),
                "distribution_manifest": candidate.get("distribution_manifest"),
                "distribution_bundle": candidate.get("distribution_bundle"),
                "distribution_bundle_sha256": candidate.get("distribution_bundle_sha256"),
                "distribution_attestation": candidate.get("distribution_attestation"),
                "distribution_attestation_signature": candidate.get("distribution_attestation_signature"),
                "action": action,
                "needs_apply": action not in {"keep"},
                "requested_by": requesters.get(identity_key, []),
                "depends_on": candidate.get("depends_on", []),
                "conflicts_with": candidate.get("conflicts_with", []),
                "root": identity_key == root_identity,
                "source_commit": candidate.get("registry_commit"),
                "source_ref": candidate.get("registry_ref"),
                "source_tag": candidate.get("registry_tag"),
                "source_snapshot_kind": candidate.get("source_snapshot_kind"),
                "source_snapshot_tag": candidate.get("source_snapshot_tag"),
                "source_snapshot_ref": candidate.get("source_snapshot_ref"),
                "source_snapshot_commit": candidate.get("source_snapshot_commit"),
            }
        )
    return {
        "mode": mode,
        "root": candidate_view(root_candidate),
        "steps": steps,
        "registries_consulted": [reg.get("name") for reg in catalog.get("registries", [])],
    }
