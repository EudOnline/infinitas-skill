# OpenClaw / ClawHub Bridge Protocol

## Machine-Facing Surface

当 AI 需要理解本仓库与 OpenClaw / ClawHub 的关系时，只应优先读取以下文件：

- `README.md`
- `docs/ai/agent-operations.md`
- `docs/ai/openclaw.md`
- `docs/ai/publish.md`
- `docs/ai/pull.md`
- `catalog/ai-index.json`

如非故障排查，不应继续深入内部实现脚本。

## Core Model

本仓库是**私有技能注册表**，不是 OpenClaw 运行时目录本身。

必须区分 4 个状态：

1. **OpenClaw 本地原型**：例如 `~/.openclaw/workspace/skills/<skill>`
2. **Registry source**：`skills/incubating/` 与 `skills/active/`
3. **Immutable release artifacts**：`catalog/distributions/...` 与 provenance / attestation
4. **Runtime install target**：例如 `~/.openclaw/skills` 或 `~/.openclaw/workspace/skills`

AI 不得把这 4 个状态混为一谈。

## Supported Commands

### Import local OpenClaw skill into the registry

```bash
scripts/import-openclaw-skill.sh <source-dir-or-SKILL.md> [--owner NAME] [--publisher NAME] [--mode auto|confirm] [--force]
```

用途：把 OpenClaw 本地技能导入为仓库内的 incubating skill，并补齐 `_meta.json`、`reviews.json`、`tests/smoke.md`。

### Publish registry skill into immutable release artifacts

```bash
scripts/publish-skill.sh <skill> [--version <semver>] [--mode auto|confirm]
```

用途：把 registry 中的 skill 发布为可验证的不可变 release 产物。

### Pull released skill into an OpenClaw runtime directory

```bash
scripts/pull-skill.sh <qualified-name-or-name> <target-dir> [--version <semver>] [--mode auto|confirm]
```

用途：只从已发布的不可变产物安装到 OpenClaw 本地目录。

### Export a released skill into an OpenClaw / ClawHub-compatible folder

```bash
scripts/export-openclaw-skill.sh <qualified-name-or-name> --out DIR [--version <semver>] [--mode auto|confirm] [--force]
```

用途：把一个已发布版本导出成独立目录，经过规范化渲染和 OpenClaw 兼容性检查后，供人工审查或手动 `clawhub publish`。

## Canonical Workflows

### Private default workflow

1. 在 OpenClaw 本地工作区原型开发 skill
2. 运行 `scripts/import-openclaw-skill.sh ...`
3. 在仓库中完成 review / promotion / release
4. 运行 `scripts/publish-skill.sh ...`
5. 运行 `scripts/pull-skill.sh ... ~/.openclaw/skills`

### Public optional workflow

1. 先完成 private release
2. 运行 `scripts/export-openclaw-skill.sh ... --out <dir>`
3. 人工确认导出目录内容
4. 人工执行 `clawhub publish <export-dir>`

**默认不是 public publish。**

## Export validation

`export-openclaw-skill.sh` 现在会返回：

- `public_ready`: 当前导出目录是否满足公开发布约束
- `validation_errors`: 若不满足，列出阻止公开发布的原因

这意味着：

- 导出成功 ≠ 可以直接公开发布
- `public_ready: true` 才表示导出内容通过了当前公开发布门禁
- 即使 `public_ready: false`，仍可用于人工审查或私有运行时场景

## Hard Rules for AI

- 不得直接从 `skills/incubating/` 或 `skills/active/` 执行安装
- 不得把 OpenClaw 本地工作区目录当作“已发布版本”
- 不得默认执行 `clawhub publish`
- `confirm` 模式必须保持无副作用
- 安装默认版本必须来自 `catalog/ai-index.json`

## How to Decide

- 想把 OpenClaw 新技能纳入治理：用 `import-openclaw-skill.sh`
- 想给 OpenClaw 运行时装稳定版本：用 `pull-skill.sh`
- 想把私有 release 导出给 ClawHub：用 `export-openclaw-skill.sh`
- 想生成新的稳定 release：用 `publish-skill.sh`
