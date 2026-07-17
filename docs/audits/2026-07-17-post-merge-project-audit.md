# infinitas-skill 合并后全面审计报告

**审计日期：** 2026-07-17  
**审计基线：** `main` @ `5533c0f`（本地比 `origin/main` 领先 21 个提交）  
**审计范围：** 产品与业务闭环、双消费者架构、API/CLI 契约、发布制品、身份与访问、安全、数据库、后台任务、运维、测试、CI/CD、Web UI、可访问性、响应式、主题、性能与文档  
**审计原则：** 只检查、复现、记录和排序；不在审计阶段修改产品实现

## 1. 最终结论

**发布结论：不通过（Fail）。**

项目已经具备较强的工程底座，但当前不能作为 v0.1 发布。阻断原因不是格式、静态检查或依赖漏洞，而是两个直接影响核心价值的运行时问题：

1. 当前对外可用的默认 `external_ref` 发布路径会生成一个状态为 `ready`、但不能被安装器接受的制品；唯一能携带完整技能内容的 `uploaded_bundle` 又没有对应的 Agent/CLI 上传 API。
2. 正常动画偏好下，Web 顶栏、标题和主要卡片永久保持 `opacity: 0`，人类管理员看到的主要是空白页面。

此外，匿名分享链接密码解析的限流记录会随错误响应回滚，暴力破解保护实际无效；平台兼容性字段也从未被写入或成为发布门槛。

这意味着：**质量门全绿证明了仓库内部契约的一致性，但尚未证明产品的核心业务闭环可用。**

### 评分总览

| 维度 | 评分 | 判断 |
|---|---:|---|
| 发布就绪度 | 43/100 | 不通过；存在 2 个 Critical 阻断项 |
| 产品与业务闭环 | 42/100 | 概念合理，但 publish → install 主链路未闭合 |
| 架构与领域边界 | 88/100 | 双消费者、领域所有权、事务和 lifespan 边界清晰 |
| API / CLI 契约 | 76/100 | OpenAPI 同步良好，但内容上传契约缺失 |
| 安全 | 72/100 | 基础防护较强；匿名分享限流存在实质缺口 |
| 测试与质量保证 | 68/100 | 数量与门禁强，但未覆盖用户可见性和真实安装闭环 |
| 发布工程 / CI | 78/100 | 完整且可复现；当前提交尚未进入远端 CI |
| 运维与部署 | 70/100 | SQLite 单节点边界明确；参考 Compose 无法直接网页登录 |
| 可维护性 | 91/100 | 硬门有效，模块、函数、CSS、脚本规模均合规 |
| Web UX / 可访问性 | 58/100 | 基础语义不错，但当前正常模式不可见 |
| 响应式 | 72/100 | 320px 无横向溢出，移动端信息密度仍需优化 |
| 主题与视觉系统 | 79/100 | token 化和暗色模式完整；存在重复卡片与冗余层级 |
| 性能 | 75/100 | 资产较轻；存在无效请求和可选超大远程背景 |
| 文档与治理 | 73/100 | 文档体系完整，但部分“maintained”说明已过时 |

**综合工程性：76/100。** 这是一个工程结构明显优于当前产品完成度的项目：底层治理接近可持续维护水平，但功能闭环和真实用户验证没有跟上。

## 2. 审计证据与质量门

合并后的完整门禁成功执行：

| 检查 | 结果 |
|---|---|
| Ruff lint | Pass |
| Ruff format check | Pass |
| Mypy（`src/infinitas_skill` + `server`） | Pass |
| Policy packs | Pass |
| Unit / integration / security / performance | 1202 passed |
| 非 E2E 综合覆盖率 | 64.04%，通过 64% 门槛 |
| Playwright E2E | 22 passed |
| Alembic metadata / 空库往返 | 2 passed |
| OpenAPI drift | Pass |
| `pip-audit` | 无已知漏洞 |
| `npm audit --audit-level=high` | 无高危漏洞 |
| 前端构建 | Pass |
| `git diff --check` | Pass（审计报告写入前） |

仓库规模与维护性硬门：

- 生产 Python 约 40,774 行；最大生产模块 549 行，低于 600 行上限。
- 最大生产函数由测试强制不超过 100 行。
- `server/static/css/input.css` 为 978 行，低于 1000 行上限。
- 顶层 `scripts/` 严格为 4 个允许文件。
- 最终 CSS 为 34,742 bytes；全部前端 JavaScript 约 125,996 bytes。
- OpenAPI 为跟踪生成物，并具有无写入的 `--check` 模式。

