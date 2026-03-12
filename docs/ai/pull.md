# `pull-skill` Protocol

## Command

```bash
scripts/pull-skill.sh <qualified-name> <target-dir> [--version <semver>] [--registry <name>] [--mode auto|confirm]
```

## Inputs

- `qualified-name`: publisher-qualified name，或 AI index 中可唯一解析的技能名
- `target-dir`: 本地安装目标目录
- `--version <semver>`: 可选；未指定时使用 AI index 中声明的 `default_install_version`
- `--registry <name>`: 可选；从指定已配置 registry 的 `catalog/ai-index.json` 解析和安装技能
- `--mode auto|confirm`: 可选；默认值为 `auto`

## Preconditions

- 默认或指定 registry 的 `catalog/ai-index.json` 存在且有效
- 目标 skill 在 AI index 中可解析
- 所选版本在 AI index 中存在
- 所选版本必须具备 manifest、bundle digest 与 attestation 引用
- 安装策略必须为 `immutable-only`

## Ordered Execution Steps

1. 解析目标 registry，读取并校验对应的 `catalog/ai-index.json`
2. 解析目标 skill 和目标版本
3. 若未显式指定版本，则读取 `default_install_version`
4. 校验 manifest 路径、bundle 路径、sha256 与 attestation 路径
5. 验证 manifest、bundle、attestation
6. 校验兼容性与运行前置条件
7. 在临时位置物化安装内容
8. 原子写入目标目录
9. 写入本地 lock / install manifest
10. 输出结构化 JSON 结果

## Stop Conditions

出现以下任一情况必须立即停止，并返回失败结果：

- AI index 不存在或无效
- skill 或版本在 AI index 中不存在
- 安装策略不是 `immutable-only`
- 缺少 manifest、bundle digest 或 attestation
- 任何校验失败
- 目标目录已存在不兼容安装且未显式允许覆盖
- 本地 lock / install manifest 写入失败

## Output JSON

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

失败时至少包含：

```json
{
  "ok": false,
  "state": "failed",
  "failed_at_step": "verified_manifest",
  "error_code": "manifest-verification-failed",
  "message": "...",
  "suggested_action": "..."
}
```

## OpenClaw Context

- 推荐目标目录是 `~/.openclaw/skills` 或 `~/.openclaw/workspace/skills`
- `pull-skill.sh` 只从 immutable release artifacts 安装，不从本地原型目录复制
- 即使指定了 `--registry`，也只允许读取该 registry 已发布的 immutable 索引与产物
- 若 AI 看到的是 OpenClaw 本地原型目录，应先走 `scripts/import-openclaw-skill.sh`，而不是直接安装

## Forbidden Assumptions

- 不得从 `skills/active` 或 `skills/incubating` 直接安装
- 不得把 `latest` 当作可推断概念；默认版本必须来自 AI index
- 不得在 attestation 校验失败时继续安装
- 不得在 `confirm` 模式下修改目标目录
- 不得静默覆盖已有安装

## Mode Rules

- 默认模式是 `auto`
- `auto` 模式必须从不可变发布物完成完整安装
- `confirm` 模式必须只输出执行计划，不得修改目标目录
