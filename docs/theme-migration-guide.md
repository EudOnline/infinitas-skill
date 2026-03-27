# 主题迁移指南

## 状态

`2026-03-27` 起，托管 UI 已完成切换，`layout-kawaii.html` 是唯一的线上模板壳。旧 `layout.html` / `index.html` 已移除，本文件不再提供“双主题并存”迁移步骤。

## 当前结构

- 首页模板：`server/templates/index-kawaii.html`
- 通用壳：`server/templates/layout-kawaii.html`
- 控制台页：`/submissions`、`/reviews`、`/jobs`
- 登录页：`server/templates/login-kawaii.html`
- `/v2`：保留为重定向入口，返回 `307 -> /`

## 当前主题能力

- 亮色模式和深色模式共用 `layout-kawaii.html`
- 语言切换通过 `lang` 查询参数控制
- 主题切换通过前端 `localStorage` 记录 `kawaii-color-scheme`

## 后续维护原则

- 不再复制 `layout-kawaii.html` 覆盖旧模板文件
- 不再恢复 `index.html` / `layout.html` 作为回退方案
- 新页面默认接入 `layout-kawaii.html`
- 视觉调整优先修改现有 kawaii design tokens 和共享区块，而不是新增第二套样式体系

## 归档说明

如果需要查看旧主题替换思路，请通过 git 历史查阅 2026-03-27 之前的版本。本仓库当前主分支不再支持旧主题并行运行。

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
html[data-color-scheme="dark"] {
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
