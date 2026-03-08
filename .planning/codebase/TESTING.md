# Testing and Validation

## 总体判断

这个仓库当前的“测试”更准确地说是**registry validation**，而不是传统意义上的单元测试/集成测试体系。

- 自动化重点放在元数据正确性、目录结构一致性、policy 合规性、依赖/冲突引用完整性，以及生成 catalog 是否与源码一致。
- 仓库里没有 `pytest`、`unittest`、`tox`、`nox`、coverage、lint/format 配置。
- 唯一看到的 `tests/` 文件是 3 个模板里的 `tests/smoke.md`，它们是人工 smoke 场景说明，不是自动执行测试。

换句话说：**当前仓库是“脚本自校验 + CI 触发”模式，不是“源码 + 测试套件”模式。**

## GitHub Actions 入口

CI 只有一个工作流：`.github/workflows/validate.yml`。

- 触发条件：`push` 到 `main`，以及所有 `pull_request`。
- 运行环境：`ubuntu-latest`。
- 依赖准备：仅安装 Python 3.11。
- 实际执行：`scripts/check-all.sh`。

这说明 GitHub Actions 只是把本地总入口脚本搬到 CI 上，并没有额外的矩阵、缓存、lint、release、artifact、nightly 或 end-to-end job。

## `scripts/check-*` 检查职责

### `scripts/check-all.sh`

这是总编排入口，负责把若干局部校验串起来：

1. `scripts/check-registry-sources.py`
2. `scripts/validate-registry.py`
3. `scripts/check-registry-integrity.py`
4. `scripts/check-promotion-policy.py`
5. 对 `skills/*/*` 下每个含 `_meta.json` 的目录执行 `scripts/check-skill.sh`
6. 重新运行 `scripts/build-catalog.sh`
7. 归一化比较 4 个 catalog 文件，忽略 `generated_at`，确保派生文件没有漂移

最后一步很关键：它把“是否记得提交重新生成后的 catalog”纳入了校验链，而不仅仅是检查原始元数据。

### `scripts/check-registry-sources.py`

检查 `config/registry-sources.json`：

- `registries` 必须是非空数组。
- 每个 registry 必须是对象。
- `name` 必须唯一且非空。
- `kind` 目前只允许 `git` 或 `local`。
- `trust` 必须是非空字符串。
- `git` 类型必须提供 `url`。

这是 registry 级配置合法性检查。

### `scripts/validate-registry.py`

这是 `_meta.json` 结构与字段语义的主校验器，会遍历：

- `skills/incubating`
- `skills/active`
- `skills/archived`
- `templates`

检查内容包括：

- 目录必须同时存在 `SKILL.md` 和 `_meta.json`
- `name` 命名规则
- semver 风格 `version`
- `status` 与父目录一致
- `summary` / `owner` 非空
- `review_state` / `risk_level` 枚举值
- `maintainers` / `tags` / `agent_compatible` / `depends_on` / `conflicts_with` 类型
- `derived_from` / `replaces` 可空字符串约束
- `requires` / `entrypoints` / `tests` / `distribution` 对象约束
- `tests.smoke` 文件存在

虽然仓库提供了 `schemas/skill-meta.schema.json`，但这里并不直接使用 `jsonschema`；实际 CI 依赖的是这个手写 Python 校验器。

### `scripts/check-registry-integrity.py`

这个脚本检查跨 skill 引用关系，而不是单个文件格式：

- 校验 `depends_on` / `conflicts_with` 引用格式是否合法
- 阻止 skill 引用自己
- 要求 `active` skill 的依赖必须能在 `active` 或 `archived` 中解析到
- 对活跃且 installable 的冲突对给出 `WARN`
- 同样会把 `templates` 纳入扫描集合

它提供的是**图完整性**而不是语法完整性。

### `scripts/check-promotion-policy.py`

这个脚本把 `policy/promotion-policy.json` 转成可执行 gate。

- 默认只对 `active` skill 生效。
- `--as-active` 会把指定目录按 active 规则预检；`scripts/promote-skill.sh` 正是这样调用的。
- 会检查 `review_state`、`CHANGELOG.md`、smoke test、owner、`reviews.json`、最少审批数。
- 对高风险 active skill 还会追加 `maintainers` 数量与 `requires` block 约束。

这是 promotion 环节最接近“策略测试”的脚本。

### `scripts/check-skill.sh`

这是单 skill 的综合校验器，但它**不在 `validate-registry.py` 里复用**，而是独立存在。

它会检查：

- `SKILL.md`、`_meta.json`、`CHANGELOG.md` 是否存在（模板目录免 `CHANGELOG.md`）
- `SKILL.md` frontmatter 中 `name` / `description`
- `SKILL.md` 与目录名、`_meta.json.name` 是否一致
- `_meta.json` 基础字段、枚举值、semver 风格
- `tests.smoke` 文件存在
- 基于正则的 secrets 扫描

这个脚本有两点很重要：

- 它是唯一显式做 secrets 扫描的检查。
- 它校验 `SKILL.md` frontmatter，而 `validate-registry.py` 不检查 `description`。

### `scripts/check-install-target.py`

这是安装/同步场景的专用校验器，不属于当前 CI 主链。

- 读取目标目录的 `.infinitas-skill-install-manifest.json`，或回退扫描目标目录里的已安装 skill
- 检查 `depends_on` 是否都已安装
- 检查锁定版本与已安装版本是否匹配
- 检查 `conflicts_with` 是否与已安装 skill 冲突

`scripts/install-skill.sh` 和 `scripts/sync-skill.sh` 都会调用它，但 `.github/workflows/validate.yml` 和 `scripts/check-all.sh` 不会调用它。

