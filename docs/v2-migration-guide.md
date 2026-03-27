# V2 UI 迁移指南

## 状态

本文件已归档。`2026-03-27` 起，历史 `/v2` 实验页已经退役，不再提供独立模板或静态 CSS 资产。

## 当前行为

- `GET /v2` 返回 `307` 并重定向到 `/`
- 线上唯一 UI 壳为 `server/templates/layout-kawaii.html`
- 首页使用 `server/templates/index-kawaii.html`
- 控制台页与登录页均已接入 kawaii 壳

## 已移除的历史资产

- `server/templates/layout_v2.html`
- `server/templates/index_v2.html`
- `server/static/css/variables.css`
- `server/static/css/base.css`
- `server/static/css/components.css`

## 如果你在查历史方案

这些内容只存在于 git 历史中：

- `/v2` 独立实验页
- `layout_v2.html` / `index_v2.html`
- 基于独立 CSS bundle 的 V2 设计

请不要再根据旧文档恢复这些文件或重新接线 `/v2` 首页入口。
