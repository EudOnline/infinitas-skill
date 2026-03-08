# 技术栈

## 定位
- 这是一个以 Git 仓库为中心的私有 skill registry / skill ops 工具仓库，不是长驻服务或前后端应用；核心对象是 `skills/`、`templates/`、`catalog/` 与配套治理脚本，见 `README.md`、`docs/conventions.md`。
- 当前仓库没有实际 skill 内容；`catalog/catalog.json`、`catalog/active.json`、`catalog/compatibility.json` 均为 0 项，说明现阶段重点是 registry 基础设施而非业务技能包。

## 核心实现栈
- Shell 编排：主入口基本都在 `scripts/*.sh`，以 `bash` 实现脚手架、校验、推广、安装、同步、快照、发布等流程，例如 `scripts/new-skill.sh`、`scripts/check-all.sh`、`scripts/promote-skill.sh`、`scripts/release-skill.sh`。
- Python 工具：辅助逻辑集中在 `scripts/*.py`，统一使用 `python3` + 标准库；可见模块包括 `json`、`pathlib`、`subprocess`、`argparse`、`hashlib`、`hmac`，仓库内未见 `pyproject.toml`、`requirements*.txt`。
- 内容格式：运行面向人的内容是 Markdown（`skills/**/SKILL.md`、`templates/**/SKILL.md`、`CHANGELOG.md`、`tests/smoke.md`、`docs/*.md`）；机器面向的配置与索引是 JSON（`_meta.json`、`catalog/*.json`、`config/*.json`、`policy/*.json`、`schemas/*.json`）。
- 源数据层：Git 既是版本控制层，也是 registry source / release / lineage / snapshot 的底层依赖；路径证据见 `scripts/release-skill-tag.sh`、`scripts/generate-provenance.py`、`scripts/sync-registry-source.sh`。

## 目录与职责分层
- `skills/incubating/`、`skills/active/`、`skills/archived/`：skill 生命周期主目录；状态规则由 `scripts/validate-registry.py`、`scripts/check-skill.sh`、`docs/lifecycle.md` 约束。
- `templates/basic-skill/`、`templates/scripted-skill/`、`templates/reference-heavy-skill/`：脚手架模板源，由 `scripts/new-skill.sh` 复制并替换占位名。
- `catalog/`：生成物目录；`scripts/build-catalog.sh` 产出 `catalog.json`、`active.json`、`compatibility.json`、`registries.json`，`catalog/provenance/` 存放 release provenance。
- `config/`：外部 source 与签名配置；当前关键文件是 `config/registry-sources.json`、`config/signing.json`、`config/allowed_signers`。
- `policy/` 与 `schemas/`：治理约束层；`policy/promotion-policy.json` 负责 active skill 审核门槛，`schemas/skill-meta.schema.json` 负责 `_meta.json` 结构定义。
- `.cache/registries/`：远程 git registry 的本地缓存目录，由 `scripts/sync-registry-source.sh` 写入。

## 自动化工作流
- 创建：`scripts/new-skill.sh` 从 `templates/` 初始化新 skill。
- 单体校验：`scripts/check-skill.sh` 检查 `SKILL.md`、`_meta.json`、`CHANGELOG.md`、`tests/smoke.md` 与 secret scan。
- Registry 级校验：`scripts/check-all.sh` 串联 `scripts/check-registry-sources.py`、`scripts/validate-registry.py`、`scripts/check-registry-integrity.py`、`scripts/check-promotion-policy.py`，并验证 `catalog/*.json` 可重复生成。
- 审核/推广：`scripts/request-review.sh`、`scripts/approve-skill.sh`、`scripts/review-status.py`、`scripts/promote-skill.sh` 共同驱动 review 到 active 的流程；高风险规则来自 `policy/promotion-policy.json`。
- 分发/本地运行：`scripts/install-skill.sh`、`scripts/sync-skill.sh`、`scripts/switch-installed-skill.sh`、`scripts/rollback-installed-skill.sh` 面向本地 agent skill 目录；安装状态写入目标目录下的 `.infinitas-skill-install-manifest.json`。
- 发布：`scripts/release-skill.sh`、`scripts/release-skill-tag.sh`、`scripts/generate-provenance.py`、`scripts/sign-provenance.py`、`scripts/verify-provenance.py`、`scripts/sign-provenance-ssh.sh`、`scripts/verify-provenance-ssh.sh` 组成完整 release/provenance 链路。

## 运行时依赖
- 必需命令：`bash`、`python3`、`git`，以及常见 Unix 工具（`cp`、`mv`、`rm`、`find`、`sed`、`diff`、`grep`）。
- 可选命令：`gh` 用于 GitHub Release（见 `scripts/release-skill.sh`），`ssh-keygen` 用于 SSH provenance 签名/验签（见 `scripts/sign-provenance-ssh.sh`、`scripts/verify-provenance-ssh.sh`）。
- CI 运行时：GitHub Actions 在 `ubuntu-latest` 上安装 `python-version: 3.11` 并执行 `scripts/check-all.sh`，见 `.github/workflows/validate.yml`。

## 明显缺失 / 边界
- 未发现 `package.json`、`Cargo.toml`、`go.mod`、`Dockerfile` 等应用级构建清单；该仓库当前不是 Node/Rust/Go/容器项目。
- 未见数据库、HTTP API、前端 UI、消息队列或后台 worker；所有行为都通过本地文件系统 + Git + CLI 脚本完成。
- 对 roadmap 来说，最重要的既有资产是“轻依赖 shell/python 自动化 + Git 驱动治理”，后续扩展应优先沿这条路线演进，而不是引入重型应用框架。
