# PTCGP Auto - 通知中心功能

## What This Is

为 PTCGP Auto Web 管理界面添加通知中心功能。首页右上角铃铛图标显示未读数量，点击从右侧滑出面板展示通知列表，支持 markdown 渲染、滚动加载、展开详情等交互。

## Core Value

用户能快速查看未读通知，了解系统运行状态（稀有卡牌、任务状态、系统警告），无需跳转到管理页面。

## Requirements

### Validated

- ✓ 通知数据模型 (`Notification` with `is_read` field) — existing
- ✓ 通知仓储层 (`NotificationRepository`) — existing
- ✓ 通知基础设施 (`Notifier` + 企业微信推送) — existing
- ✓ 通知管理页面 (`/management/notifications`) — existing
- ✓ 未读数量接口 (`/notifications/count`) — existing
- ✓ 标记已读接口 (`mark-read`, `mark-all-read`) — existing

### Active

- [ ] 首页右上角铃铛图标 + 未读 badge
- [ ] 点击铃铛从右侧滑出通知中心面板
- [ ] 通知中心显示全部通知（未读优先）
- [ ] 滚动到底部自动加载更多
- [ ] 点击通知项展开详情 + 标记已读
- [ ] 提供「全部已读」按钮
- [ ] 支持 markdown 渲染

### Out of Scope

- 通知筛选功能 — 用户可直接跳转到管理页面筛选
- 通知分类标签 — 简化首次实现

## Context

### 现有系统

项目采用 FastAPI + HTMX 架构，Web 层遵循 routers/services/queries 分层。通知系统已有完整基础设施：

- 数据模型: `src/ptcgp_auto_v2/db/models/notification.py`
- 仓储: `src/ptcgp_auto_v2/db/repositories/notification_repository.py`
- 路由: `src/ptcgp_auto_v2/web/routers/notifications.py`
- 服务: `src/ptcgp_auto_v2/web/services/notification_service.py`

### 技术栈

- 前端: HTMX + ES6 Modules + Jinja2
- 样式: CSS 变量驱动主题，禁止硬编码颜色
- 交互: `data-action` 委托模式，禁止内联事件

## Constraints

- **主题兼容**: 必须使用 CSS 变量，支持所有主题（Retro/Luxury/Organic 等）
- **事件规范**: 禁止 `onclick/onchange` 内联事件，使用 `data-action` 委托
- **滚动锁定**: 打开面板时锁定 body 滚动
- **HTMX 替换**: 面板内容刷新统一替换外层容器

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 右侧滑出面板 | 类似 macOS 通知中心，用户熟悉 | — Pending |
| 滚动加载而非分页 | 更好的连续体验 | — Pending |
| 点击展开详情 | 一站式查看 markdown 内容 | — Pending |

---
*Last updated: 2026-02-23 after initialization*