这些指标说明工程治理真实有效，但也说明现有测试更偏向“结构和接口存在”，尚不足以替代真实业务验收。

## 3. 严重度统计

| 严重度 | 数量 | 发布含义 |
|---|---:|---|
| Critical | 2 | 阻断发布 |
| High | 4 | Critical 修复后仍必须在发布前解决 |
| Medium | 6 | 建议在首个发布迭代内完成 |
| Low | 3 | 可进入后续治理 backlog |
| **总计** | **15** | **当前 Fail** |

## 4. Critical 发现

### C1. 没有一条对外可用且最终可安装的发布路径

- **位置：** `server/modules/release/materializer.py:59`、`server/modules/release/bundle.py:27`、`server/modules/authoring/schemas.py:25`、`server/modules/authoring/service.py:87`、`src/infinitas_skill/install/skill_validation.py:98`
- **类别：** Product correctness / Release / Agent workflow
- **严重度：** Critical
- **描述：** 默认内容模式是 `external_ref`。该模式不会拉取固定 commit 的真实技能内容，而只把 `snapshot/content-ref.txt` 与 `snapshot/metadata.json` 写入 tar 包。安装器随后要求制品根目录至少存在 `SKILL.md`、`_meta.json`、`CHANGELOG.md` 和 smoke test，因此该包必然不能安装。
- **第二层问题：** `uploaded_bundle` 能携带完整文件，但 API 只接受一个实际为数据库 Artifact ID 的 `content_upload_token`；OpenAPI、router 和 CLI 中没有创建 release-independent 上传 Artifact 的端点。现有测试通过直接调用 storage/service 并插入数据库来“预置上传”，真实消费者无法完成这一步。
- **隔离复现：** 使用官方 integration fixture 创建默认版本和 Release，worker 报 job completed，Library 显示 Release `ready`。解包后文件严格为：

  ```text
  snapshot/content-ref.txt
  snapshot/metadata.json
  ```

  同一制品交给正式安装校验器，结果为缺少 `SKILL.md`、`_meta.json` 和 `CHANGELOG.md`。
- **影响：** Agent 可以创建对象、版本、Release、Exposure，甚至获得安装 URL，但无法得到可运行技能；这是核心 publish → discover → install 价值链断裂。
- **修复建议：** 在 v0.1 只保留一条明确路径：
  1. 实现认证的内容包上传端点与 CLI 命令，返回不可伪造的一次性上传引用；worker 验证包结构后再创建版本；或
  2. 让 `external_ref` worker 在隔离目录中拉取被 40 位 commit 固定的内容，验证 host/ref、完整技能结构、secret 扫描与 digest，再把真实文件物化为 bundle。
  3. `ready` 前必须运行与安装器相同的 `validate_installable_skill_dir()` 或等价服务端校验。
  4. 新增真正的 API/CLI publish → worker → exposure → registry → install → target file integrity E2E。
- **建议命令：** `/harden`

### C2. 正常动画偏好下 Web 主界面永久透明

- **位置：** `server/static/css/input.css:901`、`server/static/js/app.js:77`、`server/templates/layout-kawaii.html:46`
- **类别：** Accessibility / Functional UI / Motion
- **严重度：** Critical
- **标准：** WCAG 1.3.1、2.1.1；核心功能可达性
- **描述：** CSS 将 `.animate-in` 和 `.reveal-pending` 都设为 `opacity: 0`。JavaScript 只查询 `[data-reveal]` 并为其添加 `.reveal-visible`，不会处理模板广泛使用的 `.animate-in`。只有 `prefers-reduced-motion: reduce` 或禁用脚本时才强制可见。
- **浏览器证据：** 在 Playwright 默认动画偏好、1440px 与 320px 两种视口下，顶栏、Hero、页面标题、设置卡片和管理卡片均不可见；截图呈现大面积空白。强制 `reduced_motion="reduce"` 后，同一页面内容立即出现。
- **影响：** 大多数正常用户无法使用人类管理员入口；Cookie/CSRF、Library、Token、Share、Activity 等功能虽然存在于 DOM，却不可见。
- **修复建议：** 统一动画契约，只让带 `data-reveal` 的元素在 JS 初始化后进入 pending；默认 CSS 必须可见。增加 `opacity > 0`、可见文本、关键 CTA 可点击和截图回归，而不是只检查 DOM 节点存在。
- **建议命令：** `/animate`、`/harden`

