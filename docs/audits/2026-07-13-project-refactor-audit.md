# Infinitas Skill 重构后项目审计报告

**审计日期：** 2026-07-13  
**审计范围：** `server/`、`src/infinitas_skill/`、`scripts/`、`tests/`、Alembic、OpenAPI、CI、Web UI 静态实现  
**审计方式：** 初始审计为只读审查与隔离环境验证；随后按本报告逐项整改并补充回归测试  
**工作树背景：** 审计开始时已有 119 个文件未提交变更（2,388 行新增、5,397 行删除），全部视为现有用户工作，不做归因或覆盖。

## 0. 整改状态（2026-07-13）

| 编号 | 状态 | 结果摘要 |
|---|---|---|
| H1 | 已修复 | 自动生成 token 使用实际生成值入库，且已有 active personal token 时不再重启轮换 |
| H2 | 已修复 | 浏览器 credential 改为 `session`，登录/登出不再吊销 Agent 的 `personal_token` |
| H3 | 已修复 | `Base`/`utcnow` 移至无反向依赖的 `server/model_base.py`，干净解释器导入通过 |
| H4 | 已修复 | ORM 索引与迁移 head 对齐，循环 FK 使用延迟约束排序，`alembic check` 无漂移 |
| H5 | 已修复 | tar 成员写入前统一校验，拒绝 traversal、绝对路径、链接与特殊文件 |
| M1 | 已修复 | OpenAPI 支持真正的 `--check`，schema app 不启动数据库，环境强隔离 |
| M2 | 已修复 | 分页测试改为验证实际 FastAPI `Query` 上限元数据 |
| M3 | 已修复（环境受限） | Makefile 将 unit/security/performance/Alembic 拆为独立 pytest 进程；当前沙箱的 AnyIO worker-thread 阻塞使同步 API 请求组无法本地完成 |
| M4 | 已治理 | 全仓 Ruff `F` 为零；`server/src` 清零，脚本、测试、迁移按规则码建立不可增长预算 |
| M5 | 已修复 | autouse fixture 在每个测试后恢复全部 `INFINITAS_*` 环境变量 |
| L1 | 已修复 | PurgeCSS 中间文件移至已忽略的 `build/static/` |
| L2 | 已修复 | 通用控制台表面去渐变/blur/glow，首页 hero 与主 CTA 保留品牌强调 |

本轮新增的关键证据：维护范围 Ruff 通过；全仓 `ruff --select F` 通过；分层 Ruff 非增长预算通过；Mypy 对 208 个源文件通过；OpenAPI `--check` 通过；Alembic 元数据 2 项通过；完整 performance 15 项通过；unit 排除 4 个环境阻塞同步请求用例后 848 项通过；聚焦整改回归 20 项通过；开发工作流/预算契约 6 项通过；前端构建通过。

## 1. 执行摘要

总体结论：**有条件不通过**。项目的核心架构方向是清楚的，Web UI 与 Agent/CLI 两类消费者也确实分别存在，不能把未被前端调用的 API 或 CLI 函数当作死代码。本轮未发现 CLI 核心路径与当前 OpenAPI 路由不匹配：CLI 使用的 15 个 `/api/v1` 核心路径均能在 65-path OpenAPI 中找到。

问题主要不是“路由重复”，而是多轮重构后留下的跨层契约断裂：凭据类型复用导致浏览器登录影响 Agent token；自动生成 token 与实际入库 token 不一致；模型拆包后的兼容 re-export 造成导入顺序依赖；ORM 与迁移 head 存在大量索引漂移。

| 严重度 | 数量 | 结论 |
|---|---:|---|
| Critical | 0 | 未发现无需前置条件即可直接接管生产系统的问题 |
| High | 5 | 凭据生命周期、恢复归档安全、导入拓扑、数据库契约 |
| Medium | 5 | 测试/CI、OpenAPI 生成、性能测试陈旧、仓库 lint 卫生 |
| Low | 2 | 生成物卫生、前端视觉系统过度装饰 |

最高优先级的三个问题：

1. 浏览器登录会选中并吊销 Agent/CLI 使用的 `personal_token`。
2. 开发/测试环境打印的自动生成 bootstrap token 与数据库保存的哈希不匹配。
3. Alembic head 与 ORM 元数据存在 20 组索引差异，并存在 `releases ↔ artifacts` 循环外键。

## 2. 高优先级发现

### H1. 自动生成的 bootstrap token 永远无法认证

