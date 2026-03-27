# 💻 重构实施代码示例

## 具体实现参考代码

---

## 1. 组件化模板结构

### 1.1 基础布局组件

```html
<!-- templates/layouts/base.html -->
<!DOCTYPE html>
<html lang="zh-CN" data-theme="{{ theme|default('default') }}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title|default('infinitas skill') }} 🎯</title>
  
  <!-- 字体 -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  
  <!-- 样式 -->
  <link rel="stylesheet" href="/static/css/base.css">
  <link rel="stylesheet" href="/static/css/components.css">
  {% block extra_css %}{% endblock %}
</head>
<body>
  <!-- 搜索栏（全局 Sticky） -->
  {% include 'components/search_bar.html' %}
  
  <!-- 主导航 -->
  {% include 'components/navigation.html' %}
  
  <!-- 主内容 -->
  <main class="main-container">
    {% block content %}{% endblock %}
  </main>
  
  <!-- Toast 容器 -->
  <div id="toast-container" class="toast-container"></div>
  
  <!-- 脚本 -->
  <script src="/static/js/app.js" type="module"></script>
  {% block extra_js %}{% endblock %}
</body>
</html>
```

### 1.2 技能卡片组件

```html
<!-- templates/components/skill_card.html -->
<article class="skill-card" data-skill-id="{{ skill.id }}">
  <div class="skill-card__header">
    <span class="skill-card__icon">{{ skill.icon|default('🎯') }}</span>
    <div class="skill-card__meta">
      {% if skill.rating %}
      <span class="skill-card__rating">⭐ {{ skill.rating }}</span>
      {% endif %}
    </div>
  </div>
  
  <h3 class="skill-card__name">{{ skill.name }}</h3>
  <p class="skill-card__version">{{ skill.version }}</p>
  <p class="skill-card__summary">{{ skill.summary }}</p>
  
  <div class="skill-card__tags">
    {% for tag in skill.tags|slice(0, 3) %}
    <span class="tag tag--{{ tag.type|default('default') }}">{{ tag.name }}</span>
    {% endfor %}
  </div>
  
  <div class="skill-card__footer">
    <button class="btn btn--primary" onclick="useSkill('{{ skill.id }}')">
      🚀 使用
    </button>
    <a href="/skills/{{ skill.id }}" class="btn btn--ghost">
      详情
    </a>
  </div>
</article>
```

### 1.3 搜索栏组件

```html
<!-- templates/components/search_bar.html -->
<div class="search-bar-wrapper" id="search-wrapper">
  <div class="search-bar">
    <span class="search-bar__icon">🔍</span>
    <input 
      type="text" 
      class="search-bar__input" 
      placeholder="搜索技能、标签、命令... (Cmd+K)"
      id="global-search"
      autocomplete="off"
    >
    <button class="search-bar__filter" title="筛选">
      ⚙️
    </button>
  </div>
  
  <!-- 搜索建议下拉 -->
  <div class="search-dropdown" id="search-dropdown" hidden>
    <div class="search-dropdown__section">
      <h4>技能</h4>
      <div class="search-results" id="skill-results"></div>
    </div>
    <div class="search-dropdown__section">
      <h4>命令</h4>
      <div class="search-results" id="command-results"></div>
    </div>
  </div>
</div>
```

---

## 2. CSS 架构重构

### 2.1 基础变量系统

```css
/* static/css/base.css */

:root {
  /* 字体 */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
  
  /* 圆角 */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 24px;
  --radius-full: 9999px;
  
  /* 阴影 */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
  --shadow-glow: 0 0 20px rgb(99 102 241 / 0.3);
  
  /* 过渡 */
  --transition-fast: 150ms ease;
  --transition-base: 250ms ease;
  --transition-slow: 350ms ease;
}

/* 默认主题（现代商务） */
:root {
  --color-primary: #6366f1;
  --color-primary-light: #818cf8;
  --color-primary-dark: #4f46e5;
  
  --color-bg: #ffffff;
  --color-surface: #f8fafc;
  --color-surface-elevated: #ffffff;
  
  --color-text: #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted: #94a3b8;
  
  --color-border: #e2e8f0;
  --color-border-strong: #cbd5e1;
}

/* 深色主题 */
[data-theme="dark"] {
  --color-primary: #818cf8;
  --color-primary-light: #a5b4fc;
  --color-primary-dark: #6366f1;
  
  --color-bg: #0f172a;
  --color-surface: #1e293b;
  --color-surface-elevated: #334155;
  
  --color-text: #f1f5f9;
  --color-text-secondary: #cbd5e1;
  --color-text-muted: #64748b;
  
  --color-border: #334155;
  --color-border-strong: #475569;
}

/* Kawaii 二次元主题 */
[data-theme="kawaii"] {
  --color-primary: #ff85a2;
  --color-primary-light: #ffb6c1;
  --color-primary-dark: #ff6b8a;
  
  --color-bg: #fff9fb;
  --color-surface: #ffffff;
  --color-surface-elevated: #fff0f5;
  
  --color-text: #4a4a6a;
  --color-text-secondary: #7a7a9a;
  --color-text-muted: #a0a0b8;
  
  --color-border: #ffd1dc;
  --color-border-strong: #ffb6c1;
  
  --radius-lg: 20px;
  --radius-xl: 28px;
}
```

