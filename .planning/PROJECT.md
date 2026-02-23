# PTCGP Auto v2

## What This Is

PTCGP Auto 是一个面向 Pokemon TCG Pocket 的自动化托管系统，采用任务队列 + 多设备调度架构，支持多账号日常任务执行、社交协作与数据同步。系统同时提供 FastAPI + HTMX Web 管理界面，用于查看运行状态、账号资源、卡牌记录和运营配置。v1 代码保留为 legacy，当前主线为 `src/ptcgp_auto_v2/`。

## Core Value

稳定地以最少人工介入管理多账号自动化任务，确保任务可执行、可观测、可恢复。

## Requirements

### Validated

- ✓ 多账号任务调度与执行框架（Scheduler/Executor/TaskRegistry）— existing
- ✓ 设备池与批量账号执行能力（空闲设备分配、任务分发、异常恢复）— existing
- ✓ 10+ 自动化任务能力（开包、领奖励、礼物、得卡挑战、送卡、换卡、好友管理、账号同步等）— existing
- ✓ 识别链路（OCR + YOLO + 感知哈希）与页面检测机制 — existing
- ✓ 数据持久化模型与仓储层（账号、任务、卡牌、社交、通知等）— existing
- ✓ Web 管理后台（记录、任务、管理、好友、交换、通知等路由与页面）— existing
- ✓ 通知中心（铃铛入口、滑出面板、列表加载、批量/单条已读、Markdown 安全渲染）— v2.0.0

### Active

- [ ] 规划 v2.x 下一里程碑目标（功能范围、优先级、验收标准）
- [ ] 提升 Web 运营效率（通知筛选/搜索/深链接等）
- [ ] 持续优化自动化稳定性与可观测性（失败恢复、告警、调试体验）

### Out of Scope

- 推翻现有 v2 调度架构重写为全新系统 — 当前阶段以增量演进为主
- 非 macOS 平台适配 — OCR 与当前自动化链路依赖 Apple Vision Framework

## Context

### Current State

已完成并发布里程碑 **v2.0.0 Notification Center**，当前项目处于 Brownfield 持续迭代状态：

- 交付范围：2 个阶段，8 个计划项
- 核心能力：铃铛入口、滑出面板、未读优先列表、无限滚动、批量已读、详情展开、Markdown 安全渲染、键盘无障碍
- 归档文档：`.planning/milestones/v2.0.0-ROADMAP.md`、`.planning/milestones/v2.0.0-REQUIREMENTS.md`
- 全局能力基线已由 `.planning/codebase/` 建立（STACK/ARCHITECTURE/STRUCTURE 等）

### Next Milestone Goals

1. 基于全局产品目标定义下一里程碑（而非单功能局部优化）
2. 明确 v2.x 的用户可感知价值与阶段验收真值
3. 在不破坏既有任务稳定性的前提下持续迭代 Web 管理能力

### 现有系统

项目采用 Python + FastAPI + HTMX，核心分层为 `core / tasks / services / infra / db / web / config`。系统同时保留 v1 legacy（`src/ptcgp_auto/`）与 v2 主线（`src/ptcgp_auto_v2/`）。

- CLI 入口: `main_v2.py`
- 调度入口: `src/ptcgp_auto_v2/main.py`
- Web 入口: `src/ptcgp_auto_v2/web/app.py`

### 技术栈

- 后端: Python 3.12 + FastAPI + SQLModel + SQLite
- 自动化: uiautomator2 + ADB + 页面检测
- 识别: Apple Vision OCR + YOLO + OpenCV + 感知哈希
- 前端: HTMX + ES6 Modules + Jinja2
- 样式: CSS 变量驱动主题，禁止硬编码颜色
- 交互: `data-action` 委托模式，禁止内联事件

## Constraints

- **主题兼容**: 必须使用 CSS 变量，支持所有主题（Retro/Luxury/Organic 等）
- **事件规范**: 禁止 `onclick/onchange` 内联事件，使用 `data-action` 委托
- **滚动锁定**: 打开面板时锁定 body 滚动
- **HTMX 替换**: 面板内容刷新统一替换外层容器
- **架构边界**: `core/` 与 `infra/` 不承载业务细节
- **时间规范**: 数据库与业务时间统一使用本地时间（localtime）

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| v2 采用任务队列 + 调度器架构 | 支撑多账号多设备并发与可恢复执行 | ✓ Good（existing） |
| 保留 v1 为 legacy，v2 单独演进 | 降低重构风险，保证迁移连续性 | ✓ Good（existing） |
| 右侧滑出面板 | 类似 macOS 通知中心，用户熟悉 | ✓ Good（v2.0.0） |
| 滚动加载而非分页 | 更好的连续体验 | ✓ Good（v2.0.0） |
| 点击展开详情 | 一站式查看 markdown 内容 | ✓ Good（v2.0.0） |
| Markdown 客户端渲染 + DOMPurify 白名单 | 平衡可读性与安全性 | ✓ Good（v2.0.0） |

---
*Last updated: 2026-02-23 after v2.0.0 milestone*
