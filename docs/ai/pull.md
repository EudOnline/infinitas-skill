# `pull-skill` Protocol

## Command

```bash
scripts/pull-skill.sh <qualified-name> <target-dir> [--version <semver>] [--registry <name>] [--mode auto|confirm]
```

## Inputs

- `qualified-name`: publisher-qualified name，或 AI index 中可唯一解析的技能名
- 当所选 registry 配置了 `federation.mode = "federated"` 时，`qualified-name` 可以是映射后的本地 publisher 名称；解析结果仍必须保留 upstream publisher 身份
- `target-dir`: 本地安装目标目录
- `--version <semver>`: 可选；未指定时使用 AI index 中声明的 `default_install_version`
- `--registry <name>`: 可选；从指定已配置 registry 的 `catalog/ai-index.json` 解析和安装技能
- 当 registry 是 `kind: "http"` 时，解析来自远程 hosted `ai-index.json`，而不是本地 clone
- `--mode auto|confirm`: 可选；默认值为 `auto`

## Preconditions

- 默认或指定 registry 的 `catalog/ai-index.json` 存在且有效
- 目标 skill 在 AI index 中可解析
- 所选版本在 AI index 中存在
- 所选版本必须具备 manifest、bundle digest 与 attestation 引用
- 安装策略必须为 `immutable-only`
- verified distribution manifests are the default consumer path; do not fall back to mutable working-tree folders for stable installs
- `mirror` registries 不参与默认解析；若请求的 namespace 只存在于 mirror 视图中，pull 必须失败并提示改用 authoritative source

## Ordered Execution Steps

1. 解析目标 registry，读取并校验对应的本地或 hosted `ai-index.json`
2. 若 registry 声明了 federation 规则，则先把请求 namespace 映射到允许的 upstream publisher，并记录映射前后的身份
3. 解析目标 skill 和目标版本
4. 若未显式指定版本，则读取 `default_install_version`
5. 校验 manifest 路径、bundle 路径、sha256 与 attestation 路径
6. 验证 manifest、bundle、attestation
7. 校验兼容性与运行前置条件
8. 在临时位置物化安装内容
9. 原子写入目标目录
10. 写入本地 lock / install manifest
11. 输出结构化 JSON 结果

## CI attestation and manifest policy

- distribution manifests now record `attestation_bundle.required_formats`
- consumers must use `python3 scripts/verify-distribution-manifest.py <manifest.json>` so install policy enforces `ssh`, `ci`, or `both`
- when `required_formats` includes `ci`, installation must fail if the CI attestation sidecar is missing or invalid
- pull and inspect flows should surface trust state from the verified distribution manifest, provenance bundle, and attestation policy before installing

## Stop Conditions

出现以下任一情况必须立即停止，并返回失败结果：

- AI index 不存在或无效
- skill 或版本在 AI index 中不存在
- 请求的 publisher 不在 registry 的 `allowed_publishers` 中，或只命中了 `mirror` registry
- 安装策略不是 `immutable-only`
- 缺少 manifest、bundle digest 或 attestation
- released manifest、bundle、或 attestation 文件路径存在于 AI index，但对应的 immutable artifact 实际缺失
- 任何校验失败
- 目标目录已存在不兼容安装且未显式允许覆盖
- 本地 lock / install manifest 写入失败

## Output JSON

Stable integration consumers should validate stdout JSON against:

- `schemas/pull-result.schema.json`

`confirm` 预览、实际安装结果、以及结构化失败结果都共用这份 schema，并通过 `state` 区分。

成功时至少包含：

```json
{
  "ok": true,
  "qualified_name": "publisher/my-skill",
  "requested_version": null,
  "resolved_version": "1.2.3",
  "target_dir": "/path/to/skills",
  "state": "installed",
  "lockfile_path": "/path/to/skills/.infinitas-skill-install-manifest.json",
  "installed_files_manifest": "/path/to/skills/.infinitas-skill-install-manifest.json",
  "next_step": "sync-or-use"
}
```

`confirm` 模式预览至少包含：

