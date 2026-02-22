---
phase: 01-基础面板与核心交互
plan: 02
subsystem: ui
tags: [notification, bell, badge, htmx, action-handler, css-animation]

# Dependency graph
requires:
  - phase: 01-01
    provides: 通知面板容器 HTML 结构、DrawerManager JS 模块
provides:
  - 铃铛入口 HTML 按钮
  - Badge 未读数量显示（HTMX 加载）
  - toggle-notification-panel 动作分发
  - Badge 动画样式与辅助方法
affects: [notification-list, notification-badge-oob]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "data-action 事件委托模式"
    - "HTMX hx-trigger 多事件源（load + custom event）"
    - "CSS transform + opacity 过渡动画"

key-files:
  created: []
  modified:
    - src/ptcgp_auto_v2/web/templates/index.html
    - src/ptcgp_auto_v2/web/static/css/components/notification-panel.css
    - src/ptcgp_auto_v2/web/static/js/modules/action_handlers.js
    - src/ptcgp_auto_v2/web/static/js/modules/features/notification_panel.js

key-decisions:
  - "铃铛放置在主题选择器左侧（而非右侧语言区域）"
  - "Badge 颜色复用 .status-tone-failed 语义（红色系）"
  - "animateBadgeUpdate 方法供后续 01-04 OOB 更新使用"

patterns-established:
  - "新增 UI 入口必须使用 data-action 委托，禁止 onclick"

requirements-completed: [ENTR-01, ENTR-02, ENTR-03]

# Metrics
duration: 5min
completed: 2026-02-22
---
# Phase 1 Plan 2: 铃铛入口与 Badge Summary

**在首页 header 添加铃铛图标入口，显示未读通知数量 badge，点击触发面板 toggle**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-22T18:28:06Z
- **Completed:** 2026-02-22T18:33:35Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- 铃铛图标按钮已添加到 header 右上角（主题选择器左侧）
- Badge 通过 HTMX 加载未读数量，支持 load 和 notificationsUpdated 事件触发
- toggle-notification-panel 动作分发已接入 action_handlers.js
- Badge 动画样式（scale + opacity）与 animateBadgeUpdate 辅助方法已就绪

## Task Commits

Each task was committed atomically:

1. **Task 1: 添加铃铛图标入口到 header** - `b3aabb4` (feat)
2. **Task 2: 添加 toggle-notification-panel 动作分发** - `a17cdf3` (feat)
3. **Task 3: 实现 badge 动画效果** - `d9c5332` (feat)

**Version bump:** `a8fe430` (chore)

## Files Created/Modified

- `src/ptcgp_auto_v2/web/templates/index.html` - 添加铃铛按钮 HTML，更新静态资源版本
- `src/ptcgp_auto_v2/web/static/css/components/notification-panel.css` - 添加铃铛按钮和 Badge 样式
- `src/ptcgp_auto_v2/web/static/js/modules/action_handlers.js` - 导入 getNotificationDrawer 并添加动作分发
- `src/ptcgp_auto_v2/web/static/js/modules/features/notification_panel.js` - 添加 animateBadgeUpdate 辅助方法

## Decisions Made

- **铃铛位置**：放在主题选择器左侧而非语言区域，与用户设置相关功能归组
- **Badge 颜色**：复用现有 .status-tone-failed 红色系，无需新增 CSS 变量
- **动画方法导出**：animateBadgeUpdate 作为独立导出函数，便于后续模块调用

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 铃铛入口已就绪，点击可触发面板开关
- Badge 未读数量显示正常（复用已有 /notifications/count 接口）
- 后续计划可以复用 animateBadgeUpdate 实现 OOB badge 更新

## Verification

可通过浏览器验证：
1. 首页右上角显示铃铛图标（主题选择器左侧）
2. 有未读通知时铃铛旁显示红色 badge 数字
3. 无未读通知时 badge 隐藏
4. 点击铃铛，面板从右侧滑出
5. 再次点击铃铛，面板滑回隐藏

---
*Phase: 01-基础面板与核心交互*
*Completed: 2026-02-22*

## Self-Check: PASSED

- SUMMARY.md 文件已创建
- 所有任务提交存在：b3aabb4, a17cdf3, d9c5332, a8fe430