### 2.2 组件样式

```css
/* static/css/components.css */

/* ===== 技能卡片 ===== */
.skill-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
  transition: all var(--transition-base);
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.skill-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, 
    var(--color-primary), 
    var(--color-primary-light)
  );
  opacity: 0;
  transition: opacity var(--transition-base);
}

.skill-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-primary-light);
}

.skill-card:hover::before {
  opacity: 1;
}

.skill-card__icon {
  font-size: 2rem;
  line-height: 1;
}

.skill-card__name {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-text);
  margin: 0.75rem 0 0.25rem;
}

.skill-card__version {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.skill-card__summary {
  font-size: 0.875rem;
  color: var(--color-text-secondary);
  margin: 0.75rem 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ===== 搜索栏 ===== */
.search-bar-wrapper {
  position: sticky;
  top: 0;
  z-index: 100;
  padding: 1rem 0;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  max-width: 600px;
  margin: 0 auto;
  padding: 0.75rem 1rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  transition: all var(--transition-fast);
}

.search-bar:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgb(99 102 241 / 0.1);
}

.search-bar__input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 0.9375rem;
  color: var(--color-text);
  outline: none;
}

.search-bar__input::placeholder {
  color: var(--color-text-muted);
}

/* ===== 标签 ===== */
.tag {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: var(--radius-full);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
}

.tag--primary {
  background: rgb(99 102 241 / 0.1);
  border-color: rgb(99 102 241 / 0.2);
  color: var(--color-primary-dark);
}

.tag--success {
  background: rgb(34 197 94 / 0.1);
  border-color: rgb(34 197 94 / 0.2);
  color: rgb(21 128 61);
}

/* ===== 按钮 ===== */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.625rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn--primary {
  background: var(--color-primary);
  color: white;
}

.btn--primary:hover {
  background: var(--color-primary-dark);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.btn--ghost {
  background: transparent;
  border-color: var(--color-border);
  color: var(--color-text-secondary);
}

.btn--ghost:hover {
  background: var(--color-surface);
  border-color: var(--color-border-strong);
}

/* ===== Toast 通知 ===== */
.toast-container {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.toast {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  animation: toast-in 300ms ease;
}

.toast--success {
  border-left: 3px solid #22c55e;
}

.toast--error {
  border-left: 3px solid #ef4444;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* ===== 看板 ===== */
.kanban {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
}

.kanban__column {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: 1rem;
}

.kanban__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--color-border);
}

.kanban__title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text);
}

.kanban__count {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  background: var(--color-bg);
  border-radius: var(--radius-full);
  color: var(--color-text-secondary);
}

.kanban__items {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 100px;
}

.kanban__item {
  padding: 1rem;
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: grab;
  transition: all var(--transition-fast);
}

.kanban__item:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
```

---

## 3. JavaScript 功能实现

### 3.1 核心应用逻辑