```json
{
  "ok": true,
  "qualified_name": "publisher/my-skill",
  "requested_version": null,
  "resolved_version": "1.2.3",
  "registry_name": "self",
  "registry_root": "/path/to/repo",
  "ai_index_path": "/path/to/repo/catalog/ai-index.json",
  "target_dir": "/path/to/skills",
  "state": "planned",
  "manifest_path": "catalog/distributions/.../manifest.json",
  "bundle_path": "catalog/distributions/.../bundle.tar.gz",
  "bundle_sha256": "...",
  "attestation_path": "catalog/provenance/my-skill-1.2.3.json",
  "registry_kind": "local",
  "install_name": "publisher/my-skill",
  "install_command": [
    "scripts/install-skill.sh",
    "publisher/my-skill",
    "/path/to/skills",
    "--version",
    "1.2.3"
  ],
  "next_step": "confirm-or-run",
  "explanation": {
    "selection_reason": "...",
    "registry_used": "self",
    "confirmation_required": false,
    "version_reason": "...",
    "policy_reasons": ["..."],
    "next_actions": ["..."]
  }
}
```

失败时至少包含：

```json
{
  "ok": false,
  "state": "failed",
  "failed_at_step": "verified_manifest",
  "error_code": "manifest-verification-failed",
  "message": "...",
  "suggested_action": "...",
  "explanation": {
    "selection_reason": "...",
    "registry_used": "self",
    "confirmation_required": false,
    "version_reason": "...",
    "policy_reasons": ["..."],
    "next_actions": ["..."]
  }
}
```

Important wrapper failures to handle explicitly:

- `ambiguous-skill-name`: stop and ask for the exact `qualified_name`; do not guess from a short name
- `missing-distribution-fields`: stop and tell the publisher to republish the immutable release metadata
- `missing-distribution-file`: stop and tell the publisher to rebuild or republish the immutable artifacts

When `error_code` is `missing-distribution-fields` or `missing-distribution-file`, never fall back to `skills/active`, `skills/incubating`, or any mutable source folder. The only valid repair path is to rebuild or republish the immutable release artifacts and regenerate the catalog if needed.

## OpenClaw Context

- 推荐目标目录是 `~/.openclaw/skills` 或 `~/.openclaw/workspace/skills`
- `pull-skill.sh` 只从 immutable release artifacts 安装，不从本地原型目录复制
- 对 hosted registry，`pull-skill.sh` 会下载 manifest / bundle / provenance，再进行同样的不可变校验
- 对 federated registry，pull 输出应同时暴露 mapped publisher identity 与 upstream publisher identity，避免把 namespace 映射误解成来源变更
- 即使指定了 `--registry`，也只允许读取该 registry 已发布的 immutable 索引与产物
- 面向 portal / compliance 的聚合读取应优先消费 `catalog/inventory-export.json` 与 `catalog/audit-export.json`，而不是把 `pull-skill` 的安装输出当作长期稳定集成契约
- 若 pull 结果与 inventory / audit exports 或 registry policy 看起来冲突，先参考 [docs/federation-operations.md](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules/docs/federation-operations.md) 中的恢复顺序，再决定是否调整 registry policy
- 若 AI 看到的是 OpenClaw 本地原型目录，应先走 `scripts/import-openclaw-skill.sh`，而不是直接安装
- 如果需要先看 trust state、compatibility、dependency summary 或 provenance，优先运行 `scripts/inspect-skill.sh`

## Forbidden Assumptions

- 不得从 `skills/active` 或 `skills/incubating` 直接安装
- 不得把 `latest` 当作可推断概念；默认版本必须来自 AI index
- 不得在 attestation 校验失败时继续安装
- 不得在 `confirm` 模式下修改目标目录
- 不得静默覆盖已有安装
- 若已安装副本被后续 workflow 判定为 `drifted`，优先调用 `scripts/repair-installed-skill.sh`，不要把 upgrade / rollback 当作隐式修复

## Mode Rules

- 默认模式是 `auto`
- `auto` 模式必须从不可变发布物完成完整安装
- `confirm` 模式必须只输出执行计划，不得修改目标目录

## Installed Integrity Follow-up

安装完成后，如需确认本地 runtime copy 仍与已验证发布物一致：

```bash
python3 scripts/verify-installed-skill.py <name> <target-dir> --json
```

若状态为 `drifted`，优先执行：

```bash
scripts/repair-installed-skill.sh <name> <target-dir>
```

而不是把 upgrade、rollback、或手工复制当作默认修复路径。