**整改状态：已修复。** 自动生成值直接传入 credential service；只有不存在 active personal credential 时才生成。新增“可解析”和“重启不轮换”测试。

- **位置：** `server/db.py:112`
- **类别：** Authentication / Correctness
- **证据：** 代码把生成值放入局部变量 `token`，日志也打印该变量，但调用 `ensure_personal_credential_for_user()` 时传入的是 `item["token"]`。当配置没有 token 时，后者仍为空字符串。
- **隔离复现：** 固定随机输出后，日志打印 `dev_audit_generated_token`；数据库结果为 `matches_generated=False`、`matches_empty=True`。
- **影响：** 默认 development/test bootstrap 用户会收到一个看似可用但实际无效的 bearer token；数据库保存空字符串的 SHA-256 哈希。Agent/CLI 首次接入直接失败，日志信息具有误导性。
- **建议：** 入库参数使用已归一化的局部变量 `token`；为空时禁止创建 credential；增加“日志 token 可通过 `/api/v1/access/me` 认证”的回归测试，并验证重启不会无意轮换已有 token。

### H2. 浏览器登录会吊销 Agent/CLI 的个人 bearer token

**整改状态：已修复。** 浏览器会话使用独立 `session` 类型；兼容识别旧 `personal_token` session placeholder；显式配置 token 对应旧记录被吊销或过期时创建新记录，保留旧审计历史。

- **位置：** `server/api/auth.py:126`
- **类别：** Dual-consumer authentication / Availability
- **证据：** 登录流程查询同一 principal 下最新的、未吊销的 `Credential.type == "personal_token"`，将其吊销，然后以同一类型创建 session placeholder。bootstrap Agent token 也由 `ensure_personal_credential_for_user()` 创建为 `personal_token`。
- **隔离复现：** bootstrap `audit-agent-token` 对应 credential id 为 1；登录查询会选择 id 1，结果 `same_record=True`。
- **影响：** 人类用户一次网页登录即可让同一账号的 Agent/CLI token 失效，违反双消费者隔离。后续重新播种还可能把最新 session credential 改写成配置 token，导致生命周期继续串扰。
- **建议：** 将浏览器 session 与 API personal token 建模为不同 credential type（例如 `session` 与 `personal_token`）；登录只吊销 session；bootstrap 只管理明确标识的配置凭据；补充 bearer → web login → bearer 仍有效的端到端测试。

### H3. 模型拆包后的兼容 re-export 形成导入顺序依赖

**整改状态：已修复。** 新增无领域反向导入的 `server/model_base.py`，领域模型改为依赖该模块，`server.models` 仅保留兼容 re-export。

- **位置：** `server/modules/access/models.py:6`、`server/models.py:71`
- **类别：** Architecture / Runtime correctness
- **证据：** access models 从 `server.models` 导入 `Base`，而 `server.models` 又在模块底部 re-export access models。干净解释器直接执行 `import server.modules.access.authz` 会抛出 partially initialized module 的 `ImportError`；先 `import server.models` 再导入则成功。
- **测试证据：** 单独收集 `tests/unit` 在 `tests/unit/server_access/test_authz.py` 失败；官方快速列表把 integration 放在 unit 前面，可能通过导入缓存掩盖问题。
- **影响：** 插件、脚本、测试或未来 worker 只要采用不同导入入口，就可能在进程启动阶段失败；行为由导入顺序决定。
- **建议：** 把 `Base`、`utcnow` 移至不反向导入领域模型的基础模块；逐步移除 `server.models` 的兼容 re-export，或让各领域模型只依赖该基础模块；增加“每个公开模块在干净解释器中可直接导入”的 smoke test。

### H4. ORM 元数据与 Alembic head 漂移，且发布/制品模型存在循环外键

**整改状态：已修复。** ORM 显式声明迁移 head 的复合索引并移除意外单列索引；release→artifact 约束使用 `use_alter=True`；`Base.metadata.sorted_tables` 和 `alembic check` 均通过。

- **位置：** `server/modules/release/models.py:9`、`alembic/versions/`
- **类别：** Database contract / Migration safety
- **证据：** 空库 `alembic upgrade head` 成功，但随后的 `alembic check` 失败，报告 20 组 upgrade operations，包括多个复合索引被 ORM 视为应删除、多个单列索引被视为应新增。SQLAlchemy 同时警告无法排序 `artifacts` 与 `releases`，因为 `Release` 指向四个 artifact id，而 `Artifact` 又指向 release id。
- **影响：** 新迁移 autogenerate 会产生噪声甚至错误删除性能索引；`Base.metadata.sorted_tables` 已在应用启动路径触发警告，未来 SQLAlchemy 版本可能升级为错误；级联/删除顺序和测试建库行为难以推断。
- **建议：** 明确数据库索引的单一事实来源，使 ORM `Index`/`index=True` 与 head 一致；在 CI 加 `alembic upgrade head && alembic check`；重新评估双向物理外键，至少通过 `use_alter`/命名约束或去除冗余引用解除排序环。