```javascript
// static/js/app.js

// ===== Toast 通知系统 =====
class ToastManager {
  constructor() {
    this.container = document.getElementById('toast-container');
  }

  show(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.innerHTML = `
      <span>${this.getIcon(type)}</span>
      <span>${message}</span>
    `;
    
    this.container.appendChild(toast);
    
    setTimeout(() => {
      toast.style.animation = 'toast-out 300ms ease forwards';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  getIcon(type) {
    const icons = {
      success: '✅',
      error: '❌',
      warning: '⚠️',
      info: 'ℹ️'
    };
    return icons[type] || icons.info;
  }

  success(msg) { this.show(msg, 'success'); }
  error(msg) { this.show(msg, 'error'); }
  warning(msg) { this.show(msg, 'warning'); }
  info(msg) { this.show(msg, 'info'); }
}

window.toast = new ToastManager();

// ===== 搜索功能 =====
class SearchManager {
  constructor() {
    this.input = document.getElementById('global-search');
    this.dropdown = document.getElementById('search-dropdown');
    this.skillResults = document.getElementById('skill-results');
    this.commandResults = document.getElementById('command-results');
    this.debounceTimer = null;
    
    this.init();
  }

  init() {
    // 输入监听
    this.input.addEventListener('input', (e) => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => {
        this.search(e.target.value);
      }, 150);
    });

    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        this.input.focus();
      }
      if (e.key === 'Escape') {
        this.close();
      }
    });

    // 点击外部关闭
    document.addEventListener('click', (e) => {
      if (!e.target.closest('#search-wrapper')) {
        this.close();
      }
    });
  }

  async search(query) {
    if (!query.trim()) {
      this.close();
      return;
    }

    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      const data = await response.json();
      this.render(data);
      this.open();
    } catch (err) {
      console.error('Search failed:', err);
    }
  }

  render(data) {
    // 渲染技能结果
    this.skillResults.innerHTML = data.skills?.map(skill => `
      <a href="/skills/${skill.id}" class="search-result">
        <span class="search-result__icon">${skill.icon || '🎯'}</span>
        <div class="search-result__info">
          <div class="search-result__name">${skill.name}</div>
          <div class="search-result__desc">${skill.summary}</div>
        </div>
        <span class="search-result__badge">${skill.version}</span>
      </a>
    `).join('') || '<div class="search-empty">无匹配技能</div>';

    // 渲染命令结果
    this.commandResults.innerHTML = data.commands?.map(cmd => `
      <div class="search-result" onclick="copyToClipboard('${cmd.command}')">
        <span class="search-result__icon">⌨️</span>
        <div class="search-result__info">
          <div class="search-result__name">${cmd.name}</div>
          <code class="search-result__code">${cmd.command}</code>
        </div>
      </div>
    `).join('') || '<div class="search-empty">无匹配命令</div>';
  }

  open() {
    this.dropdown.hidden = false;
  }

  close() {
    this.dropdown.hidden = true;
  }
}

// ===== 主题切换 =====
class ThemeManager {
  constructor() {
    this.current = localStorage.getItem('theme') || 'default';
    this.apply(this.current);
  }

  apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    this.current = theme;
  }

  toggle() {
    const themes = ['default', 'dark', 'kawaii'];
    const next = themes[(themes.indexOf(this.current) + 1) % themes.length];
    this.apply(next);
    toast.success(`已切换到${this.getThemeName(next)}`);
  }

  getThemeName(theme) {
    const names = {
      default: '默认主题',
      dark: '深色主题',
      kawaii: '二次元主题'
    };
    return names[theme] || theme;
  }
}

window.themeManager = new ThemeManager();

// ===== 工具函数 =====
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success('已复制到剪贴板');
  } catch (err) {
    toast.error('复制失败');
  }
}

async function useSkill(skillId) {
  try {
    const response = await fetch(`/api/skills/${skillId}/use`, { method: 'POST' });
    const data = await response.json();
    toast.success('技能已就绪');
    // 可以添加更多反馈，比如显示命令预览
  } catch (err) {
    toast.error('使用技能失败');
  }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
  new SearchManager();
});
```

---

## 4. 后端 API 扩展

```python
# server/api/search.py

from fastapi import APIRouter, Query
from typing import List, Optional
from difflib import SequenceMatcher

router = APIRouter(prefix="/api", tags=["api"])

class SearchResult:
    def __init__(self, skills: list, commands: list):
        self.skills = skills
        self.commands = commands

@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=5, le=10)
) -> SearchResult:
    """
    全局搜索：支持技能名称、描述、标签、命令模糊匹配
    """
    results = {"skills": [], "commands": []}
    
    # 技能搜索（BM25 简化版）
    skills = await get_all_skills()
    scored_skills = []
    
    for skill in skills:
        score = 0
        q_lower = q.lower()
        
        # 名称匹配（权重最高）
        if q_lower in skill.name.lower():
            score += 10
        
        # 描述匹配
        if q_lower in skill.summary.lower():
            score += 5
            
        # 标签匹配
        for tag in skill.tags:
            if q_lower in tag.lower():
                score += 8
                
        # 模糊匹配
        score += SequenceMatcher(None, q_lower, skill.name.lower()).ratio() * 3
        
        if score > 0:
            scored_skills.append({"skill": skill, "score": score})
    
    # 排序取前 N
    scored_skills.sort(key=lambda x: x["score"], reverse=True)
    results["skills"] = [s["skill"] for s in scored_skills[:limit]]
    
    # 命令搜索
    commands = await get_all_commands()
    for cmd in commands:
        if q_lower in cmd.name.lower() or q_lower in cmd.command.lower():
            results["commands"].append(cmd)
    
    return results

@router.post("/skills/{skill_id}/use")
async def use_skill(skill_id: str, user: User = Depends(get_current_user)):
    """
    记录技能使用，返回使用命令
    """
    skill = await get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    # 记录使用统计
    await record_skill_usage(skill_id, user.id)
    
    return {
        "command": f"scripts/install-skill.sh {skill.name}",
        "skill": skill
    }

@router.get("/skills/{skill_id}/stats")
async def get_skill_stats(skill_id: str):
    """
    获取技能使用统计
    """
    stats = await get_usage_stats(skill_id)
    return {
        "total_installs": stats.total,
        "weekly_installs": stats.weekly,
        "rating": stats.avg_rating,
        "rating_count": stats.rating_count,
        "trend": stats.trend  # up/down/stable
    }
```

