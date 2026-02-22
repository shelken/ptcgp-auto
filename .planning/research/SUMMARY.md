# Project Research Summary

**Project:** Notification Center UI (通知中心)
**Domain:** Slide-out notification panel for HTMX-based web app
**Researched:** 2026-02-23
**Confidence:** HIGH

## Executive Summary

这是一个为现有 FastAPI + HTMX + Jinja2 + ES6 Modules 架构添加的右侧滑出通知中心面板。专家推荐采用 **纯 CSS transform 动画** + **HTMX revealed trigger 无限滚动** + **客户端 marked.js 渲染 Markdown** 的组合方案，完全复用项目现有的 `data-action` 事件委托模式和 CSS 变量主题系统。

**推荐实现路径：** 第一阶段实现基础面板（铃铛入口、滑出动画、通知列表、滚动锁定、焦点陷阱），第二阶段添加详情展开与 Markdown 渲染。核心技术决策：使用 marked.js（40KB）+ DOMPurify 做 XSS 防护，避免服务端渲染的复杂性；使用 `hx-trigger="revealed once"` 避免重复请求。

**关键风险：** 滚动穿透（需同时锁定 body 和 html）、HTMX 重复请求（revealed 触发器需 `once` 修饰符）、Badge 不同步（需 OOB swap）、焦点陷阱缺失（无障碍合规失败）。这些都有明确的预防策略，可在实现阶段规避。

## Key Findings

### Recommended Stack

通知中心采用轻量级客户端技术栈，无需引入构建工具或额外框架。核心决策：**客户端 Markdown 渲染**（marked.js 40KB）、**纯 CSS 动画**（transform + transition）、**HTMX revealed trigger** 实现无限滚动。完全复用现有 `data-action` 委托模式和 CSS 变量主题系统。

**Core technologies:**
- **marked.js** — 客户端 Markdown 渲染 — 轻量（40KB）、零后端依赖、与 HTMX 天然兼容
- **DOMPurify** — XSS 防护 — marked.js 不做 HTML sanitization，必须配合使用
- **CSS transform + transition** — 滑出动画 — GPU 加速、零 JS 依赖、与现有 modal.css 模式一致
- **HTMX revealed trigger** — 无限滚动 — 零 JS 代码、声明式、与现有架构一致

### Expected Features

通知中心遵循 macOS/iOS 原生模式，右侧滑出面板是最符合用户预期的交互方式。研究显示，用户对通知中心有明确的"默认预期"，缺少这些功能会让产品显得不完整。

**Must have (table stakes):**
- **Bell icon + unread badge** — 通用入口模式，用户默认在 header 右上角寻找
- **Slide-out panel from right** — macOS/iOS 原生模式，符合用户心智模型
- **Notification list (chronological, unread-first)** — 最新的在前，未读优先展示
- **Unread/read visual distinction** — 粗体 vs 常规，清晰视觉层级
- **Timestamp (relative time)** — "5 min ago"，提供事件上下文
- **Mark all as read** — 批量操作，多未读时用户期望的功能
- **Body scroll lock** — 打开面板时锁定背景滚动，避免 UX 混乱
- **Close mechanisms** — 点击外部 + ESC 键 + 关闭按钮，多通道关闭

**Should have (competitive):**
- **Infinite scroll / Load more** — 无缝浏览历史记录，scroll-to-bottom 触发
- **Expandable notification details** — 点击展开完整 Markdown 内容，保持上下文
- **Markdown rendering** — 富文本支持（链接、格式化、代码）

**Defer (v2+):**
- **Notification categories/grouping** — 按类型分组（系统、任务、卡牌），复杂度高
- **Search/filter** — 快速查找通知，需要额外 UI 和后端支持
- **Snooze notifications** — 专注时段暂停通知，复杂度高

### Architecture Approach

采用右侧滑出面板模式，复用现有 Modal 基础设施，通过 HTMX 局部更新实现通知列表的动态加载。遵循项目强制的 `data-action` 事件委托模式，避免内联 onclick。

**Major components:**
1. **notification_panel.html** — 面板模板（header + list content + footer），通过 HTMX 动态加载
2. **notification_panel.js** — DrawerManager 类，复用 modal.js 的 scroll lock 机制，实现焦点陷阱
3. **notification-panel.css** — 面板样式，使用现有 CSS 变量（`--card-bg`、`--border-color` 等）确保主题兼容

**HTMX Swap 策略:**
- 打开面板：`hx-target="#notification-panel" hx-swap="innerHTML"`
- 加载更多：`hx-target="#notification-list-content" hx-swap="beforeend"`
- Badge 更新：`hx-swap-oob="true"` (Out of Band)

### Critical Pitfalls