### H5. 托管恢复脚本可被恶意 tar 路径穿越

**整改状态：已修复。** 提取前验证全部成员，只允许普通文件和目录；拒绝相对逃逸、绝对路径、symlink、hardlink、device 与其他特殊成员，并使用 `filter="data"` 提取。

- **位置：** `scripts/rehearse-hosted-restore.py:81`
- **类别：** Security / Operations
- **标准：** CWE-22
- **证据：** 对外部 `archive_path` 直接调用 `tarfile.extractall(output_dir)`，未设置安全 filter，也未逐成员验证 `resolve()` 后仍在目标目录内。项目支持 Python 3.11+，不能依赖较新 Python 的默认安全行为。
- **影响：** 运行恢复演练的操作员若接收了被篡改的备份，归档可写出 `output_dir`，覆盖其权限范围内的任意文件。
- **建议：** Python 3.12+ 使用 `filter="data"`；为 3.11 实现成员路径、符号链接和硬链接目标校验；提取到新临时目录并在验证通过后原子切换；加入 `../`、绝对路径、symlink escape 回归样本。

## 3. 中优先级发现

### M1. OpenAPI 生成器没有检查模式，且生成过程会启动完整应用

**整改状态：已修复。** `server/app_factory.py` 提供可关闭数据库初始化的构造路径；生成器支持 `--output` 与无写入 `--check`，并覆盖继承环境以保证确定性。

- **位置：** `scripts/generate-openapi.py:13`、`server/app.py:35`
- **证据：** 脚本忽略未知的 `--check` 参数，始终覆盖 `openapi.json`；使用 `setdefault`，宿主环境可覆盖隔离配置；导入 `server.app` 会执行迁移和 bootstrap 播种。即使设置 `INFINITAS_SERVER_BOOTSTRAP_USERS=[]`，test 环境也会回退到默认用户并打印自动 token。
- **影响：** CI/开发者无法无副作用检查 schema 漂移；生成结果受宿主环境影响；一次文档生成会写数据库、日志和目标文件。`.gitignore` 又声明忽略 `openapi.json`，但该文件当前已被跟踪，维护意图矛盾。
- **建议：** 支持真正的 `--check`（生成至内存/临时文件后比较）；强制覆盖隔离环境而非 `setdefault`；提供不运行 startup/DB 的 schema app factory；明确 OpenAPI 是跟踪生成物还是运行时产物。

### M2. 分页性能测试仍调用已不存在的 API

**整改状态：已修复。** 测试直接检查真实 `PaginationParams.limit` 的 FastAPI `Query` 元数据包含 `Le(le=100)`；performance 分组 15 项通过。

- **位置：** `tests/performance/test_pagination.py:212`、`server/pagination.py:13`
- **证据：** `PaginationParams.from_query(limit=1000)` 不存在；性能分组结果为 1 failed、14 passed。当前真实边界由 FastAPI `Query(..., le=100)` 实现。
- **影响：** 重构后的旧测试不再验证真实入口；性能/边界分组不能全绿，也未被当前 CI 显式执行。
- **建议：** 通过 TestClient/依赖函数验证 422 或最大值契约，或恢复有明确语义的纯函数构造器；把性能分组加入 CI。

### M3. 官方门禁不能独立证明测试拓扑健康

**整改状态：已修复门禁结构，运行环境仍有验证限制。** `test-contracts` 分别启动 unit、security、performance、Alembic 四个 pytest 进程，并单独执行 OpenAPI check。当前托管沙箱中纯 `anyio.to_thread.run_sync(lambda: 42)` 也会超时，因此所有同步 FastAPI `TestClient` 请求无法在此环境完成；CI 仍固定 Python 3.11 执行这些分组。

