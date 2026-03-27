# 🎨 主题迁移指南

## 从原主题切换到 Kawaii 二次元主题

---

## 📊 主题对比

| 特性 | 原主题 | Kawaii 主题 |
|------|--------|-------------|
| **风格** | 极简商务风 | 二次元萌系 |
| **主色调** | 蓝灰色系 | 樱花粉 x 天空蓝 |
| **圆角** | 1.3rem (21px) | 1.75rem (28px) |
| **字体** | Baskerville + Avenir | Quicksand + Nunito |
| **图标** | 无 | Emoji |
| **动效** | 淡入上浮 | 弹性弹跳 + 漂浮 |
| **装饰** | 极简线条 | 彩虹渐变 + 光晕 |
| **深色模式** | 不支持 | 夜樱主题 ✅ |

---

## 🚀 快速迁移

### 方法 1：直接替换（推荐）

1. 备份原文件
```bash
cd /Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/templates
cp layout.html layout.html.bak
cp index.html index.html.bak
```

2. 应用新主题
```bash
cp layout-kawaii.html layout.html
cp index-kawaii.html index.html
```

3. 重启服务器即可看到新主题

### 方法 2：主题切换功能

如果你想保留两个主题并支持切换，修改 `app.py`：

```python
from fastapi import Request, Cookie
from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def index(request: Request, theme: str = Cookie(default="default"), db: Session = Depends(get_db)):
    context = _build_home_context(settings, db)
    context['request'] = request
    
    # 根据 cookie 选择模板
    template_name = 'index-kawaii.html' if theme == 'kawaii' else 'index.html'
    return templates.TemplateResponse(template_name, context)

# 添加主题切换 API
@app.post("/api/theme/{theme_name}")
def set_theme(theme_name: str, response: Response):
    """切换主题: default | kawaii"""
    response.set_cookie(key="theme", value=theme_name, max_age=365*24*60*60)
    return {"theme": theme_name}
```

在页面上添加切换按钮：

```html
<button onclick="setTheme('kawaii')">🎀 二次元模式</button>
<button onclick="setTheme('default')">💼 商务模式</button>

<script>
async function setTheme(theme) {
  await fetch(`/api/theme/${theme}`, { method: 'POST' });
  location.reload();
}
</script>
```

---

## 🎨 自定义主题

### 修改主色调

在 `layout-kawaii.html` 的 `:root` 中修改：

```css
:root {
  /* 改为你喜欢的颜色 */
  --kawaii-primary: #ff85a2;        /* 粉色 */
  --kawaii-secondary: #7ec8e3;      /* 蓝色 */
  
  /* 其他辅助色 */
  --kawaii-mint: #98fb98;           /* 绿色 */
  --kawaii-lavender: #e6e6fa;       /* 紫色 */
  --kawaii-coral: #ffa07a;          /* 橙色 */
}
```

### 推荐的配色方案

#### 方案 1：薄荷绿系（清新风）
```css
--kawaii-primary: #98ddca;        /* 薄荷绿 */
--kawaii-secondary: #a8e6cf;      /* 浅绿 */
--kawaii-primary-deep: #7bc4a8;   /* 深绿 */
```

#### 方案 2：薰衣草系（优雅风）
```css
--kawaii-primary: #d4a5d4;        /* 淡紫 */
--kawaii-secondary: #b8a9c9;      /* 紫灰 */
--kawaii-primary-deep: #b085b0;   /* 深紫 */
```

#### 方案 3：珊瑚橙系（活力风）
```css
--kawaii-primary: #ffa69e;        /* 珊瑚 */
--kawaii-secondary: #ff7e79;      /* 橙红 */
--kawaii-primary-deep: #ff6b6b;   /* 深红 */
```

---

## 🧩 组件使用手册

### 基础卡片

```html
<div class="kawaii-card">
  <h3>标题</h3>
  <p>内容</p>
</div>
```

### 按钮

```html
<!-- 主按钮 -->
<button class="kawaii-button kawaii-button--primary">
  <span>🚀</span> 主操作
</button>

<!-- 次要按钮 -->
<button class="kawaii-button kawaii-button--secondary">
  次要操作
</button>

<!-- 幽灵按钮 -->
<button class="kawaii-button kawaii-button--ghost">
  边框按钮
</button>

<!-- 带漂浮动画 -->
<button class="kawaii-button kawaii-button--primary float">
  漂浮按钮
</button>
```

### 标签

```html
<span class="kawaii-tag kawaii-tag--pink">🌸 粉色标签</span>
<span class="kawaii-tag kawaii-tag--blue">💧 蓝色标签</span>
<span class="kawaii-tag kawaii-tag--green">🌿 绿色标签</span>
```

### 徽章