## 5. High 发现

### H1. 匿名分享链接解析的限流记录会在错误密码时回滚

- **位置：** `server/modules/access/share_links_router.py:120`、`server/rate_limit.py:157`、`server/db.py:85`
- **类别：** Security / Authentication abuse prevention
- **严重度：** High
- **描述：** 解析端点先通过同一个请求 Session 写入 `RateLimitEntry`，随后密码或 secret 错误会转换为 `HTTPException`。`get_db()` 对异常统一 rollback，于是限流计数也被回滚。
- **隔离复现：** 对同一个 4 位密码分享链接连续发送 25 次错误密码，结果全部为 403，429 次数为 0；数据库中 `share-resolve:*` 限流 bucket 数量为 0。
- **影响：** 匿名攻击者可无限尝试分享密码；当前最小密码长度仅 4，实际风险明显。
- **修复建议：** 限流计数使用独立事务或原子提交的专用 Session；失败认证也必须持久化。增加“连续错误解析达到阈值后 429”的安全测试，并覆盖密码与 capability secret 两条路径。
- **建议命令：** `/harden`

### H2. Hosted Release 的平台兼容性字段从未持久化，也不阻断 ready

- **位置：** `server/modules/release/materializer.py:251`、`server/modules/release/models.py:42`、`server/modules/release/schemas.py:24`
- **类别：** Trust / Product contract / Release policy
- **严重度：** High
- **描述：** materializer 调用 `collect_release_state(...).get("platform_compatibility")` 后丢弃返回值；异常被日志捕获并明确“proceeding without compatibility data”。全仓没有给 `Release.platform_compatibility_json` 赋值的实现，API 因此稳定返回 `{}`。
- **影响：** README 声明“平台/运行时支持判断属于产品能力”，但 Hosted Release 无法向 Agent 提供该判断，也不会因 OpenClaw 不兼容而阻止 Release ready 或后续 Exposure。
- **修复建议：** 明确 Hosted 与 repo-native 兼容性来源；把结构化结果写入 Release，在 provenance/manifest 中签名，并按产品策略决定 unknown/stale/blocking 是否阻止 ready 或 public exposure。
- **建议命令：** `/harden`

### H3. 参考 Compose 配置无法启用浏览器管理员登录

- **位置：** `.env.compose.example:18`
- **类别：** Operations / First-run business availability
- **严重度：** High
- **描述：** 示例 `INFINITAS_SERVER_BOOTSTRAP_USERS` 只提供 token，不提供 password。Bearer Token 可服务 Agent，但 Web 登录只验证用户名/密码；复制示例、替换 token 和 secret 后，人类管理员仍无法登录。
- **影响：** 双消费者架构中的人类管理员入口在官方部署样例下不可用，且用户可能误以为 token 同时是网页登录凭据。
- **修复建议：** 示例为 maintainer/contributor 明确提供独立 password placeholder；部署检查应验证至少一个可登录 maintainer，同时强调 password 与 Agent token 生命周期分离。
- **建议命令：** `/onboard`、`/clarify`

### H4. E2E 门禁未验证“用户真正看得见”和“Release 真正装得上”

- **位置：** `tests/e2e/test_navigation.py:4`、`tests/e2e/test_library_admin_flow.py:4`、现有 release materialization integration tests
- **类别：** Test strategy / Release confidence
- **严重度：** High
- **描述：** 浏览器测试主要断言 selector 存在、文字存在或 bounding box 高度；Playwright 的 `is_visible()` 不会因为 `opacity: 0` 判定不可见。Release 测试验证了 tar、manifest、signature 与 ready 状态，却没有把生成制品交给正式安装器。
- **影响：** 两个 Critical 问题都能在 1202 + 22 全绿的情况下进入 `main`，说明当前发布门缺少业务结果断言。
- **修复建议：** 引入三类结果型测试：计算样式可见性/截图、真实发布安装回路、参考 Compose 首次登录 smoke。把关键业务路径作为独立发布门，而不是继续增加只验证内部状态的测试数量。
- **建议命令：** `/harden`

