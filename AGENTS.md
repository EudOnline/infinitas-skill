# Agent 工作指南：infinitas-skill

## 项目架构核心认知

### 双消费者架构（Dual-Consumer Architecture）

本项目采用**双消费者**设计，必须始终区分以下两类消费者：

| 消费者 | 入口 | 数据格式 | 用途 |
|--------|------|---------|------|
| **人类用户** | `server/ui/routes.py` | `HTMLResponse`（服务端渲染页面） | 浏览器访问的 Web UI |
| **Agent / CLI** | `server/api/*.py`<br>`server/modules/*/router.py` | JSON / `response_model` | 编程接口，`infinitas` CLI 调用 |

**关键规则：**

1. **前端 UI 没有调用某个 API ≠ 该 API 是死代码**。Agent 通过 CLI（`src/infinitas_skill/cli/`）或脚本直接调用这些 JSON API。
2. **同一概念存在多个 `/me` 或 `/skills` 端点 ≠ 路由冲突**。例如：
   - `/api/v1/me` — Agent API 获取当前用户身份
   - `/api/auth/me` — 浏览器探测会话认证状态
   - `/api/background/me` — 获取用户背景设置
   - `/api/v1/access/me` — 获取访问控制上下文
3. **`src/infinitas_skill/` 中的函数未被其他 Python 模块导入 ≠ 死代码**。这些函数大多是 CLI 命令实现（`infinitas registry`、`infinitas release` 等），或被 `.sh` 脚本通过动态导入使用。

### 目录职责

```
server/ui/routes.py          → 人类用户的页面路由（HTML）
server/api/*.py              → 人类/Agent 通用的 API 路由（JSON）
server/modules/*/router.py   → 领域模块的 API 路由（JSON）
src/infinitas_skill/cli/     → CLI 入口，调用上述 JSON API
src/infinitas_skill/*/       → CLI 库函数、脚本库
scripts/*.sh / *.py          → Shell/Python 脚本，可能动态导入 src/ 函数
skills/active/*/             → 真实技能定义，被 Agent 消费
```

### 审计与代码审查注意事项

**在进行代码审计或寻找 Bug 时：**

- ✅ 检查 `HTMLResponse` 路由的模板变量是否完整
- ✅ 检查 JSON API 的 `response_model` 与 `schemas/*.schema.json` 是否一致
- ✅ 检查 Agent CLI 调用的 API 路径是否与实际路由匹配
- ❌ 不要将"前端未使用的 API"视为死代码或 Bug
- ❌ 不要将跨模块同名函数（如 `load_json`、`from_model`）视为冲突，它们可能是独立的工具函数
- ❌ 不要将 CLI 专用函数标记为"未使用"

### 认证方式差异

| 路由类型 | 认证方式 | 说明 |
|---------|---------|------|
| UI 路由 (`server/ui/`) | Cookie + CSRF Token | 浏览器会话认证 |
| API 路由 (`server/api/`, `server/modules/*/router.py`) | Bearer Token / Credential | Agent/程序认证 |
| Registry 文件 (`/registry/*`) | Registry Read Token | 业务层认证（`UnauthorizedError` → 401） |
| Share Link (`/api/share-links/*/resolve`) | Share Password | 匿名访问，通过 payload 密码认证 |

---

*本指南用于防止 AI Agent 在审计、重构或 Bug 修复时误解项目的双消费者架构。*
