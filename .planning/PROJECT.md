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
- ✓ 首页右上角铃铛图标 + 未读 badge — v2.0.0
- ✓ 点击铃铛从右侧滑出通知中心面板 — v2.0.0
- ✓ 通知中心显示全部通知（未读优先）— v2.0.0
- ✓ 滚动到底部自动加载更多 — v2.0.0
- ✓ 点击通知项展开详情 + 标记已读 — v2.0.0
- ✓ 提供「全部已读」按钮 — v2.0.0
- ✓ 支持 markdown 渲染并进行 XSS 过滤 — v2.0.0
- ✓ 面板可通过 ESC / 外部点击 / 关闭按钮关闭 — v2.0.0
- ✓ 焦点陷阱与焦点恢复无障碍能力 — v2.0.0

### Active

- [ ] 通知中心筛选能力（按类型/来源）
- [ ] 通知中心搜索能力（标题/内容关键字）
- [ ] 通知优先级与分组展示
- [ ] 通知详情中的卡片/任务深链接跳转

### Out of Scope

- 全量实时推送更新 — 当前以打开面板刷新为主，避免阅读打断
- 声音提醒 — 避免通知疲劳

## Context

### Current State

已完成并发布里程碑 **v2.0.0 Notification Center**：

- 交付范围：2 个阶段，8 个计划项
- 核心能力：铃铛入口、滑出面板、未读优先列表、无限滚动、批量已读、详情展开、Markdown 安全渲染、键盘无障碍
- 归档文档：`.planning/milestones/v2.0.0-ROADMAP.md`、`.planning/milestones/v2.0.0-REQUIREMENTS.md`

### Next Milestone Goals

1. 增强通知检索效率（筛选 + 搜索）
2. 增强通知语义表达（优先级、分组、状态）
3. 打通通知到业务页面的深链接跳转

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
| 右侧滑出面板 | 类似 macOS 通知中心，用户熟悉 | ✓ Good（v2.0.0） |
| 滚动加载而非分页 | 更好的连续体验 | ✓ Good（v2.0.0） |
| 点击展开详情 | 一站式查看 markdown 内容 | ✓ Good（v2.0.0） |
| Markdown 客户端渲染 + DOMPurify 白名单 | 平衡可读性与安全性 | ✓ Good（v2.0.0） |

---
*Last updated: 2026-02-23 after v2.0.0 milestone*