## 6. Medium 发现

### M1. 首页背景偏好仍调用已删除的 API

- **位置：** `server/static/js/modules/auth-background.js:99`、`server/templates/partials/home-auth-panel.html:27`
- **类别：** Functional UI / Performance / Dead contract
- **严重度：** Medium
- **描述：** 前端调用 `/api/v1/background/me` 与 `/api/v1/background/set`，但 OpenAPI、router 与 server 模块中没有对应路由。登录用户首页每次都会产生失败请求，远端同步静默失效。
- **浏览器证据：** 本地资源追踪中该请求产生约 28 KB 无效响应传输。
- **修复建议：** 该功能不在 v0.1 产品契约内，优先删除远端同步和相关 UI；若确需保留，归入 identity/profile 领域并补齐 schema、CSRF、持久化和 E2E。
- **建议命令：** `/distill`、`/optimize`

### M2. Console 页面存在重复 H1、跳级标题和重复说明卡片

- **位置：** `server/templates/layout-kawaii.html:149`、`server/templates/manage.html:4`、`server/templates/settings.html:4`
- **类别：** Accessibility / Information architecture / Anti-pattern
- **严重度：** Medium
- **标准：** WCAG 1.3.1、前端设计“避免重复信息”
- **描述：** console layout 已输出页面标题 H1，manage/settings/profile 模板再次输出相同 H1；Settings 随后直接使用 H3。视觉上也形成“Management”大卡片后紧接一个同名小卡片。
- **影响：** 屏幕阅读器大纲和视觉层级都不清晰，增加无价值首屏高度。
- **修复建议：** 每页保留一个 H1；子区块从 H2 开始；删除重复标题卡，用 tabs 或内容组直接承接页面介绍。
- **建议命令：** `/clarify`、`/distill`

### M3. 320px 移动端 chrome 占据过多首屏，底部导航遮挡内容

- **位置：** `server/templates/layout-kawaii.html`、`server/static/css/input.css` 的 mobile topbar/bottom navigation 规则
- **类别：** Responsive / Mobile UX
- **严重度：** Medium
- **描述：** 移动端顶栏展开品牌、主题、语言、状态、导航和搜索，约占首屏一半；管理页固定底部导航覆盖第二个标题卡与 tabs 区域。虽然没有横向滚动，任务内容需要明显下移或滚动后才出现。
- **影响：** 小屏管理员进入页面时先看到控制 chrome，而不是当前任务；信息查找效率下降。
- **修复建议：** 把主题/语言/focus 收进设置抽屉；压缩品牌区；为固定底栏按真实高度预留 safe-area；避免顶部和底部同时重复导航。
- **建议命令：** `/adapt`

### M4. 64.04% 聚合覆盖率只比门槛高 0.04%，且不约束关键业务路径

- **位置：** `scripts/check-all.sh`、`pyproject.toml`
- **类别：** Test quality / Risk management
- **严重度：** Medium
- **描述：** 当前覆盖率门槛有效但余量极小，且是跨 `src` 与 `server` 的总量门；高风险模块可以被大量低风险测试稀释。此次 Critical/High 都位于已有测试触达但断言不足的路径。
- **影响：** 覆盖率数字容易被误解为业务可靠性，新增未覆盖代码还可能造成门禁波动。
- **修复建议：** 保留总门槛，同时为发布物化、安装、授权、分享解析与 UI 关键页设置结果型测试和按包最低覆盖；目标不是盲目提高百分比，而是覆盖状态转换与失败路径。

### M5. “maintained”业务文档仍描述已删除的 ShareLink 双轨模型

- **位置：** `docs/guide/control-plane-business-flows.md:246`
- **类别：** Documentation / Architecture communication
- **严重度：** Medium
- **描述：** 文档称仍存在 `AccessGrant + Credential` 与 standalone `ShareLink` 两套模型，但代码和测试已明确删除 standalone shares 模块并统一到 access 领域。
- **影响：** 新贡献者可能按不存在的模型设计修复，审计人员也会误判领域边界。
- **修复建议：** 更新业务流文档，并补充真实 content ingress 与 installable artifact 约束；文档门应检查关键术语与已删除模块。
- **建议命令：** `/clarify`

### M6. `SECURITY.md` 不是完整的发布级安全政策