- **位置：** `Makefile:21`、`.github/workflows/validate.yml:44`、`pyproject.toml:26`
- **证据：** `ci-fast` 只执行手工文件列表；顺序为 integration 在前、unit 在后，恰好掩盖 H3 的循环导入。`tests/security`、`tests/performance`、完整 `tests/e2e` 未由该门禁直接执行。仓库现有 433 个 pytest test/class 定义，同时仍保留 77 个 `scripts/test-*.py` 双轨入口。
- **影响：** 测试通过依赖集合顺序；新增测试可能不会自动进入门禁；影子脚本与 pytest 迁移容易产生两套夹具和不同环境语义。
- **建议：** CI 至少增加 clean-process unit、integration、security、performance 分组；用 marker/目录收集替代手工文件清单；为保留的脚本测试建立明确退役清单和唯一包装方向。

### M4. 全仓质量基线与“维护范围”基线差距过大

**整改状态：已建立可执行治理。** 已删除 3 个无效脚本绑定和 1 个性能夹具无效绑定，修复维护代码/测试的可机械问题；全仓 `ruff check . --select F` 通过，`server/src` 全规则清零。新增 `scripts/check-ruff-budgets.py` 与 `config/ruff-budgets.json`，按层、按规则码限制剩余历史债务：scripts 为 C901=27、E402=37、E501=311、I001=10；tests 为 C901=2；migrations 为 C901=2、E501=31、I001=3、S105=1。新规则默认预算为 0，旧债务只能减少、不能增长。

- **位置：** `Makefile:38`、`pyproject.toml:18`
- **证据：** 维护范围 Ruff 通过；`ruff check .` 报告 447 项。多数为旧迁移/脚本的 E501、E402、I001 和复杂度，但也包含真实信号，例如 `scripts/validate-registry.py` 未使用变量、`server/auth_guards.py` 格式漂移、测试夹具未使用变量。
- **影响：** 新旧代码边界不断固化，重构区域可能永久逃逸统一静态规则；安全类告警容易淹没在格式噪声中。
- **建议：** 不要一次性机械修完 447 项；先将 Ruff 按 `server/src`、迁移、脚本、测试分层，建立每层不增长预算；优先处理 F、S、循环复杂度，再逐批清理格式。

### M5. 测试环境和运行环境通过全局 `os.environ`/缓存共享，隔离脆弱

**整改状态：已修复共享 fixture。** autouse fixture 保存并恢复所有 `INFINITAS_*` 环境变量，同时继续清理 settings/engine/session factory 缓存；OpenAPI 生成也不再依赖宿主环境。

- **位置：** `tests/conftest.py:24`、多份 integration fixture
- **证据：** 多个 fixture 直接写全局环境变量，autouse fixture 只清缓存、不恢复环境。应用导入又会立即创建全局 `app` 并连接数据库。不同测试顺序可改变设置、模型导入与数据库指向。
- **影响：** 单测、全集和手工子集可能得出不同结果；并行执行风险高；失败难以归因。
- **建议：** 统一使用 `monkeypatch` 或 `make_test_env`，fixture teardown 恢复环境；避免模块导入时创建有副作用的全局应用；为跨文件测试启用随机顺序或至少运行独立进程分组。

## 4. 低优先级发现

### L1. 构建会改写已跟踪的中间 CSS 文件

**整改状态：已修复。** 中间文件改为 `build/static/input.purged.css`，由 `.gitignore` 排除；Tailwind 只读取该路径，构建契约测试防止回退。

- **位置：** `server/static/css/.input.purged.css`、`package.json`
- **证据：** `npm run build` 会重写该中间文件和 asset hashes；该中间文件被 Git 跟踪。本轮验证产生的新增中间文件差异已精确还原。
- **影响：** 正常验证会污染工作树，增加生成物冲突和无意义 diff。
- **建议：** 中间文件放入 `build/` 或缓存目录并忽略；只跟踪真正部署所需的最终 CSS/哈希，CI 验证最终生成物可重复。

### L2. 前端视觉系统过度依赖渐变、霓虹、发光和模糊

**整改状态：已修复。** 通用 `.kawaii-card`、控制台卡片、导航、搜索下拉、用户面板和认证遮罩改为实体表面与轻量阴影；暗色 toast/badge 去 glow。首页 `hero-card` 与主 CTA 仍保留品牌渐变和强调层级。

- **位置：** `server/static/css/input.css:79`、`server/static/css/input.css:1292`
- **类别：** UI anti-pattern / Maintainability
- **结论：** AI Slop 检查为 **Partial**。主题有明确 kawaii 方向，并非无意图模板，但暗色模式大量使用 neon cyan/pink、渐变卡片、glow shadow、backdrop blur，多个组件重复同一视觉语言。
- **影响：** 信息层级可能被装饰效果稀释，CSS 维护成本和低端设备合成成本上升。
- **建议：** 保留少量品牌性高的 hero/CTA 效果，其余表格、管理页和状态组件回归实体色与边框；用性能面板和对比度工具验证，而非仅凭静态判断。

