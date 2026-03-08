# Codebase Conventions

## 总体风格

这个仓库是一个**脚本驱动、文档先行、配置可审计**的私有 skill registry，而不是传统的 Python/Node 应用。日常约定主要落在 `README.md`、`docs/*.md`、`config/*.json`、`policy/*.json`、`schemas/*.json` 和 `scripts/*`，而不是包管理器、测试框架或应用源码目录。

- 代码组织围绕 skill 生命周期：`skills/incubating/` → `skills/active/` → `skills/archived/`。
- `templates/` 提供基线结构；当前仓库里实际存在的 skill 目录只有 3 个模板，`skills/*` 目前为空。
- `catalog/*.json` 是生成产物，不是手写源文件。
- 文档不仅解释流程，也充当操作约定与人工检查清单。

## 目录与职责约定

- `README.md`：入口文档，概述仓库目标、目录布局和推荐命令。
- `docs/*.md`：人类可读的规则、流程、发布策略、信任模型与 checklist。
- `config/*.json`：运行时/集成配置，例如 registry 来源与签名设置。
- `policy/*.json`：机器可读策略，目前主要是 promotion policy。
- `schemas/*.json`：JSON Schema 合同；当前 `_meta.json` 的 schema 使用 draft 2020-12。
- `scripts/`：单文件 CLI 工具；shell 做编排，Python 做结构化 JSON/校验逻辑。
- `templates/*`：脚手架模板，定义仓库默认 skill 形状。
- `catalog/*.json`：由 `scripts/build-catalog.sh` 生成的索引视图。
- `catalog/provenance/`：由 release 流程生成的 provenance 记录及签名侧车文件。

## Skill 与文档约定

仓库把“一个 skill”视为一个独立目录，通常应包含以下形状：

```text
skill-name/
├─ SKILL.md
├─ _meta.json
├─ CHANGELOG.md
├─ scripts/
├─ references/
├─ assets/
└─ tests/
   └─ smoke.md
```

核心约定如下：

- 目录名使用小写加连字符；`scripts/new-skill.sh` 会把输入 slugify 成这种格式。
- `SKILL.md` 顶部 frontmatter 至少包含 `name` 和 `description`。
- `_meta.json.name`、`SKILL.md` 的 `name:`、目录名应保持一致；`archived` 快照目录是例外，目录名可以带版本和时间戳。
- 长文参考资料放进 `references/`，避免把 `SKILL.md` 写成大而全的手册。
- 可执行辅助逻辑放进 `scripts/`；输出模板或资源放进 `assets/`。
- `tests/smoke.md` 是“最低可行人工验证案例”，当前不是自动执行脚本。
- `CHANGELOG.md` 使用 semver 对应的版本块，仓库文档示例格式是 `## x.y.z - YYYY-MM-DD`。

Markdown 写作也有明显习惯：

- 文件名统一使用小写连字符风格，例如 `release-checklist.md`、`promotion-policy.md`。
- 文档偏“操作手册”风格，常见结构是背景 → 规则 → 命令示例 → checklist。
- 命令示例优先用 fenced code block（`bash`/`json`/`text`）。
- 文档与脚本相互印证：`docs/` 解释 why，`scripts/` 执行 how。

## Shell 脚本习惯

shell 脚本是这类仓库中的编排层，风格高度一致：

- 统一使用 `#!/usr/bin/env bash`。
- 绝大多数 shell 脚本一开始就启用 `set -euo pipefail`。
- 常见根目录定位写法：

```bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
```

- 参数解析偏向简单 `while [[ $# -gt 0 ]]; do case ... esac`，复杂度保持在单文件可读范围内。
- 遇到错误时直接 `echo ... >&2` 并 `exit 1`，成功时打印简短状态，如 `OK:`、`created:`、`promoted:`、`installed:`。
- 会在 destructive 操作前做显式存在性检查，例如覆盖前先 `[[ -e ... ]]` 或要求 `--force`。
- 不依赖 `jq`；凡是涉及 JSON 读写、字段提取、格式化输出，普遍内嵌小段 Python heredoc 完成。

当前 shell 约定不是“纯 shell”，而是“shell 负责流程，Python 负责结构化数据”。典型例子：

- `scripts/check-all.sh` 用 shell 串联校验链路。
- `scripts/promote-skill.sh` / `scripts/release-skill.sh` 用内嵌 Python 读取 `_meta.json`、提取 changelog、改写状态字段。
- `scripts/build-catalog.sh` 直接在 shell 中嵌入较长 Python 生成 catalog。