```html
<span class="kawaii-badge kawaii-badge--success">✅ 成功</span>
<span class="kawaii-badge kawaii-badge--pending">⏳ 等待中</span>
<span class="kawaii-badge kawaii-badge--running">🔄 运行中</span>
<span class="kawaii-badge kawaii-badge--error">❌ 错误</span>
```

### 输入框

```html
<input class="kawaii-input" placeholder="输入内容..." />
```

### 工具提示

```html
<button class="kawaii-button kawaii-tooltip" data-tooltip="点击复制">
  📋 复制
</button>
```

---

## 🎭 动画工具类

| 类名 | 效果 |
|------|------|
| `.animate-in` | 弹性入场动画 |
| `.float` | 持续漂浮 |
| `.sparkle` | 闪烁效果 |
| `.stagger-1` ~ `.stagger-5` | 交错延迟 |

### 使用示例

```html
<!-- 入场动画 -->
<div class="kawaii-card animate-in">内容</div>

<!-- 交错入场 -->
<div class="kawaii-card animate-in stagger-1">第一</div>
<div class="kawaii-card animate-in stagger-2">第二</div>
<div class="kawaii-card animate-in stagger-3">第三</div>

<!-- 漂浮动画 -->
<div class="float">🎈 漂浮元素</div>

<!-- 闪烁 -->
<span class="sparkle">✨</span>
```

---

## 📱 页面布局示例

### 仪表盘布局

```html
<div class="dashboard-grid">
  <!-- Hero 区 -->
  <section class="hero-section animate-in">
    <div class="hero-card kawaii-card">
      <!-- Hero 内容 -->
    </div>
  </section>
  
  <!-- 状态卡片网格 -->
  <div class="status-grid">
    <div class="status-item kawaii-card animate-in stagger-1">
      <div class="status-icon">📊</div>
      <div class="status-value">42</div>
      <div class="status-label">技能数量</div>
    </div>
    <!-- 更多状态... -->
  </div>
  
  <!-- 功能卡片网格 -->
  <div class="console-grid">
    <a href="/page" class="console-card kawaii-card">
      <div class="console-emoji">🎯</div>
      <h3>功能名称</h3>
      <p>功能描述</p>
    </a>
    <!-- 更多卡片... -->
  </div>
</div>
```

### 列表页布局

```html
<div class="list-page">
  <div class="page-header kawaii-card animate-in">
    <h1>📦 提交队列</h1>
    <input class="kawaii-input" placeholder="🔍 搜索..." />
  </div>
  
  <div class="data-table kawaii-card animate-in stagger-1">
    <table class="kawaii-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>#001</td>
          <td>示例技能</td>
          <td><span class="kawaii-badge kawaii-badge--success">✅</span></td>
          <td>
            <button class="kawaii-button kawaii-button--ghost" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;">
              查看
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
```

---

## 🎯 实用技巧

### 1. 减小按钮尺寸

```html
<button class="kawaii-button kawaii-button--primary" 
        style="padding: 0.5rem 1rem; font-size: 0.8rem;">
  小按钮
</button>
```

### 2. 卡片内边距调整

```html
<div class="kawaii-card" style="padding: 1rem;">
  紧凑卡片
</div>
```

### 3. 自定义彩虹渐变

```css
.my-card::before {
  background: linear-gradient(90deg, 
    #ff85a2,  /* 粉 */
    #ffd93d,  /* 黄 */
    #6bcf7f,  /* 绿 */
    #4d96ff   /* 蓝 */
  );
}
```

### 4. 添加 Emoji 动画

```html
<span style="display: inline-block; animation: bounce 1s infinite;">
  🎉
</span>

<style>
@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}
</style>
```

---

## 🔧 故障排除

### 问题 1：字体加载慢

**解决方案**：使用 `font-display: swap`

```css
@font-face {
  font-family: 'Quicksand';
  font-display: swap;  /* 先显示后备字体 */
  /* ... */
}
```

### 问题 2：动画太卡

**解决方案**：添加 `will-change` 或禁用复杂动效

```css
.kawaii-card {
  will-change: transform;
}

/* 或在移动端简化 */
@media (max-width: 720px) {
  .kawaii-card:hover {
    transform: none;  /* 移除悬停动效 */
  }
}
```

### 问题 3：深色模式不生效

**检查**：确保系统深色模式开启，或手动设置

```css
/* 强制深色模式 */
html[data-theme="dark"] {
  color-scheme: dark;
  /* 覆盖深色变量 */
}
```

---

## 📚 扩展阅读

- [设计系统完整文档](./kawaii-theme-design.md)
- [Google Fonts - Quicksand](https://fonts.google.com/specimen/Quicksand)
- [Google Fonts - Nunito](https://fonts.google.com/specimen/Nunito)
- [CSS Cubic Bezier 工具](https://cubic-bezier.com/)

---

## 💝 反馈与贡献

如果你在使用过程中有任何建议或发现了问题，欢迎反馈！

**设计原则**：保持可爱，但绝不牺牲可用性。
