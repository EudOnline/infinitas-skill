# 外部集成

## 总览
- 集成面是典型的 Git-centric registry：远程 registry source、GitHub CI、Git tag / GitHub Release、provenance 签名/验签、本地 agent 安装目录。
- 当前没有 npm / PyPI / Docker registry / 云对象存储等分发链路；分发模式仍是“git 仓库 + 本地复制安装 + 生成的 catalog JSON”。

## Remote Registry
- registry source 的单一配置入口是 `config/registry-sources.json`；当前只启用了一个名为 `self` 的 `git` registry，URL 为 `https://github.com/EudOnline/infinitas-skill.git`，分支 `main`，`trust` 为 `private`，`priority` 为 `100`。
- 生成后的 source 视图写入 `catalog/registries.json`；`scripts/build-catalog.sh` 会补充每个 registry 的 `resolved_root`，供后续安装/解析使用。
- `scripts/sync-registry-source.sh` 负责把 git registry clone/fetch 到本地；若配置未指定 `local_path`，默认缓存到 `.cache/registries/<registry-name>/`。`scripts/sync-all-registries.sh` 则批量同步全部启用项。
- `scripts/resolve-skill-source.py` 是安装/切换/回滚的解析核心：按显式 `--registry`、版本、`priority`、stage 偏好（默认 `active` 优先）解析 skill 来源。
- 重要发现：多 registry 设计已经落地到配置、导出、同步、解析四层，但当前生产配置仍是单 registry/self，尚未看到第二个真实远程源。

## 本地消费者集成
- 默认安装目标是 `~/.openclaw/skills`，见 `scripts/install-skill.sh`、`scripts/sync-skill.sh`、`scripts/switch-installed-skill.sh`、`scripts/rollback-installed-skill.sh`；这表明首要消费者是本机 agent runtime，而不是中央服务。
- 目标目录中的 `.infinitas-skill-install-manifest.json` 由 `scripts/update-install-manifest.py` 维护，记录 `source_repo`、`source_registry`、`source_version`、`locked_version`、历史版本与 target path。
- `scripts/check-install-target.py` 在安装/同步/切换前校验 `depends_on` 与 `conflicts_with`，因此“依赖解析”发生在本地 install target 层，而不是远程 registry 服务层。
- `catalog/compatibility.json` 是面向消费方的兼容性导出；其数据来自每个 skill `_meta.json` 中的 `agent_compatible` 字段，规则定义见 `schemas/skill-meta.schema.json` 与 `docs/compatibility-matrix.md`。

## Signing 与 Verification
- provenance 文件由 `scripts/generate-provenance.py` 生成到 `catalog/provenance/<skill>-<version>.json`；内容包含 skill 元数据、`git.repo_url`、`git.branch`、`git.commit`、`expected_tag` 与 `registry.default_registry`。
- HMAC 签名链路由 `scripts/sign-provenance.py` 与 `scripts/verify-provenance.py` 提供，依赖环境变量 `INFINITAS_SKILL_SIGNING_KEY`，可选 `INFINITAS_SKILL_SIGNING_KEY_ID`；签名产物是 `<file>.sig.json`。
- SSH 签名链路由 `scripts/sign-provenance-ssh.sh` 与 `scripts/verify-provenance-ssh.sh` 提供，配置来自 `config/signing.json`，允许签名人列表来自 `config/allowed_signers`；底层命令是 `ssh-keygen -Y sign` / `ssh-keygen -Y verify`，签名产物是 `<file>.ssig`。
- `scripts/release-skill.sh` 可以在写出 provenance 后立即执行 HMAC 签名+验签，或 SSH 签名/验签，形成 release 时的“生成即验证”链路。
- 重要发现：`config/allowed_signers` 当前为空，说明 SSH 验签机制已接好接口，但信任根尚未实际配置。
- 明显边界：未见 Sigstore/Cosign、GPG artifact signing、KMS/HSM、第三方 transparency log 集成。

## Release 与发布通道
- `scripts/release-skill.sh` 是统一 release 入口；它会先执行 `scripts/check-skill.sh` 和 `scripts/check-all.sh`，并且只接受 `skills/active/` 中的 skill 进入 release。
- Git tag 约定是 `skill/<name>/v<version>`，实现见 `scripts/release-skill-tag.sh` 与 `scripts/release-skill.sh`，文档约定见 `docs/release-strategy.md`。
- 若带 `--push-tag`，脚本会执行 `git push origin <tag>`；若带 `--github-release`，会调用 `gh release create`，说明正式发布平台是 GitHub，而不是独立包仓库。
- `scripts/generate-provenance.py` 与 `scripts/update-install-manifest.py` 都会读取当前仓库的 `remote.origin.url`，所以 Git remote 配置本身也是一条关键集成面。
- 重要发现：发布流程覆盖 tag、notes、GitHub Release、provenance、签名与验签，但 CI 中没有自动 publish；当前仍是人工触发的受控 release。

## CI / Policy / Governance 集成
- GitHub Actions 工作流位于 `.github/workflows/validate.yml`；触发条件是 push 到 `main` 与 pull request，执行 `scripts/check-all.sh`。
- `scripts/check-all.sh` 串起 source 配置校验、元数据校验、依赖完整性、promotion policy 与 catalog 可重复生成，因此 CI 的主要角色是 registry integrity gate，而不是部署。
- active skill 的治理规则在 `policy/promotion-policy.json`；执行入口是 `scripts/check-promotion-policy.py`，配套操作命令包括 `scripts/request-review.sh`、`scripts/approve-skill.sh`、`scripts/review-status.py`。
- review 数据写在各 skill 目录的 `reviews.json`；也就是说审核集成仍然是 repo-native 文件流，而不是外部审批系统。

## 现状结论
- 已接入：GitHub 仓库、GitHub Actions、Git tags、可选 GitHub Releases、HMAC provenance、SSH provenance、本地 OpenClaw skill 安装目录。
- 已预留但未充分利用：多远程 registry、SSH allowed signers 信任根、真实 active skills 的 catalog 生态。
- 尚未接入：包管理仓库、容器镜像仓库、外部 artifact store、Sigstore/GPG 类签名基础设施、自动化发布流水线。