1. **滚动穿透 (Scroll Chaining)** — 打开面板时必须同时锁定 `body` 和 `document.documentElement`，否则背景页面会跟着滚动
2. **HTMX revealed 重复请求** — 使用 `hx-trigger="revealed once"` 防止快速滚动时触发多次请求，导致数据重复
3. **Badge 不同步** — 标记已读后 badge 必须通过 OOB swap 同步更新，否则显示与实际不符
4. **焦点陷阱缺失** — 必须实现 Tab 循环 + ESC 关闭 + aria-modal 属性，否则 WCAG 无障碍合规失败
5. **DOM 嵌套膨胀** — 使用 `hx-swap="innerHTML"` 而非默认的 `outerHTML`，避免容器嵌套

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: 基础面板与核心交互
**Rationale:** 必须先有稳定的面板容器和滚动机制，才能安全地添加内容加载功能。滚动锁定、焦点陷阱、z-index 层级这些基础设施如果延迟处理，后续修复成本高。
**Delivers:** 可打开/关闭的滑出面板，含通知列表、未读徽标、滚动锁定、键盘可访问
**Addresses:** Bell icon + badge, Slide-out drawer, Notification list, Unread/read distinction, Mark all as read, Body scroll lock, Close mechanisms (全部 P1 功能)
**Avoids:** 滚动穿透, 焦点陷阱缺失, Z-index 冲突, HTMX 重复请求, DOM 嵌套, 终止提示缺失

### Phase 2: 详情展示与 Markdown 渲染
**Rationale:** 依赖 Phase 1 的面板基础设施。Markdown 渲染涉及 XSS 防护，需要额外的安全审计，不适合混在基础阶段。
**Delivers:** 点击通知展开详情，Markdown 内容渲染，详情展开时布局稳定
**Uses:** marked.js + DOMPurify (from STACK.md)
**Implements:** Expandable details 组件，htmx:afterSwap 后 Markdown 渲染

### Phase Ordering Rationale

- **Phase 1 优先：** 滚动锁定、焦点陷阱、z-index 层级是基础设施，如果延迟处理会导致后续重构成本。用户即使没有 Markdown 详情也能完成基本的通知浏览和标记已读。
- **Phase 2 后置：** Markdown 渲染需要 XSS 防护（DOMPurify），布局抖动问题需要详情组件稳定后才能解决。这是增值功能，不影响核心流程。
- **分组依据：** Phase 1 是"让面板工作"，Phase 2 是"让内容更丰富"。遵循 MVP 原则，先验证基本交互。

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** Markdown 渲染的 XSS 防护策略需要具体测试，DOMPurify 配置是否足够严格

Phases with standard patterns (skip research-phase):
- **Phase 1:** 滑出面板、滚动锁定、焦点陷阱都有成熟的实现模式（Bootstrap Offcanvas、项目现有 modal.js），无需额外研究

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | marked.js、DOMPurify、CSS transform 都是成熟稳定的技术，官方文档详尽 |
| Features | HIGH | 多个权威设计系统（PatternFly、Carbon、Apple）提供了明确的功能规范 |
| Architecture | HIGH | HTMX + ES6 Modules + CSS 变量模式在项目中已验证，参考现有 modal.js 实现 |
| Pitfalls | HIGH | 每个陷阱都有明确的预防策略和验证方法，来源包括 MDN、CSS-Tricks、HTMX 官方 |

**Overall confidence:** HIGH

### Gaps to Address

- **Markdown 内容来源：** 研究假设通知内容存储为 Markdown 字符串，需在规划阶段确认实际数据结构
- **后端 API 设计：** `/notifications/panel`、`/notifications/count`、`/notifications/load-more` 接口响应格式需要在实现阶段细化
- **多标签页同步：** 研究未深入探讨多标签页打开时 badge 状态同步问题，可能需要 BroadcastChannel API

## Sources

### Primary (HIGH confidence)
- [marked.js 官方文档](https://marked.js.org/) — API 使用、安全警告
- [HTMX infinite scroll with revealed](https://dri.es/infinite-scroll-with-htmx) — revealed trigger 用法
- [PatternFly - Notification Drawer Design Guidelines](https://www.patternfly.org/components/notification-drawer/design-guidelines) — 企业级设计系统规范
- [Carbon Design System - Notifications](https://carbondesignsystem.com/patterns/notification-pattern) — IBM 设计系统通知模式
- [MDN: Stacking Context](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_positioned_layout/Understanding_z-index/Stacking_context) — Z-index 堆叠上下文
- 项目现有代码：`modal.js`、`action_handlers.js`、`modal.css` — 架构模式复用

### Secondary (MEDIUM confidence)
- [Smashing Magazine: Design Guidelines For Better Notifications UX](https://smashingmagazine.com/2025/07/design-guidelines-better-notifications-ux) — UX 设计规范
- [CSS-Tricks: A Primer on Focus Trapping](https://css-tricks.com/a-primer-on-focus-trapping/) — 焦点陷阱实现
- [HTMX GitHub Issue #463: Fast Scroll reveal failure](https://github.com/bigskysoftware/htmx/issues/463) — revealed 触发器问题
- [Bootstrap Offcanvas Documentation](https://getbootstrap.com/docs/5.3/components/offcanvas/) — 滑出面板参考

### Tertiary (LOW confidence)
- [Infinite Ajax Scroll: Common Pitfalls](https://infiniteajaxscroll.com/blog/common-pitfalls-infinite-scroll) — 无限滚动陷阱，非 HTMX 特定
- [Stack Overflow: HTMX revealed trigger issues](https://stackoverflow.com/questions/65961570/htmx-endless-scrolling-via-revealed-does-not-work) — 社区讨论，需验证

---
*Research completed: 2026-02-23*
*Ready for roadmap: yes*