## 发布 / promotion / 安装链路里的隐式测试

除了 `check-all.sh` 这条显式主链，仓库还有几条“操作前先校验”的隐式验证路径。

### Promotion 链路

`scripts/promote-skill.sh` 的 gate 顺序是：

1. `check-skill.sh`
2. 内嵌 Python 检查 `review_state == approved`
3. `check-promotion-policy.py --as-active`
4. `check-registry-integrity.py`
5. 若覆盖 active skill，则先 `snapshot-active-skill.sh`
6. 移动目录并把 `_meta.json.status` 改成 `active`
7. `build-catalog.sh`

这条链会阻止未审查、依赖不完整或 policy 不满足的 skill 被 promote。

### Release 链路

`scripts/release-skill.sh` 在任何 tag / provenance / GitHub release 动作前，会先：

1. 解析 skill 目录
2. `check-skill.sh`
3. `check-all.sh`
4. 确认目标 skill 当前 `status == active`
5. 从 `CHANGELOG.md` 中提取与当前 version 对应的 release notes

后续可选动作包括：

- 创建或签名 git tag
- `git push origin <tag>`
- 生成 provenance JSON
- HMAC 签名并立即 verify
- SSH 签名或 SSH verify
- `gh release create`

也就是说，release 工具本身自带“发布前全仓校验”语义。

### 安装 / 同步链路

`scripts/install-skill.sh` / `scripts/sync-skill.sh` 也会嵌入检查：

- 先通过 `resolve-skill-source.py` 解析来源
- 对源 skill 跑 `check-skill.sh`
- 对目标目录跑 `check-install-target.py`
- 成功后更新 `.infinitas-skill-install-manifest.json`

这些检查属于运行时安全网，但目前不在 CI 主链里。

## 当前覆盖现状

基于当前仓库快照，覆盖现状相当明确：

- 我实际运行了 `scripts/check-all.sh`，当前结果为通过。
- 本次运行只验证了 **1 个 registry source** 与 **3 个 skill 目录**。
- 这 **3 个 skill 目录全部来自 `templates/`**，因为 `skills/incubating/`、`skills/active/`、`skills/archived/` 当前都是空的。
- 仓库里没有 Python 测试文件，也没有自动化测试目录；唯一的 3 个 `tests/smoke.md` 也都在模板下。
- CI 当前覆盖的是“模板与治理框架是否自洽”，不是“真实 active/incubating skill 在生命周期里是否稳定”。

还有一个容易忽略但很关键的细节：

- `validate-registry.py` 和 `check-registry-integrity.py` 会扫 `templates/`。
- 但 `check-all.sh` 中逐个执行 `check-skill.sh` 的 `find` 只扫 `skills/*/*`，**不会扫 `templates/`**。

这意味着当前 CI 虽然验证了模板的 `_meta.json` 结构与图关系，但**并没有对模板运行 `check-skill.sh` 的 frontmatter 校验和 secrets 扫描**。

## 主要缺口

### 1. 没有传统自动化测试套件

- 没有单元测试
- 没有集成测试
- 没有 end-to-end workflow 测试
- 没有覆盖率指标

### 2. 安装/发布路径没有被 CI 真正执行

以下关键脚本不在 GitHub Actions 主链中：

- `install-skill.sh`
- `sync-skill.sh`
- `promote-skill.sh`
- `snapshot-active-skill.sh`
- `release-skill.sh`
- provenance 签名/验签脚本

所以依赖安装、版本锁、manifest 历史、snapshot、tag、GitHub release、签名与验签更多靠脚本内部保护，而不是专门测试验证。

### 3. 真正的 skill 生命周期还没有被样本验证

当前 `skills/*` 为空，导致：

- 没有真实 `incubating` → `active` → `archived` 案例
- 没有真实 `reviews.json` 审批样本
- 没有真实依赖/冲突图
- 没有真实 install manifest 演化样本

因此很多规则目前只是“定义好了”，尚未通过仓库内真实数据长期磨合。

### 4. Schema 与实现存在双维护风险

- `schemas/skill-meta.schema.json` 定义合同
- `validate-registry.py` / `check-skill.sh` 以手写逻辑重复实现合同

这种设计避免了外部依赖，但会带来 schema 漂移风险；一旦字段演进，必须同步修改 schema、脚本与文档。

### 5. 缺少 lint / static analysis 层

仓库没有发现以下常见质量闸门：

- `shellcheck` / `shfmt`
- `ruff` / `black` / `mypy`
- `actionlint` / `yamllint`
- JSON Schema 自动验证工具链

当前质量门主要依赖作者手写脚本，而非通用静态分析器。

## 结论

这个仓库已经有一条清晰、可运行的 validation spine：

- CI 入口简单
- 本地与 CI 共用 `check-all.sh`
- promotion / release / install 路径都带内建 gate
- catalog 派生物具备一致性检查

但它的覆盖仍然偏“治理规则验证”，而不是“功能行为测试”。当前最大缺口不是某个脚本完全没校验，而是：

- 缺少真实 skill 样本驱动的验证数据
- 缺少对 install / promote / release / provenance 流程的自动化回归测试
- 缺少把 `check-skill.sh` 覆盖到模板或 fixture 的 CI 步骤

如果后续需要提升可靠性，优先级最高的补强点会是：

1. 加入至少一个真实 fixture skill 覆盖 active/incubating/archived 路径
2. 让 `check-skill.sh` 也覆盖模板或专用 fixture
3. 为 install/promote/release/provenance 增加脚本级集成测试
4. 为 shell/Python/YAML 增加通用 lint
