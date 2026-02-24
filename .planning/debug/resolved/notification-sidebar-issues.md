---
status: resolved
trigger: "检查通知边栏功能。首先全部已读功能���正常，当有未读时，全部已读功能也无法点击。第二，当点击一条已读时，右上角的铃铛的数量没有相应变化。"
created: 2026-02-25T10:30:00
updated: 2026-02-25T11:00:00
---

## Current Focus

hypothesis: 已修复
test: 运行测试通过
expecting: 功能正常
next_action: 归档

## Symptoms

expected: 
1. 当有未读通知时，全部已读按钮应该可点击，点击后标记所有为已读
2. 当点击单条通知展开时，右上角铃铛数字应该减少

actual:
1. 全部已读按钮在有未读时仍然无法点击
2. 点击单条通知展开后，右上角铃铛数字没有变化

errors: 无错误消息
reproduction: 
1. 打开通知面板，查看全部已读按钮状态
2. 展开一条未读通知，观察右上角铃铛数字
started: 发现问题

## Eliminated

- hypothesis: 后端 mark_all_as_read 未实现
  evidence: 检查代码发现后端逻辑正常
  timestamp: 2026-02-25T10:33:00

## Evidence

- timestamp: 2026-02-25T10:30:00
  checked: notification_panel.html 第 14-16 行
  found: 按钮 disabled 条件为 `unread_count is not defined or unread_count == 0`
  implication: 模板可能未正确获取 unread_count

- timestamp: 2026-02-25T10:32:00
  checked: notification_panel.js 第 474 行
  found: 单条已读触发 `document.dispatchEvent(new CustomEvent('notificationRead'))`
  implication: 事件名可能不匹配

- timestamp: 2026-02-25T10:33:00
  checked: index.html 第 54-57 行
  found: badge 监听 `hx-trigger="load, notificationsUpdated from:body"`
  implication: **问题2根因：事件名不匹配！触发的是 notificationRead，监听的是 notificationsUpdated**

- timestamp: 2026-02-25T10:40:00
  checked: index_service.py build_index_context 函数
  found: 函数返回的 context 中没有 unread_count 变量
  implication: **问题1根因：首屏渲染时 unread_count 未定义，导致按钮被禁用**

- timestamp: 2026-02-25T10:42:00
  checked: index.html 第 633 行
  found: `{% include 'partials/notification_panel.html' %}` 直接嵌入模板
  implication: 首屏渲染时没有经过后端 API，直接使用 index_context，缺少 unread_count

## Resolution

root_cause: 
- 问题1：build_index_context 未提供 unread_count 变量，导致首屏渲染时全部已读按钮被禁用
- 问题2：单条已读触发 notificationRead 事件，但 badge 监听 notificationsUpdated 事件，事件名不匹配

fix: 
- 问题1：在 build_index_context 中添加 unread_count 变量（index_service.py）
- 问题2：将 notification_panel.js 中的 notificationRead 改为 notificationsUpdated，并在 body 上触发

verification: 
- 58 个测试通过，1 个失败是之前就存在的问题
- 静态资源版本号更新到 5.04

files_changed: 
- src/ptcgp_auto_v2/web/services/index_service.py
- src/ptcgp_auto_v2/web/static/js/modules/features/notification_panel.js
- src/ptcgp_auto_v2/web/templates/index.html