- **位置：** `SECURITY.md:1`
- **类别：** Security governance
- **严重度：** Medium
- **描述：** 当前文件仅列出不应提交的 secret 与一般建议，没有支持版本、漏洞报告渠道、响应预期、披露流程、威胁边界或部署安全基线。
- **影响：** 一旦发布镜像或供其他团队使用，安全问题缺少标准入口和责任边界。
- **修复建议：** 增加 supported versions、private reporting channel、response SLA、credential rotation、single-node/SQLite 威胁边界和第三方依赖处理流程。

## 7. Low 发现

### L1. 私有控制台依赖 Google Fonts 与可选 Unsplash 1920px 背景

- **位置：** `server/templates/layout-kawaii.html:24`、`server/templates/partials/home-auth-panel.html:85`
- **类别：** Privacy / Performance / Availability
- **严重度：** Low
- **描述：** 页面默认连接 Google Fonts；用户选择背景后会请求 Unsplash 1920px 图片。离线或受限网络会回退，但私有控制台访问会暴露到第三方资源域。
- **建议：** 自托管字体；删除非核心远程背景，或明确 opt-in、尺寸预算和隐私提示。
- **建议命令：** `/optimize`

### L2. CI 在同一 workflow 内和两个 workflow 间重复执行大量门禁

- **位置：** `.github/workflows/validate.yml:39`、`.github/workflows/container-image.yml:44`
- **类别：** CI efficiency
- **严重度：** Low
- **描述：** validate 先跑 unit、`make ci-fast`、Alembic/OpenAPI，再跑包含这些检查的 `check-all.sh`；container-image 又独立跑完整 `check-all.sh`。
- **建议：** 把完整验证做成 reusable workflow/job artifact，镜像发布依赖其成功结果，减少反馈时间和 runner 成本。

### L3. 前端构建提示 Browserslist 数据过期，tar 提取在 Python 3.14 有行为变更警告

- **位置：** 前端构建输出、`src/infinitas_skill/install/distribution_materialization.py:50`
- **类别：** Dependency maintenance / Future compatibility
- **严重度：** Low
- **建议：** 更新 `caniuse-lite` 数据；显式使用兼容的 tar filter 或手工 metadata 策略，并在 Python 3.14 加入 CI 预演。

## 8. 功能与业务设计合理性

### 合理且应保留的设计

- **双消费者分工合理。** Web 负责管理员分发控制，Agent/CLI 负责发布、发现和安装；两者共享领域服务但不互相导入。
- **对象、不可变版本、Release、Exposure、Review、Access 的分层合理。** “Release ready 不等于可消费”是正确的治理模型。
- **v0.1 只支持 `skill` 合理。** Object 抽象保留扩展边界，但没有虚假宣称其他 kind 已实现。
- **private-first 与 public 强制 blocking review 合理。** 对私有技能仓库来说，默认保守是正确业务选择。
- **单节点 SQLite 发布边界合理。** 当前明确不宣称 PostgreSQL、多节点与水平扩展，避免超卖能力。
- **浏览器 session 与 Agent token 分离合理。** 本轮重构已消除网页登录吊销 Agent token 的旧问题。

### 当前不合理或尚未完成的设计

- **内容所有权没有闭环。** 系统把 `external_ref` 当作不可变内容快照，但实际上只冻结了字符串，不拥有或验证真实内容。
- **`content_upload_token` 命名和契约不合理。** 它是可猜测的数据库整数 ID，不是上传能力 token；同时没有上传动作。
- **Release readiness 只证明制品内部自洽，不证明它是一个可安装 Skill。** 业务语义与技术状态不一致。
- **兼容性、Review 和 provenance 的边界需要重新定义。** 当前 repo-native release policy 很强，Hosted Release 却没有把兼容性结果持久化到同一信任链。
- **背景个性化不属于 v0.1 核心价值。** 在上传/安装主链路未闭合时保留该功能，增加了 JS、第三方资源、无效 API 和测试面。
- **bootstrap-only 身份管理可作为 v0.1 限制，但参考部署必须保证至少一个可登录管理员。**

## 9. 工程性分析

### 优点

