# Agent 工作指南：infinitas-skill

## 双消费者架构

本项目同时服务两类消费者，审计和重构时必须保持边界清晰。

| 消费者 | 入口 | 输出 | 认证 |
|---|---|---|---|
| 人类管理员 | `server/ui/routes/*.py` | 服务端渲染 HTML | Session Cookie + CSRF |
| Agent / CLI | `server/modules/*/router.py` | JSON + `response_model` | Bearer Token / Credential |

- UI 没有调用某个 JSON API，不代表该 API 是死代码；`src/infinitas_skill/` 中的 CLI 会直接消费这些接口。
- 相似的 `/me`、`/skills` 路径可能属于不同领域上下文，必须结合 router prefix、认证依赖和响应模型判断。
- CLI 命令处理函数和脚本动态入口不能只凭静态 import 次数判定为未使用。

## 领域所有权

| 领域 | 目录 | 主要职责 |
|---|---|---|
| identity | `server/modules/identity/` | 用户、主体、凭据、浏览器认证 |
| access | `server/modules/access/` | 授权、对象 Token、分享链接 |
| authoring | `server/modules/authoring/` | Skill 与不可变版本 |
| release | `server/modules/release/` | Release、Artifact、物化与证明 |
| exposure | `server/modules/exposure/` | 可见性与安装策略 |
| review | `server/modules/review/` | Review Case 与决策 |
| discovery | `server/modules/discovery/` | 搜索、发现与投影 |
| library | `server/modules/library/` | UI/API 共用的只读 Library 模型 |
| audit | `server/modules/audit/` | 活动与审计读取 |
| jobs | `server/modules/jobs/` | 后台任务模型 |

ORM 模型只能由所属领域定义。`server/model_registry.py` 仅负责一次性导入模型以填充 `Base.metadata`，不得成为业务导入中心。

## 边界规则

- `server/ui/` 和 JSON router 可以消费共享领域 service/read model，但不得互相导入。
- UI route 必须完整提供模板变量；JSON route 必须保持 `response_model`、OpenAPI 与 schema 一致。
- 事务由 `server.db.get_db()` 或 `session_scope()` 统一提交/回滚；领域 service 不自行 `commit()`。
- 应用导入和 `create_app()` 不初始化数据库。数据库迁移与 bootstrap 只在 FastAPI lifespan 中执行。
- 数据库只有一个当前 schema 和一个 `alembic/versions/0001_initial.py`。不添加数据搬迁、旧字段适配或历史迁移链。
- 当前运行时/平台支持判断属于产品能力；项目内部旧格式、旧命令、旧路由、旧 import 路径不保留适配层。

## 目录职责

```text
server/app.py                    FastAPI 组装
server/lifecycle.py              启动期初始化
server/db.py                     Engine、Session 与事务边界
server/ui/routes/*.py            人类管理员 HTML 路由
server/modules/*/router.py       Agent/CLI JSON API
src/infinitas_skill/cli/         单一 `infinitas` CLI 入口
src/infinitas_skill/*/           CLI 领域逻辑与仓库工具
skills/active/*/                 Agent 消费的技能定义
scripts/check-all.sh             完整验证入口
scripts/generate-openapi.py      OpenAPI 生成/检查
```

`scripts/` 顶层只允许四个构建或验证文件：

- `build-asset-hashes.js`
- `check-all.sh`
- `generate-openapi.py`
- `purgecss-run.js`

## 测试与质量门

所有自动化测试都位于 `tests/` 并由 pytest 执行。禁止恢复 `scripts/test-*.py` 双轨测试。

完成声明前运行：

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/infinitas_skill server
.venv/bin/pytest tests/unit tests/integration tests/security tests/performance
.venv/bin/pytest tests/e2e
.venv/bin/pytest tests/integration/test_alembic_metadata.py -q --override-ini=addopts=
.venv/bin/python scripts/generate-openapi.py --check
npm run build
git diff --check
```

维护性硬门：生产模块不超过 600 行、生产函数不超过 100 行、`server/static/css/input.css` 不超过 1000 行、顶层脚本严格等于上述四个文件。

## 审计检查表

- 检查 HTML 模板变量、Cookie/CSRF 流程和可访问性状态。
- 检查 CLI 使用的 API 路径、认证头、错误码和响应字段。
- 检查领域模型所有权、跨层 import、事务边界和 lifespan 副作用。
- 检查 `openapi.json`、JSON Schema、Pydantic response model 与实现是否同步。
- 不因前端未引用而删除 Agent API，不因跨模块同名函数而推断冲突。
