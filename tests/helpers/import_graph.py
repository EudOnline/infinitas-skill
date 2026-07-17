from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from pathlib import Path

ImportGraph = dict[str, set[str]]


def discover_modules(package_roots: Iterable[Path]) -> dict[str, Path]:
    """Return importable module names and their source files for package roots."""
    modules: dict[str, Path] = {}
    for package_root in package_roots:
        package_root = package_root.resolve()
        package_name = package_root.name
        for path in sorted(package_root.rglob("*.py")):
            relative = path.relative_to(package_root)
            parts = list(relative.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            module_name = ".".join((package_name, *parts))
            modules[module_name] = path
    return modules


def build_import_graph(package_roots: Iterable[Path]) -> ImportGraph:
    """Build an AST-only graph containing imports between discovered modules."""
    modules = discover_modules(package_roots)
    graph: ImportGraph = {module_name: set() for module_name in modules}
    package_modules = {
        module_name for module_name, path in modules.items() if path.name == "__init__.py"
    }

    for source_module, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                candidates = (alias.name for alias in node.names)
                graph[source_module].update(
                    target
                    for candidate in candidates
                    if (target := _internal_target(candidate, modules)) is not None
                    and target != source_module
                )
            elif isinstance(node, ast.ImportFrom):
                graph[source_module].update(
                    _from_import_targets(
                        source_module,
                        node,
                        modules,
                        package_modules,
                    )
                )
        graph[source_module].discard(source_module)

    return graph


def strongly_connected_components(
    graph: Mapping[str, Iterable[str]],
) -> tuple[tuple[str, ...], ...]:
    """Return Tarjan strongly connected components in deterministic order."""
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(graph.get(node, ())):
            if target not in graph:
                continue
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])

        if lowlinks[node] != indices[node]:
            return

        component: list[str] = []
        while True:
            target = stack.pop()
            on_stack.remove(target)
            component.append(target)
            if target == node:
                break
        components.append(tuple(sorted(component)))

    for node in sorted(graph):
        if node not in indices:
            visit(node)

    return tuple(sorted(components))


def _from_import_targets(
    source_module: str,
    node: ast.ImportFrom,
    modules: Mapping[str, Path],
    package_modules: set[str],
) -> set[str]:
    base = _resolve_from_base(source_module, node, package_modules)
    if base is None:
        return set()

    targets: set[str] = set()
    for alias in node.names:
        candidate = base if alias.name == "*" else f"{base}.{alias.name}"
        target = _internal_target(candidate, modules)
        if target is None:
            target = _internal_target(base, modules)
        if target is not None and target != source_module:
            targets.add(target)
    return targets


def _resolve_from_base(
    source_module: str,
    node: ast.ImportFrom,
    package_modules: set[str],
) -> str | None:
    if node.level == 0:
        return node.module

    package = (
        source_module if source_module in package_modules else source_module.rpartition(".")[0]
    )
    package_parts = package.split(".") if package else []
    parent_hops = node.level - 1
    if parent_hops > len(package_parts):
        return None
    if parent_hops:
        package_parts = package_parts[:-parent_hops]
    if node.module:
        package_parts.extend(node.module.split("."))
    return ".".join(package_parts) or None


def _internal_target(candidate: str, modules: Mapping[str, Path]) -> str | None:
    if candidate in modules:
        return candidate
    return None
