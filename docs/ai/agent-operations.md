# Agent Operations Manual

## Machine-Facing Surface

当 agent 需要在本仓库执行常见技能操作时，优先按以下顺序读取：

- `README.md`
- `docs/ai/agent-operations.md`
- `docs/ai/openclaw.md`
- `docs/ai/publish.md`
- `docs/ai/pull.md`
- `catalog/ai-index.json`

如非故障排查，不应继续深入内部实现脚本。

## Goal

本手册的目标不是替代底层协议，而是让 agent 能先做出正确决策：

- 什么时候应该 `import`
- 什么时候应该 `publish`
- 什么时候应该 `pull`
- 什么时候只能做人工步骤
- 什么时候必须先停下来而不是继续猜测

将本文件视为**决策手册**；将 `docs/ai/publish.md` 与 `docs/ai/pull.md` 视为**严格执行协议**。

## Core Model

执行任何操作前，必须区分以下状态：

1. **Local prototype**：例如 `~/.openclaw/workspace/skills/<skill>`
2. **Registry source**：仓库内的 `skills/incubating/` 与 `skills/active/`
3. **Immutable release artifacts**：`catalog/distributions/...` 与 `catalog/provenance/...`
4. **Runtime install target**：例如 `~/.openclaw/skills`

不要把这些状态混为一谈。

尤其要记住：

- `skills/incubating/` 或 `skills/active/` 里的内容是**可编辑源码**，不是安装产物
- `catalog/distributions/...` 和 attestation/provenance 才是**可验证发布产物**
- 其他 agent 要安装稳定版本时，应从发布产物安装，而不是从源码目录复制

## Quick Decision Guide

当用户表达以下意图时，agent 应优先选择这些命令：

- **“创建一个新的 registry skill”** → `scripts/new-skill.sh`
- **“把 OpenClaw 本地技能纳入平台治理”** → `scripts/import-openclaw-skill.sh`
- **“检查这个 skill 是否合规”** → `scripts/check-skill.sh`
- **“准备评审 / 请求评审”** → `scripts/request-review.sh`
- **“记录 reviewer 决策”** → `scripts/approve-skill.sh`
- **“确认能否升到 active”** → `scripts/review-status.py --as-active --require-pass`
- **“发布稳定版本供其他 agent 安装”** → `scripts/publish-skill.sh`
- **“给本地 agent 安装稳定版本”** → `scripts/pull-skill.sh`
- **“查看已安装 skill 状态”** → `scripts/list-installed.sh`
- **“导出到 ClawHub 兼容目录”** → `scripts/export-openclaw-skill.sh`

若目标是**自主 agent 安装稳定版本**，默认优先 `pull-skill.sh`，不是 `install-skill.sh`。

## Canonical Workflows

### Workflow A: Create a new registry-native skill

适用场景：技能尚未存在于 OpenClaw 本地工作区，而是直接在 registry 中创建。

1. 脚手架新技能：

   ```bash
   scripts/new-skill.sh publisher/my-skill basic
   ```

2. 补全至少这些文件：

   - `skills/incubating/my-skill/SKILL.md`
   - `skills/incubating/my-skill/_meta.json`
   - `skills/incubating/my-skill/tests/smoke.md`
   - `skills/incubating/my-skill/CHANGELOG.md`

3. 校验 skill：

   ```bash
   scripts/check-skill.sh skills/incubating/my-skill
   ```

4. 请求并记录评审：

   ```bash
   scripts/request-review.sh my-skill --note "Ready for active"
   scripts/approve-skill.sh my-skill --reviewer reviewer-id --decision approved --note "Looks good"
   python3 scripts/review-status.py my-skill --as-active --require-pass
   ```

5. 发布稳定版本：

   ```bash
   scripts/publish-skill.sh publisher/my-skill
   ```

6. 将发布产生的仓库变更提交并推送到共享远端。

7. 其他 agent 更新仓库后，执行：

   ```bash
   scripts/pull-skill.sh publisher/my-skill ~/.openclaw/skills
   ```

### Workflow B: Import an existing OpenClaw prototype

适用场景：skill 已经存在于 OpenClaw 本地工作区，例如 `~/.openclaw/workspace/skills/my-skill`。

1. 导入到 registry：

   ```bash
   scripts/import-openclaw-skill.sh ~/.openclaw/workspace/skills/my-skill --owner lvxiaoer --publisher lvxiaoer
   ```

2. 校验导入结果：

   ```bash
   scripts/check-skill.sh skills/incubating/my-skill
   ```

3. 按 Workflow A 的 review → publish 流程继续。

4. 发布完成后，其他 agent 从发布产物安装：

   ```bash
   scripts/pull-skill.sh lvxiaoer/my-skill ~/.openclaw/skills
   ```

### Workflow C: Publish a version for other agents

适用场景：某个 agent 已经完成 skill 修改，希望其他 agent 能安装同一个稳定版本。

1. 如有版本变更，先更新版本号与变更日志：

   ```bash
   scripts/bump-skill-version.sh my-skill patch --note "Describe the change"
   ```

2. 运行校验：

   ```bash
   scripts/check-skill.sh skills/incubating/my-skill
   ```

   或：

   ```bash
   scripts/check-skill.sh skills/active/my-skill
   ```

3. 执行发布：

   ```bash
   scripts/publish-skill.sh publisher/my-skill
   ```