- 领域模型所有权清楚，`model_registry.py` 只负责 metadata 注册。
- UI 与 JSON router 边界遵守双消费者要求。
- service 不自行 commit，事务由依赖/上下文统一管理。
- 应用 import 与 `create_app()` 不迁移数据库，初始化在 lifespan。
- 单一 `0001_initial.py`、Alembic drift、OpenAPI drift 都有硬门。
- 生产模块、函数、CSS、JS 与顶层脚本均有自动化规模预算。
- 安全头、CSP、CSRF、TrustedHost、token hash、scope 和对象授权基础较完整。
- Release 制品具有确定性 tar metadata、manifest、SSH signature 与 provenance 验证。
- worker 有 lease、heartbeat、失败状态与恢复检查；备份、恢复、检查、mirror 均有 runbook。
- 依赖 action 使用 commit pin，Python/Node 依赖审计进入发布门。

### 局限

- 测试策略偏内部契约，缺少最终用户结果断言。
- repo-native CLI release 与 Hosted Release 的 trust semantics 尚未完全收敛。
- 文档、UI 个性化残留和实际 v0.1 范围存在偏差。
- 本地 `main` 领先远端 21 个提交，当前审计基线尚没有 GitHub CI、multi-arch image build 与 provenance attestation 结果。

## 10. 前端专项结论

### AI Slop Verdict：Partial

明确未发现：

- 紫蓝渐变标题或 metric gradient text
- 霓虹 cyan-on-dark 默认主题
- 大面积 glassmorphism / glow border
- 弹跳或 elastic easing
- 纯黑纯白主色

仍存在：

- 大量圆角卡片与重复 console metric card grid
- emoji + 标题 + 数字的同构卡片
- Hero 大标题模板感较强
- 页面标题与正文标题重复
- 移动端 chrome 过度占用首屏

视觉方向本身是明确的 kawaii / soft editorial，不属于无意图模板；问题主要是组件层级过多和产品控制台的信息效率不足。

### 正向 A11y / Responsive 证据

- 关键输入均有 label 或 ARIA name。
- 被测导航和 toggle 目标高度达到 44px。
- 320px 页面没有非预期横向溢出。
- light/dark 主题关键 token 对比度测试达到 4.5:1。
- 有 skip link、可见 focus、modal ARIA、focus trap、Escape/Tab 处理。
- 支持 `prefers-reduced-motion`，但当前该分支意外成为唯一可见模式。

## 11. 建议整改顺序

| 优先级 | 工作 | 验收条件 |
|---|---|---|
| P0 | 重新定义并实现唯一可安装的内容 ingress | Agent/CLI 可上传或 worker 可安全导入；Release ready 前通过正式 Skill 校验 |
| P0 | 修复 `.animate-in` 可见性契约 | 默认动画偏好下 desktop/mobile 关键内容 `opacity > 0`，截图回归通过 |
| P0 | 增加 publish → install 真正 E2E | 从 HTTP/CLI 发布到目标目录出现有效 `SKILL.md`，并通过 installed integrity |
| P0 | 修复 share resolve 限流事务 | 11 次或配置阈值后稳定返回 429，错误尝试计数持久化 |
| P1 | 持久化并签名平台兼容性 | Release/API/provenance/manifest 一致；策略可阻断不兼容公开发布 |
| P1 | 修正 Compose bootstrap 登录 | 示例部署后 maintainer 可网页登录且 Agent token 独立可用 |
| P1 | 删除或补齐背景偏好 API | 首页无 404；不保留半实现功能 |
| P2 | 收敛 mobile chrome、标题层级与卡片密度 | 单 H1、无首屏遮挡、任务内容优先 |
| P2 | 更新业务流、Security policy 与发布文档 | 文档不再描述已删除模型，公开安全流程完整 |
| P3 | 合并 CI 重复执行并补未来版本预演 | reusable gate；Python 3.14 与浏览器数据维护明确 |

## 12. 发布准入条件

只有满足以下条件后，才能把结论提升为“有条件通过”：

- C1、C2、H1 全部修复并有失败前/修复后回归测试。
- 真实发布安装闭环至少覆盖 `uploaded_bundle` 或最终选定的唯一内容模式。
- 正常动画偏好的 desktop 与 320px 浏览器 smoke 通过。
- 参考 Compose 能完成首次管理员登录。
- `main` push 到远端，GitHub validate 与 multi-arch container build/attestation 全绿。
- 重新运行 `scripts/check-all.sh`、`git diff --check` 并保持工作树干净。

在此之前，不建议创建应用版本 tag、发布 `latest` 镜像或向其他团队宣称 v0.1 可用。
