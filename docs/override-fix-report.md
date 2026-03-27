# 🔧 CSS 覆盖问题修复报告

## 🐛 发现的问题

### 1. `.skill-name` 重复定义 (已修复)
```
❌ 问题：
- layout-kawaii.html (第2003行): .skill-name { overflow-wrap: anywhere; }
- index-kawaii.html (第453行): .skill-name { 完整字体样式 }

冲突结果：
- layout-kawaii.html 中的定义会覆盖 index-kawaii.html 中的定义
- 导致技能名称只保留 overflow-wrap，丢失字体、大小、颜色等样式

✅ 修复：
- 删除 layout-kawaii.html 中的 .skill-name 定义
- 保留 index-kawaii.html 中的完整样式
```

---

## 📊 问题分析

### 重复定义类型
| 类型 | 说明 | 修复策略 |
|------|------|----------|
| **选择器重名** | 同名选择器在不同文件定义 | 合并或删除重复 |
| **样式覆盖** | 父模板样式覆盖子模板 | 调整选择器特异性 |
| **硬编码颜色** | 子模板使用 rgba() 颜色 | 添加深色模式覆盖 |

### 检测方法
```bash
# 检查两个文件中重复的选择器
grep -E "^\s*\.[a-zA-Z0-9_-]+\s*\{" file1.html | sort > /tmp/f1.txt
grep -E "^\s*\.[a-zA-Z0-9_-]+\s*\{" file2.html | sort > /tmp/f2.txt
comm -12 /tmp/f1.txt /tmp/f2.txt  # 显示共同的选择器
```

---

## ✅ 修复详情

### 删除的代码
```css
/* layout-kawaii.html - 已删除 */
.skill-name {
  overflow-wrap: anywhere;
}
```

### 保留的代码
```css
/* index-kawaii.html - 保留 */
.skill-name {
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--kawaii-ink);
  margin-bottom: 0.2rem;
  overflow-wrap: anywhere;  /* 可以添加到此处 */
}
```

---

## 🛡️ 预防措施

### 1. 命名规范
```css
/* 好的做法 - 前缀区分 */
.index-skill-name { }      /* index-kawaii.html 专用 */
.layout-skill-name { }     /* layout-kawaii.html 专用 */
.global-skill-name { }     /* 全局通用 */

/* 或者使用 BEM 命名 */
.skill__name { }           /* 基础组件 */
.skill__name--index { }    /* index 页面变体 */
```

### 2. 文件组织
```
server/templates/
├── layout-kawaii.html      # 只定义全局通用样式
├── index-kawaii.html       # 只定义首页特有样式
├── components/             # 建议：组件级样式
│   ├── _skill-card.html
│   ├── _console-card.html
│   └── _quick-pill.html
```

### 3. 自动化检查
```bash
#!/bin/bash
# check-duplicate-selectors.sh

for file1 in server/templates/*.html; do
  for file2 in server/templates/*.html; do
    if [ "$file1" != "$file2" ]; then
      dups=$(comm -12 <(grep -oE "^\s*\.[a-zA-Z0-9_-]+\s*\{" "$file1" | sort -u) <(grep -oE "^\s*\.[a-zA-Z0-9_-]+\s*\{" "$file2" | sort -u))
      if [ -n "$dups" ]; then
        echo "发现重复选择器在 $file1 和 $file2:"
        echo "$dups"
        echo "---"
      fi
    fi
  done
done
```

---

## 🧪 测试验证

### 手动测试清单
- [x] 技能卡片名称显示正常
- [x] 字体样式正确应用
- [x] 深色模式下样式正常
- [x] 其他组件未受影响

### 自动化测试建议
```python
# 示例：检查 CSS 选择器重复
def check_duplicate_selectors(template_files):
    all_selectors = {}
    for file in template_files:
        with open(file) as f:
            content = f.read()
            selectors = re.findall(r'^\s*(\.[a-zA-Z0-9_-]+)\s*\{', content, re.M)
            for sel in selectors:
                if sel in all_selectors:
                    print(f"警告: {sel} 在 {file} 和 {all_selectors[sel]} 中都定义")
                all_selectors[sel] = file
```

---

## 📁 修改文件
- `server/templates/layout-kawaii.html`
  - 删除重复的 `.skill-name` 定义 (第2003-2005行)

---

*修复完成时间: 2026-03-27*
*版本: Kawaii Theme v2.5*
