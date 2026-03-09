# `publish-skill` Protocol

## Command

```bash
scripts/publish-skill.sh <skill> [--version <semver>] [--mode auto|confirm]
```

## Inputs

- `skill`: skill 名称、qualified name，或可解析到 `_meta.json` 的 skill 目录
- `--version <semver>`: 可选；仅用于断言当前待发布版本，不负责自动 bump 版本
- `--mode auto|confirm`: 可选；默认值为 `auto`

## Preconditions

- 目标 skill 可以被仓库解析
- 目标 skill 通过 `scripts/check-skill.sh`
- 目标 skill 满足发布前 review / promotion gate
- 目标 skill 必须最终以不可变发布物形式发布
- 运行环境必须允许执行现有 release、tag、catalog 相关脚本

## Ordered Execution Steps

1. 解析目标 skill
2. 读取 `_meta.json` 并校验可选 `--version`
3. 运行 skill 校验与发布前校验
4. 若目标为 incubating skill，则先验证 active review gate，再执行 promotion
5. 创建或验证稳定发布 tag
6. 生成 bundle、manifest、provenance / attestation
7. 验证发布物完整性
8. 更新 catalog 与 AI index
9. 输出结构化 JSON 结果

## Stop Conditions

出现以下任一情况必须立即停止，并返回失败结果：

- skill 无法解析
- `check-skill.sh` 或发布前检查失败
- review gate 不通过
- 缺少 manifest
- 缺少 attestation / provenance
- 生成的发布物验证失败
- catalog 或 AI index 无法更新

## Output JSON

成功时至少包含：

```json
{
  "ok": true,
  "skill": "my-skill",
  "qualified_name": "publisher/my-skill",
  "version": "1.2.3",
  "state": "published",
  "manifest_path": "catalog/distributions/.../manifest.json",
  "bundle_path": "catalog/distributions/.../bundle.tar.gz",
  "bundle_sha256": "...",
  "attestation_path": "catalog/provenance/my-skill-1.2.3.json",
  "published_at": "2026-03-09T00:00:00Z",
  "next_step": "pull-skill"
}
```

失败时至少包含：

```json
{
  "ok": false,
  "state": "failed",
  "failed_at_step": "reviewed",
  "error_code": "review-gate-failed",
  "message": "...",
  "suggested_action": "..."
}
```

## Forbidden Assumptions

- 不得把“代码已合并”视为“已发布”
- 不得把“已生成 tag”视为“已发布”
- 不得在缺少 manifest 或 attestation 时宣布发布成功
- 不得在 `confirm` 模式下修改仓库、tag、catalog 或发布物
- 不得从 `skills/active` 或 `skills/incubating` 直接暴露安装语义

## Mode Rules

- 默认模式是 `auto`
- `auto` 模式可以执行完整发布链路
- `confirm` 模式必须只输出执行计划，不得产生任何副作用
