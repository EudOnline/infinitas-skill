---
name: federation-registry-ops
description: Use when Codex, Claude, or Claude Code needs to inspect registry source configuration, federation or mirror behavior, or audit and inventory export artifacts in infinitas-skill.
---

# Federation registry ops

## Overview

This skill covers registry operations that are broader than one skill install or release: federation rules, mirror behavior, source identity, and the generated audit or inventory exports.

Use it when the question is about why a registry source is or is not visible, why identity changed across registries, or why exported inventory and audit views disagree with expectations.

## Read First

- `docs/ops/federation-operations.md`
- `docs/reference/cli-reference.md`
- `docs/reference/multi-registry.md`
- `catalog/inventory-export.json`
- `catalog/audit-export.json`
- `config/registry-sources.json`

## Workflow

1. Confirm whether the issue is about registry source configuration, mirror state, federation mapping, or export artifacts.
2. Read the generated export or catalog artifact before inferring behavior from implementation code.
3. Check the configured registry source and trust policy in `config/registry-sources.json`.
4. Use search, inspect, and export artifacts to compare the expected source identity with the observed result.
5. Use the registry source and catalog CLI commands when generated surfaces need refresh.

## Command and Artifact Map

- `uv run infinitas discovery search`: confirm whether a skill is visible through generated discovery surfaces
- `uv run infinitas discovery inspect`: inspect the selected skill's source, trust, and provenance view
- `catalog/inventory-export.json`: current inventory and registry visibility view
- `catalog/audit-export.json`: release and provenance-oriented audit view
- `uv run infinitas registry sources check`: validate source configuration
- `uv run infinitas registry sources status`: inspect source refresh state
- `uv run infinitas registry sources mirror`: push the configured one-way mirror
- `uv run infinitas registry catalog build`: regenerate derived catalog artifacts

## Hard Rules

- Do not treat mirror visibility as authoritative source ownership
- Do not debug federation issues only from raw source folders when exports already show the disagreement
- Do not use this skill for simple install or release workflows
- Do not ignore trust level and source registry when comparing search and audit results

## Bundled Resources

- `tests/smoke.md` contains a realistic federation and audit debugging request