## Python 脚本习惯

Python 是仓库里真正的“数据与规则层”，也有统一写法：

- 统一使用 `#!/usr/bin/env python3`。
- 只依赖标准库；仓库里没有 `pyproject.toml`、`requirements.txt`、`setup.cfg`、`pytest` 配置等打包/依赖声明。
- 常见根目录定位写法：

```python
ROOT = Path(__file__).resolve().parent.parent
```

- 以 `Path` + `json` 为核心，不引入第三方解析器。
- JSON 读取多用 `json.loads(path.read_text(encoding='utf-8'))`。
- JSON 写回统一倾向 `json.dump(..., ensure_ascii=False, indent=2)`，并手动补一个末尾换行。
- 校验脚本偏向小函数 + 显式 `errors += 1` 计数，不使用复杂框架。
- CLI 退出以 `raise SystemExit(1)` 或 `return 1` 为主；输出格式统一为 `FAIL:` / `WARN:` / `OK:`。
- 正则、允许值集合等常量倾向放在文件顶部，例如 `NAME_RE`、`SEMVER_RE`、`ALLOWED_STATUS`。

这意味着仓库更重视**可移植性与零依赖**，而不是复用型 Python 包设计。

## JSON / Schema / 配置习惯

仓库对 JSON 的使用非常一致：

- 普遍使用 2 空格缩进。
- UTF-8 编码，写回时保留 Unicode（`ensure_ascii=False`）。
- 配置与策略优先机器可读化，再由文档补充语义。
- `_meta.json` 是每个 skill 的核心合同；schema 定义在 `schemas/skill-meta.schema.json`。
- `config/registry-sources.json` 是 registry 来源真相源。
- `policy/promotion-policy.json` 是 active skill 的 promotion gate 真相源。
- `config/signing.json` 提供 provenance SSH 签名相关默认值。

值得注意的细节：

- schema 允许 `additionalProperties: true`，说明作者希望在不频繁破坏兼容性的前提下扩展元数据。
- 但 CI/本地校验并不直接跑 `jsonschema`；实际 enforcement 来自手写 Python 校验器。
- 因此仓库实际遵循的是“JSON Schema + Python 校验脚本”双轨模型，二者需要人工保持同步。

## 生成文件与可重复性约定

`catalog/catalog.json`、`catalog/active.json`、`catalog/compatibility.json`、`catalog/registries.json` 都由 `scripts/build-catalog.sh` 生成。

生成约定包括：

- 文件带 `generated_at` 时间戳。
- 生成脚本在写入前会做“归一化比较”；只有非时间戳内容变化时才会落盘。
- `scripts/check-all.sh` 会在校验末尾重新跑一次 build，并忽略 `generated_at` 比较前后内容，借此防止 catalog 漏提交。

这类生成物被当作**可提交、可审阅的派生产物**，而不是纯本地缓存。

## 发布与验证链路约定

几个关键流程都把“先校验，再变更”作为默认约束：

- GitHub Actions 只有一个 `validate-registry` 工作流，入口是 `scripts/check-all.sh`。
- `scripts/promote-skill.sh` 在移动目录前先跑 `check-skill.sh`、review_state 检查、promotion policy、integrity check，再 `build-catalog.sh`。
- `scripts/release-skill.sh` 在打印 release notes、打 tag、写 provenance 之前，会先跑 `check-skill.sh` 和 `check-all.sh`。
- provenance 产物默认落到 `catalog/provenance/`，HMAC 签名依赖环境变量，SSH 签名依赖 `config/signing.json` 与 `ssh-keygen -Y`。

## 当前仓库状态下的重要现实

截至当前快照，这些约定更多由**模板、文档和脚本**体现，而不是由真实 skill 数据沉淀出来：

- `skills/incubating/`、`skills/active/`、`skills/archived/` 都为空。
- 现有自动校验主要覆盖 3 个模板目录与若干 JSON 配置/生成物。
- 因此这里的 conventions 已经很明确，但更多是“治理框架”而不是“生产样本归纳”。

这对后续工作有两个直接影响：

- 新增真实 skill 时，应以 `templates/*`、`docs/conventions.md`、`schemas/skill-meta.schema.json` 和 `scripts/check-skill.sh` 共同作为落地规范。
- 如果后续元数据字段或发布流程演进，需要同步更新文档、schema、校验脚本和 catalog 生成逻辑，避免约定漂移。
