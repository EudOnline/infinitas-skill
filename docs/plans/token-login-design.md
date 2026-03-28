# 🔐 Token 持久化登录设计方案

## 📋 需求分析

### 现状问题
- 控制台页面需要认证才能访问
- 每次重启浏览器后需要重新输入 token
- 没有便捷的首页登录入口

### 目标
- ✅ 首页添加 Token 输入框
- ✅ Token 保存在浏览器本地（30天有效期）
- ✅ 自动携带 token 访问 API
- ✅ 支持登出功能

---

## 🏗️ 架构设计

### 认证流程
```
┌─────────────────────────────────────────────────────────┐
│                     用户访问首页                          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ 检查 localStorage 中是否有 token                         │
│  - 有: 验证 token 有效性 → 显示已登录状态                 │
│  - 无: 显示 Token 输入框                                 │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ 用户输入 Token 点击登录                                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│ 后端验证 Token                                            │
│  - 有效: 保存到 localStorage (30天) + 显示用户信息        │
│  - 无效: 显示错误提示                                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🎨 UI 设计方案

### 未认证状态
```
┌─────────────────────────────────────────┐
│  ✨ 小二的私人 Agent 技能库               │
│  发现、试用、归档 技能即插即用            │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ 🔑 输入访问令牌                  │   │
│  │ ┌─────────────────────────────┐ │   │
│  │ │ sk-xxxxxxxxxxxxxxxxxxxxx    │ │   │
│  │ └─────────────────────────────┘ │   │
│  │     💡 Token 用于验证身份       │   │
│  │  [ 🔓 验证并保存 ]              │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### 已认证状态
```
┌─────────────────────────────────────────┐
│  ✨ 小二的私人 Agent 技能库               │
│  发现、试用、归档 技能即插即用            │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ 👤 已认证: lvxiaoer             │   │
│  │ 🕐 有效期: 30天                 │   │
│  │  [ 🚪 退出登录 ]                │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

---

## 🔧 技术实现

### 1. 前端存储方案
```javascript
// Token 管理类
class TokenManager {
  static STORAGE_KEY = 'infinitas_auth_token';
  static EXPIRY_KEY = 'infinitas_auth_expiry';
  
  // 保存 token (30天)
  static save(token) {
    const expiry = Date.now() + (30 * 24 * 60 * 60 * 1000);
    localStorage.setItem(this.STORAGE_KEY, token);
    localStorage.setItem(this.EXPIRY_KEY, expiry.toString());
  }
  
  // 获取 token
  static get() {
    const token = localStorage.getItem(this.STORAGE_KEY);
    const expiry = localStorage.getItem(this.EXPIRY_KEY);
    
    if (!token || !expiry) return null;
    
    // 检查过期
    if (Date.now() > parseInt(expiry)) {
      this.clear();
      return null;
    }
    
    return token;
  }
  
  // 清除 token
  static clear() {
    localStorage.removeItem(this.STORAGE_KEY);
    localStorage.removeItem(this.EXPIRY_KEY);
  }
  
  // 获取剩余天数
  static getRemainingDays() {
    const expiry = localStorage.getItem(this.EXPIRY_KEY);
    if (!expiry) return 0;
    
    const remaining = parseInt(expiry) - Date.now();
    return Math.max(0, Math.ceil(remaining / (24 * 60 * 60 * 1000)));
  }
}
```

### 2. API 请求自动携带 Token
```javascript
// 拦截所有 fetch 请求
const originalFetch = window.fetch;
window.fetch = async function(...args) {
  const [url, options = {}] = args;
  
  // 添加认证头
  const token = TokenManager.get();
  if (token) {
    options.headers = {
      ...options.headers,
      'Authorization': `Bearer ${token}`
    };
  }
  
  return originalFetch(url, options);
};
```

### 3. 登录表单组件
```html
<!-- 未认证状态 -->
<div class="auth-panel" id="auth-panel">
  <div class="auth-header">
    <span class="auth-icon">🔑</span>
    <span class="auth-title">输入访问令牌</span>
  </div>
  
  <div class="auth-form">
    <input 
      type="password" 
      id="token-input" 
      class="token-input" 
      placeholder="sk-xxxxxxxxxxxxxxxxxxxxx"
      autocomplete="off"
    />
    <p class="auth-hint">💡 Token 用于验证身份，可在个人设置中获取</p>
    <button class="kawaii-button kawaii-button--primary" id="login-btn">
      <span>🔓</span>
      <span>验证并保存</span>
    </button>
  </div>
  
  <div class="auth-error" id="auth-error" hidden>
    <span>❌</span> <span id="error-message">Token 无效</span>
  </div>
</div>

