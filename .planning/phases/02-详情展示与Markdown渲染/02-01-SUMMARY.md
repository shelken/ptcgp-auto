---
phase: 02-详情展示与Markdown渲染
plan: 01
subsystem: ui
tags: [details, summary, accordion, toggle, read-mark, animation]

# Dependency graph
requires: []
provides:
  - 通知项详情展开/收起交互
  - 手风琴互斥模式
  - 乐观 UI 已读标记
affects: [02-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - details/summary 原生手风琴
    - ::details-content 平滑动画
    - capture 阶段事件监听

key-files:
  created: []
  modified:
    - src/ptcgp_auto_v2/web/templates/partials/notification_list_items.html
    - src/ptcgp_auto_v2/web/static/css/components/notification-panel.css
    - src/ptcgp_auto_v2/web/static/js/modules/features/notification_panel.js

key-decisions:
  - "使用 details/summary 原生元素实现手风琴，name 属性实现互斥"
  - "使用 calc-size() + ::details-content 实现平滑高度动画（Chrome 129+）"
  - "toggle 事件使用 capture 阶段监听（因为不冒泡）"

patterns-established:
  - "Pattern: 原生 HTML 元素优先（details/summary vs 自定义 JS 手风琴）"
  - "Pattern: 乐观 UI 更新 + 异步后端调用"

requirements-completed:
  - INTR-01
  - INTR-02
  - INTR-03

# Metrics
duration: 4 min
completed: 2026-02-22
---

# Phase 2 Plan 1: 详情展开/收起交互 Summary

**实现通知项点击展开详情功能，使用原生 details/summary 手风琴结构，支持乐观 UI 已读标记**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-22T20:13:30Z
- **Completed:** 2026-02-22T20:18:15Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- 使用 details/summary 实现原生手风琴互斥模式
- 添加平滑高度动画（calc-size + ::details-content）
- 实现点击展开时自动滚动到可见位置
- 实现乐观 UI 已读标记 + 异步后端调用

## Task Commits

Each task was committed atomically:

1. **Task 1: 修改通知项 HTML 为 details/summary 结构** - `2c82c17` (feat)
2. **Task 2: 添加 details 展开/收起动画样式** - `1bb2419` (feat)
3. **Task 3: 添加 toggle 事件处理和已读标记逻辑** - `41ab70c` (feat)

## Files Created/Modified

- `src/ptcgp_auto_v2/web/templates/partials/notification_list_items.html` - details/summary 手风琴结构
- `src/ptcgp_auto_v2/web/static/css/components/notification-panel.css` - 展开/收起动画样式
- `src/ptcgp_auto_v2/web/static/js/modules/features/notification_panel.js` - toggle 事件处理 + 已读标记

## Decisions Made

- 使用 details/summary 原生元素实现手风琴，通过 `name="notification-accordion"` 属性实现浏览器原生的互斥行为
- 使用 `calc-size(auto, size)` + `::details-content` 实现平滑高度动画，仅 Chrome 129+ 支持
- 提供 `@supports` 降级方案，旧浏览器功能正常但无动画
- toggle 事件使用 capture 阶段监听（第三个参数 `true`），因为 toggle 事件不冒泡
- 乐观 UI 更新在视觉反馈前执行，不等待后端响应

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 详情展开/收起交互完成，满足 INTR-01/INTR-02/INTR-03 需求
- Ready for Plan 02: Markdown 渲染

---
*Phase: 02-详情展示与Markdown渲染*
*Completed: 2026-02-22*
