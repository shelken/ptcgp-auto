# Roadmap: PTCGP Auto - 通知中心功能

## Overview

为 PTCGP Auto Web 管理界面添加通知中心功能。用户可从首页右上角铃铛图标打开右侧滑出面板，浏览通知列表（未读优先），支持滚动加载、批量标记已读，并可展开查看 Markdown 格式的通知详情。项目分两阶段交付：先建立稳定的面板基础设施，再添加详情展示与渲染能力。

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: 基础面板与核心交互** - 铃铛入口、滑出面板、通知列表、滚动加载、标记已读、无障碍支持 (completed 2026-02-23)
- [ ] **Phase 2: 详情展示与 Markdown 渲染** - 点击展开详情、Markdown 渲染、XSS 防护

## Phase Details

### Phase 1: 基础面板与核心交互
**Goal**: 用户可以打开通知面板、浏览通知列表、批量标记已读，面板支持完整的关闭机制和无障碍访问
**Depends on**: Nothing (first phase)
**Requirements**: ENTR-01, ENTR-02, ENTR-03, PANEL-01, PANEL-02, PANEL-03, PANEL-04, PANEL-05, PANEL-06, LIST-01, LIST-02, LIST-03, LIST-04, LIST-05, INTR-04, INTR-05, A11Y-01, A11Y-02
**Success Criteria** (what must be TRUE):
  1. 用户点击首页铃铛图标可打开右侧滑出的通知面板
  2. 面板显示通知列表（未读优先），每条通知显示标题和相对时间，未读/已读有视觉区分
  3. 用户可通过点击外部区域、按 ESC 键、点击关闭按钮三种方式关闭面板
  4. 用户点击"全部已读"按钮后，所有未读通知被标记，badge 数量实时更新为 0
  5. 滚动到列表底部时自动加载更多通知，显示 loading 状态
  6. 面板支持键盘 Tab 导航，焦点被正确捕获和恢复
**Plans:** 5 plans

Plans:
- [x] 01-01-PLAN.md — 面板基础设施（HTML 结构、CSS 样式、滑出动画、滚动锁定）
- [x] 01-02-PLAN.md — 铃铛入口与 Badge（图标、未读数量、点击触发）
- [x] 01-03-PLAN.md — 通知列表（列表渲染、未读/已读样式、滚动加载）
- [x] 01-04-PLAN.md — 标记已读交互（全部已读按钮、badge OOB 更新）
- [x] 01-05-PLAN.md — 关闭机制与无障碍（外部点击、ESC 关闭、焦点陷阱）

### Phase 2: 详情展示与 Markdown 渲染
**Goal**: 用户可以点击通知展开详情，查看 Markdown 渲染后的完整内容
**Depends on**: Phase 1
**Requirements**: INTR-01, INTR-02, INTR-03, MD-01, MD-02
**Success Criteria** (what must be TRUE):
  1. 用户点击通知项可展开查看完整详情内容
  2. 通知详情支持 Markdown 渲染（链接、格式化、代码块等）
  3. 点击通知项后该通知自动标记为已读
  4. 展开的详情区域可以收起折叠
**Plans**: TBD

Plans:
- [ ] 02-01: 详情展开/收起交互（点击展开、再次点击收起）
- [ ] 02-02: Markdown 渲染与 XSS 防护（marked.js + DOMPurify 集成）

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. 基础面板与核心交互 | 5/5 | Complete | 2026-02-23 |
| 2. 详情展示与 Markdown 渲染 | 0/2 | Not started | - |

---
*Roadmap created: 2026-02-23*
*Total phases: 2*
*Total v1 requirements: 22*