## 5. 正向发现

- 双消费者架构在代码中真实存在：UI 为服务端 HTML，CLI 直接调用 JSON API；本轮没有把“前端未调用”误判为死代码。
- CLI 核心路径与当前 OpenAPI 一致；`/api/v1/access/me`、authoring、release、exposure、review 路径均有对应路由。
- 认证基础措施较完整：生产环境强 secret/allowed hosts、加密且签名的 session cookie、CSRF 双提交、HttpOnly/SameSite、token hash、scope 与 release access 检查。
- artifact download 对 `resolve()` 后路径使用 `relative_to(root)`，具备目录穿越防护。
- UI 静态实现包含 WAI-ARIA tabs、modal focus trap、Escape/Tab 键处理、可见 focus、`prefers-reduced-motion`、暗色主题和响应式断点。
- 维护范围 Ruff 通过；Mypy 对 206 个源文件无错误；governance 分组 352 项全部通过。
- 空库可升级到 Alembic head；从 head 降至明确不可逆的 private-first cutover 边界后可以再次升级到 head。
- 前端 `npm run build` 成功。

## 6. 验证矩阵

| 检查 | 结果 | 说明 |
|---|---|---|
| Maintained Ruff | Pass | 维护范围无错误 |
| Full-repo functional Ruff | Pass | `ruff check . --select F` 无错误；历史格式/复杂度债务保留分层治理 |
| Layered Ruff budgets | Pass | `server/src` clean；scripts/tests/migrations 按规则码未超过预算 |
| Mypy | Pass | 208 source files，无 error |
| Unit tests | Partial Pass | 848 passed、4 deselected；4 项同步 FastAPI 请求受沙箱 AnyIO worker-thread 阻塞 |
| Focused remediation tests | Pass | 20 passed：凭据、恢复安全、模型导入、OpenAPI、构建/进程/视觉契约 |
| Performance tests | Pass | 15 passed |
| Security tests | 环境阻塞 | 28 项全部依赖同步 `TestClient`；纯 AnyIO worker 探针亦超时 |
| Alembic upgrade/check | Pass | 2 passed；空库升级后无 metadata drift |
| OpenAPI check | Pass | schema current，检查模式不写文件 |
| Frontend build | Pass | PurgeCSS/Tailwind/hash 生成成功；中间文件位于 ignored build 目录 |
| Full E2E | 未验证 | 当前沙箱禁止绑定本地 socket，fixture 报 `PermissionError` |
| Dependency vulnerability audit | 未验证 | `pip-audit` 需要访问 PyPI，当前网络受限 |

## 7. 建议整改顺序

| 阶段 | 工作 | 验收条件 |
|---|---|---|
| 立即 | 修复 H1/H2，拆分 session 与 API token | web login 前后 Agent token 均有效；自动 token 可认证 |
| 立即 | 修复 H5 的 tar 安全提取 | traversal/symlink/hardlink 恶意样本全部拒绝 |
| 本迭代 | 重构模型基础模块，消除 H3 | 所有领域模块在干净解释器中可独立导入 |
| 本迭代 | 对齐 ORM 与 Alembic，处理循环 FK | `alembic check` 无新操作、无排序警告 |
| 本迭代 | 修复性能测试与 CI 分组 | unit/integration/security/performance 独立进程全绿 |
| 后续 | OpenAPI 无副作用 check、生成物治理 | `--check` 不写文件、不建持久库、不播种用户 |
| 后续 | 分层降低 Ruff 债务 | 每层基线不增长，优先消除 F/S 类问题 |

## 8. 不应作为缺陷处理的事项

- `/api/v1/me`、`/api/v1/access/me`、`/api/v1/auth/me` 等同名概念属于不同消费者/上下文，不是天然路由冲突。
- UI 未直接调用的 JSON API 仍由 `infinitas registry` 和 Agent 脚本消费，不是死代码。
- `src/infinitas_skill/` 中没有 Python import 引用的函数可能是 CLI 或 shell 动态入口，不能仅据静态 import 图删除。
- 20260329_0004 明确声明不可逆；`downgrade base` 在此停止是已编码的迁移政策，不按本轮缺陷统计。