4. 确认以下结果存在：

   - `catalog/distributions/.../manifest.json`
   - `catalog/distributions/.../skill.tar.gz`
   - `catalog/provenance/<skill>-<version>.json`
   - 更新后的 `catalog/ai-index.json`

5. 提交并推送仓库变更；确保相关 release tag 已被推送。

6. 告知其他 agent 先更新仓库，再执行 `pull-skill.sh`。

### Workflow D: Install a published skill into another agent

适用场景：另一个 agent 需要安装某个稳定版本。

1. 先更新共享 registry 仓库。

   默认 `self` registry 是 `local-only`，因此不要假设 `scripts/sync-registry-source.sh self` 会替你从远端抓取更新；通常应先执行 `git pull`。

2. 如需先看计划，不修改目标目录：

   ```bash
   scripts/pull-skill.sh publisher/my-skill ~/.openclaw/skills --mode confirm
   ```

3. 执行安装：

   ```bash
   scripts/pull-skill.sh publisher/my-skill ~/.openclaw/skills
   ```

4. 如需固定到特定版本：

   ```bash
   scripts/pull-skill.sh publisher/my-skill ~/.openclaw/skills --version 1.2.3
   ```

5. 查看安装结果：

   ```bash
   scripts/list-installed.sh ~/.openclaw/skills
   ```

### Workflow E: Export a released skill for ClawHub

适用场景：要把已经完成 private release 的技能导出为 ClawHub 兼容目录。

1. 先确保该 skill 已经通过 `publish-skill.sh` 产生稳定发布物。

2. 导出：

   ```bash
   scripts/export-openclaw-skill.sh publisher/my-skill --version 1.2.3 --out /tmp/openclaw-export
   ```

3. 人工检查导出目录。

4. 如确实需要公开发布，再由人工执行：

   ```bash
   clawhub publish /tmp/openclaw-export/my-skill
   ```

agent 不得默认自动执行这一步。

## Confirm-First Rule

当存在以下任一情况时，优先使用 `--mode confirm`：

- 用户在问“会做什么”而不是明确要求立即修改
- 目标目录可能已有安装内容
- 当前 skill 名称或版本可能存在歧义
- 你不确定是否满足 review / release 前置条件
- 你需要先展示计划给上层 agent 或人类确认

对以下命令，`confirm` 模式都应保持无副作用：

- `scripts/import-openclaw-skill.sh`
- `scripts/publish-skill.sh`
- `scripts/pull-skill.sh`
- `scripts/export-openclaw-skill.sh`

## Hard Rules

- 不得从 `skills/incubating/` 或 `skills/active/` 直接安装到运行时目录
- 不得把“代码已合并”视为“已发布”
- 不得把“tag 已存在”视为“已发布”
- 不得在 attestation / manifest 校验失败后继续安装
- 不得把 `latest` 当作自动可推断概念；默认版本必须来自 `catalog/ai-index.json`
- 不得默认执行 `clawhub publish`
- 不得在 `confirm` 模式下修改仓库或目标目录
- 应优先使用 `publisher/skill` 这种 qualified name，避免歧义
- 在告诉其他 agent “可以安装了” 之前，必须先把发布结果同步到共享远端

## Failure Handling

遇到失败时，优先按以下方式处理：

- **`skill-not-found`**：改用 qualified name，或传入包含 `_meta.json` 的 skill 目录
- **`review-gate-failed`**：先补齐 reviewer 决策，再重新运行 `python3 scripts/review-status.py <skill> --as-active --require-pass`
- **`missing-ai-index` / `invalid-ai-index`**：运行 `scripts/build-catalog.sh`，并提交更新后的 `catalog/*.json`
- **`manifest-verification-failed`**：停止安装；先修复发布流程或重新发布
- **目标目录冲突**：先检查 `scripts/list-installed.sh` 输出，不要静默覆盖已有安装

## Minimal Command Reference

```bash
# create
scripts/new-skill.sh publisher/my-skill basic

# import local OpenClaw prototype
scripts/import-openclaw-skill.sh ~/.openclaw/workspace/skills/my-skill --owner NAME --publisher NAME

# validate
scripts/check-skill.sh skills/incubating/my-skill

# request + record review
scripts/request-review.sh my-skill --note "Ready for active"
scripts/approve-skill.sh my-skill --reviewer reviewer-id --decision approved --note "Looks good"
python3 scripts/review-status.py my-skill --as-active --require-pass

# publish immutable release
scripts/publish-skill.sh publisher/my-skill

# install for runtime agent
scripts/pull-skill.sh publisher/my-skill ~/.openclaw/skills

# inspect installed state
scripts/list-installed.sh ~/.openclaw/skills

# export after private release
scripts/export-openclaw-skill.sh publisher/my-skill --version 1.2.3 --out /tmp/openclaw-export
```

## When To Stop And Ask For Help

在以下情况下，agent 应停止继续猜测，并把阻塞点明确抛出：

- 目标 skill 名称冲突且 bare name 无法唯一解析
- 当前版本是否应该 bump 无法从上下文判断
- review policy 要求的 reviewer 身份无法满足
- 发布需要签名或 tag 权限，但当前环境没有相应凭据
- 用户要求“公开发布”，但导出与人工审核步骤尚未完成

## Summary

最重要的操作顺序只有一句话：

**prototype/import → validate → review/promotion → publish immutable release → commit/push → other agents pull/install**

如果你只记住一条规则，那就是：**给其他 agent 安装时，永远从已发布的不可变产物安装，不要直接从源码目录复制。**
