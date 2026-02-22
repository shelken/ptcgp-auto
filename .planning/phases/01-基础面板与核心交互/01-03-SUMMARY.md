---
phase: 01-基础面板与核心交互
plan: 03
subsystem: ui
tags: [notification, list, infinite-scroll, skeleton, htmx]

# Dependency graph
requires:
  - phase: 01-01
    provides: 通知面板容器 HTML 结构、CSS 样式、DrawerManager JS 模块
provides:
  - 通知列表 API 端点（/notifications/panel, /notifications/load-more）
  - 通知列表模板（notification_panel.html, notification_list_items.html）
  - 通知项样式（未读/已读区分、骨架屏、空状态）
affects: [notification-badge, notification-read]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HTMX revealed trigger 实现无限滚动"
    - "两阶段查询实现未读优先排序"
    - "CSS 骨架屏动画（prefers-reduced-motion 兼容）"

key-files:
  created:
    - src/ptcgp_auto_v2/web/templates/partials/notification_list_items.html
  modified:
    - src/ptcgp_auto_v2/web/routers/notifications.py
    - src/ptcgp_auto_v2/web/services/notification_service.py
    - src/ptcgp_auto_v2/web/templates/partials/notification_panel.html
    - src/ptcgp_auto_v2/web/static/css/components/notification-panel.css
    - src/ptcgp_auto_v2/web/static/js/modules/features/notification_panel.js
    - src/ptcgp_auto_v2/web/locales/zh_CN.json
    - src/ptcgp_auto_v2/web/locales/en.json

key-decisions:
  - "两阶段查询（先未读后已读）实现未读优先排序，避免复杂 SQL"
  - "后端预计算相对时间文本，前端仅负责 HTMX swap 后更新"

patterns-established:
  - "HTMX revealed once trigger 防止重复请求"
  - "骨架屏使用 CSS 动画，无 JS 依赖"
  - "时间字段统一使用相对时间 + 悬浮具体时间"

requirements-completed: [LIST-01, LIST-02, LIST-03, LIST-04, LIST-05]

# Metrics
duration: 15min
completed: 2026-02-23
---

# Phase 1 Plan 3: 通知列表渲染 Summary

**实现通知列表渲染，包括未读/已读视觉区分、HTMX 无限滚动加载、CSS 骨架屏和空状态展示**

## Performance

- **Duration:** 15 min
- **Started:** 2026-02-23T02:28:22Z
- **Completed:** 2026-02-23T02:43:15Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- 通知列表 API 端点已创建（/notifications/panel, /notifications/load-more）
- 未读优先排序逻辑已实现（两阶段查询）
- 通知列表模板已创建，支持 HTMX 无限滚动
- 骨架屏加载动画已添加（CSS 动画，prefers-reduced-motion 兼容）
- 面板打开时自动加载内容

## Task Commits

Each task was committed atomically:

1. **Task 1: 创建通知列表 API 端点** - `f9414df` (feat)
2. **Task 2: 创建通知列表模板** - `3aefc7c` (feat)
3. **Task 3: 面板打开时加载内容** - `6cda358` (feat)

## Files Created/Modified

- `src/ptcgp_auto_v2/web/routers/notifications.py` - 添加 /notifications/panel 和 /notifications/load-more API
- `src/ptcgp_auto_v2/web/services/notification_service.py` - 添加 build_notification_panel_context 和相对时间格式化
- `src/ptcgp_auto_v2/web/templates/partials/notification_panel.html` - 更新为支持 HTMX 动态加载
- `src/ptcgp_auto_v2/web/templates/partials/notification_list_items.html` - 新建，用于追加加载
- `src/ptcgp_auto_v2/web/static/css/components/notification-panel.css` - 增强通知项样式、骨架屏
- `src/ptcgp_auto_v2/web/static/js/modules/features/notification_panel.js` - 添加 loadPanelContent 方法
- `src/ptcgp_auto_v2/web/locales/zh_CN.json` - 添加 notification_all_loaded 翻译
- `src/ptcgp_auto_v2/web/locales/en.json` - 添加 notification_all_loaded 翻译

## Decisions Made

- **两阶段查询实现未读优先**：先查询未读通知，再查询已读通知，根据分页位置从两个结果中组合数据。这比复杂的 SQL 排序更直观。
- **后端预计算相对时间**：在服务层预计算相对时间文本（如"5分钟前"），前端仅负责 HTMX swap 后更新显示。
- **CSS 骨架屏动画**：使用纯 CSS 渐变动画实现骨架屏效果，无 JS 依赖，支持 prefers-reduced-motion。

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 通知列表渲染功能已就绪
- 下一步可以添加通知点击详情展开和全部已读功能

---

*Phase: 01-基础面板与核心交互*
*Completed: 2026-02-23*
