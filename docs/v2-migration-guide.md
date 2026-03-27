# 🚀 V2 UI 迁移指南

## 快速开始

### 1. 访问新版本

启动服务器后，访问新版本首页：
```
http://localhost:8000/v2
```

### 2. 功能对比

| 功能 | 旧版 (/) | 新版 (/v2) |
|------|----------|------------|
| 视觉设计 | 极简商务 | 现代卡片式 |
| 搜索功能 | ❌ 无 | ✅ 全局搜索 (Cmd+K) |
| 深色模式 | ❌ 无 | ✅ 一键切换 |
| 技能展示 | 表格 | 卡片网格 |
| 快速操作 | 较少 | 新建/同步/检查 |
| Toast通知 | ❌ 无 | ✅ 有 |
| 响应式 | 一般 | 优秀 |

### 3. 新功能详解

#### 🔍 全局搜索 (Cmd+K)
- 搜索技能名称、描述、标签
- 搜索常用命令
- 键盘导航 (↑↓ 选择, Enter 确认)
- 实时结果展示

#### 🌙 主题切换
- 默认主题：现代商务风
- 深色主题：夜猫子友好
- 二次元主题：可爱风格

#### 🎯 技能卡片
- Emoji 图标自动识别
- 版本号展示
- 评分系统
- 一键使用/查看详情

#### 📊 仪表盘
- 快捷操作区
- 最近使用
- 全部技能
- 系统状态统计
- 管理入口

### 4. 文件结构

```
server/
├── static/
│   ├── css/
│   │   ├── variables.css    # CSS变量 + 主题系统
│   │   ├── base.css         # 基础样式
│   │   └── components.css   # 组件样式
│   └── js/
│       └── app.js           # 核心JS功能
├── templates/
│   ├── layout_v2.html       # 新布局
│   ├── index_v2.html        # 新首页
│   └── ...                  # 旧模板保留
└── api/
    └── search.py            # 搜索API
```

### 5. 配置文件

#### 启用新主题为默认（可选）

修改 `server/app.py`，将 `/v2` 路由改为 `/`：

```python
# 将
@app.get('/', response_class=HTMLResponse)
def index(request: Request, ...):
    ...
    return templates.TemplateResponse('index.html', context)

# 改为
@app.get('/', response_class=HTMLResponse)
def index(request: Request, ...):
    ...
    return templates.TemplateResponse('index_v2.html', context)
```

#### 自定义主题颜色

编辑 `server/static/css/variables.css`：

```css
:root {
  --color-primary-500: #你的主色;
  --color-primary-600: #你的深色;
}
```

### 6. API 端点

#### 搜索 API
```
GET /api/search?q={query}&limit={limit}

Response:
{
  "skills": [...],
  "commands": [...],
  "total": 5
}
```

#### 使用技能 API
```
POST /api/skills/{skill_id}/use

Response:
{
  "command": "scripts/install-skill.sh ...",
  "skill": {...}
}
```

### 7. 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Cmd/Ctrl + K` | 打开搜索 |
| `Esc` | 关闭搜索/弹窗 |
| `↑/↓` | 搜索结果导航 |
| `Enter` | 确认选择 |

### 8. 浏览器支持

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- 支持 CSS 变量和 ES6+

### 9. 性能优化

- 字体使用 `font-display: swap`
- CSS 按需加载
- 搜索防抖 150ms
- 动画使用 `transform` 和 `opacity`

### 10. 回滚方案

如需回滚到旧版：
```bash
# 恢复备份
cd /Users/lvxiaoer/Documents/codeWork/infinitas-skill
cp .backup/templates/*.html server/templates/

# 重启服务器
```

---

## 后续优化建议

### Phase 3: 技能详情页
- [ ] 创建 `/skills/{id}` 详情页
- [ ] SKILL.md 渲染
- [ ] 使用统计图表

### Phase 4: 看板视图
- [ ] Submissions 看板
- [ ] Reviews 看板
- [ ] 拖拽操作

### Phase 5: 高级功能
- [ ] 使用分析
- [ ] 评分系统
- [ ] 通知中心