<!-- 已认证状态 -->
<div class="auth-panel auth-panel--logged-in" id="auth-panel-logged" hidden>
  <div class="auth-header">
    <span class="auth-icon">👤</span>
    <span class="auth-title">已认证</span>
  </div>
  
  <div class="auth-info">
    <p class="auth-user">用户名: <span id="auth-username">-</span></p>
    <p class="auth-expiry">有效期: <span id="auth-days">30</span> 天</p>
  </div>
  
  <button class="kawaii-button kawaii-button--ghost" id="logout-btn">
    <span>🚪</span>
    <span>退出登录</span>
  </button>
</div>
```

### 4. 后端 API
```python
# server/api/auth.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.db import get_db
from server.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenLoginRequest(BaseModel):
    token: str


class TokenLoginResponse(BaseModel):
    success: bool
    username: str | None = None
    error: str | None = None


@router.post("/login", response_model=TokenLoginResponse)
async def login(
    request: TokenLoginRequest,
    db: Session = Depends(get_db)
):
    """验证 token 并返回用户信息"""
    user = db.query(User).filter(User.token == request.token).one_or_none()
    
    if user is None:
        return TokenLoginResponse(
            success=False,
            error="无效的 Token"
        )
    
    return TokenLoginResponse(
        success=True,
        username=user.username
    )


@router.get("/me")
async def get_current_user_info(
    user: User = Depends(get_current_user)
):
    """获取当前登录用户信息"""
    return {
        "username": user.username,
        "role": user.role,
        "is_authenticated": True
    }
```

---

## 🎨 样式设计

### 登录面板样式
```css
.auth-panel {
  background: var(--kawaii-panel-soft);
  border: 2px solid var(--kawaii-line);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
  margin-top: 1rem;
}

.auth-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.auth-icon {
  font-size: 1.25rem;
}

.auth-title {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 1rem;
  color: var(--kawaii-ink);
}

.token-input {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 2px solid var(--kawaii-line);
  border-radius: var(--radius-md);
  background: var(--kawaii-surface);
  font-family: var(--font-mono);
  font-size: 0.9rem;
  color: var(--kawaii-ink);
  transition: all 200ms ease;
}

.token-input:focus {
  border-color: var(--kawaii-primary);
  box-shadow: 0 0 0 3px rgba(255, 105, 180, 0.15);
  outline: none;
}

.auth-hint {
  font-size: 0.8rem;
  color: var(--kawaii-ink-muted);
  margin: 0.5rem 0;
}

.auth-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  border-radius: var(--radius-md);
  color: var(--kawaii-danger);
  font-size: 0.9rem;
  margin-top: 0.75rem;
}

/* 深色模式 */
html[data-color-scheme="dark"] .auth-panel {
  background: rgba(35, 35, 60, 0.8);
  border-color: rgba(147, 112, 219, 0.4);
}

html[data-color-scheme="dark"] .token-input {
  background: rgba(30, 30, 50, 0.9);
  border-color: rgba(147, 112, 219, 0.35);
  color: #fff;
}
```

---

## 📱 响应式适配

```css
@media (max-width: 720px) {
  .auth-panel {
    padding: 1rem;
  }
  
  .token-input {
    font-size: 16px; /* 防止 iOS 缩放 */
  }
}
```

---

## 🔒 安全考虑

1. **Token 存储**
   - 使用 localStorage 而非 cookie（避免 CSRF 问题）
   - Token 设置 30 天过期时间
   - 支持用户主动登出清除

2. **传输安全**
   - 所有 API 请求通过 HTTPS
   - Token 放在 Authorization Header 中

3. **权限控制**
   - 后端仍需验证 token 有效性
   - 敏感操作需要额外验证

---

## 🚀 实施步骤

### Phase 1: 后端 API
1. 创建 `/api/auth/login` 端点
2. 创建 `/api/auth/me` 端点
3. 注册路由

### Phase 2: 前端组件
1. 添加 TokenManager 类
2. 修改 fetch 拦截器
3. 创建登录面板 UI
4. 添加到首页

### Phase 3: 样式适配
1. 添加 CSS 样式
2. 深色模式适配
3. 响应式适配

### Phase 4: 测试验证
1. 登录流程测试
2. Token 过期测试
3. 登出功能测试
4. 跨页面状态保持测试

---

## 📝 实现优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | Token 验证 API | 后端登录验证接口 |
| P0 | 登录面板 UI | 首页输入框和按钮 |
| P0 | Token 存储 | localStorage 保存和读取 |
| P1 | 自动携带 Token | fetch 拦截器 |
| P1 | 用户信息展示 | 显示用户名和有效期 |
| P2 | 登出功能 | 清除 Token 按钮 |
| P2 | 深色模式适配 | 霓虹风格登录面板 |

---

*设计完成时间: 2026-03-27*
*版本: v1.0*