---

## 5. 快速启动模板

```html
<!-- templates/pages/dashboard.html -->
{% extends "layouts/base.html" %}

{% block content %}
<!-- 快速操作 -->
<section class="section">
  <h2 class="section__title">👋 欢迎回来，今天想做什么？</h2>
  <div class="quick-actions">
    <button class="quick-action" onclick="openModal('new-skill')">
      <span class="quick-action__icon">➕</span>
      <span class="quick-action__label">新建技能</span>
    </button>
    <button class="quick-action" onclick="syncRegistry()">
      <span class="quick-action__icon">🔄</span>
      <span class="quick-action__label">同步仓库</span>
    </button>
    <button class="quick-action" onclick="checkUpdates()">
      <span class="quick-action__icon">🔍</span>
      <span class="quick-action__label">检查更新</span>
    </button>
  </div>
</section>

<!-- 最近使用 -->
<section class="section">
  <div class="section__header">
    <h2 class="section__title">📌 最近使用</h2>
    <a href="/skills" class="link">查看全部 →</a>
  </div>
  <div class="skills-grid" data-scroll="horizontal">
    {% for skill in recent_skills %}
      {% include "components/skill_card.html" %}
    {% endfor %}
  </div>
</section>

<!-- 推荐技能 -->
<section class="section">
  <div class="section__header">
    <h2 class="section__title">⭐ 推荐技能</h2>
    <button class="btn btn--ghost btn--sm" onclick="refreshRecommendations()">
      ↻ 换一批
    </button>
  </div>
  <div class="skills-grid">
    {% for skill in recommended_skills %}
      {% include "components/skill_card.html" %}
    {% endfor %}
  </div>
</section>

<!-- 系统状态 -->
<section class="section">
  <h2 class="section__title">📊 系统状态</h2>
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-card__icon">🔒</div>
      <div class="stat-card__value">私有</div>
      <div class="stat-card__label">访问模式</div>
    </div>
    <div class="stat-card">
      <div class="stat-card__icon">📦</div>
      <div class="stat-card__value">{{ skill_count }}</div>
      <div class="stat-card__label">技能总数</div>
    </div>
    <div class="stat-card">
      <div class="stat-card__icon">⚡</div>
      <div class="stat-card__value">{{ pending_reviews }}</div>
      <div class="stat-card__label">待评审</div>
    </div>
  </div>
</section>
{% endblock %}
```

---

## 6. 迁移清单

```markdown
## 从旧版迁移到新版

### 文件迁移
- [ ] 备份原有 templates/
- [ ] 创建新的 layouts/ 结构
- [ ] 创建 components/ 组件库
- [ ] 迁移 static/css/ 到新架构
- [ ] 添加 static/js/ 模块

### 功能实现
- [ ] 添加搜索 API
- [ ] 添加使用统计 API
- [ ] 实现 Toast 通知
- [ ] 实现主题切换
- [ ] 添加键盘快捷键

### 页面重构
- [ ] 重构首页为 Dashboard
- [ ] 新建 Skills 列表页
- [ ] 新建 Skill 详情页
- [ ] 优化 Submissions 看板
- [ ] 优化 Reviews 页面

### 测试验证
- [ ] 测试所有页面渲染
- [ ] 测试搜索功能
- [ ] 测试主题切换
- [ ] 测试响应式布局
- [ ] 测试无障碍访问
```

---

这些代码示例展示了如何实现重构方案中的关键功能。你可以根据需要逐步采用这些实现。
