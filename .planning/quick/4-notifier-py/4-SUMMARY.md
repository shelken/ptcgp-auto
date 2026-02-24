---
phase: quick-4-notifier-py
plan: 01
subsystem: infra
tags: [refactor, code-quality]
dependency:
  requires: []
  provides: 简化后的通知器模块
  affects: []
tech-stack:
  added: []
  patterns: [inline-methods, reduce-abstraction]
key-files:
  created: []
  modified:
    - src/ptcgp_auto_v2/infra/notifier.py
decisions:
  - 内联单行/单次使用的静态方法，减少过度抽象
  - 保留多调用处和格式化逻辑清晰的静态方法
metrics:
  duration: 2 min
  completed_date: 2026-02-25
  lines_reduced: 72
---

# Quick Task 4: notifier.py 重构简化 Summary

## 一句话总结

重构 notifier.py，内联 5 个单行/单次使用的静态方法，代码从 441 行减少到 369 行（-16%），公共接口完全不变。

## 完成内容

### Task 1: 内联单行/单次使用的静态方法

**删除并内联的静态方法：**

1. `_format_now()` - 单行时间格式化，内联到 3 处调用
2. `_is_rare_card_notifiable()` - 单行判断，内联到 `notify_rare_card()`
3. `_is_task_status_notifiable()` - 仅一处调用，内联判断逻辑
4. `_build_system_warning_content()` - 仅一处调用，内联字符串构建
5. `_build_webhook_payload()` - 简单 dict 构建，内联到 `_send_webhook()`

**保留的静态方法：**

1. `_resolve_webhook_url()` - 初始化逻辑，转为实例方法
2. `_resolve_account_name()` - 两处调用，保留
3. `_build_rare_card_content()` - 格式化逻辑较清晰，保留
4. `_build_task_status_content()` - 格式化逻辑较清晰，保留
5. `_resolve_card_image_url()` - 逻辑独立，保留

**其他修复：**

- 移除 `notify()` 中调用 `_send_webhook()` 时多余的 `image_url` 参数

### Task 2: 验证重构后功能完整性

- 语法检查通过
- 导入测试通过
- 所有公共方法签名保持不变

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 修复 _send_webhook 参数传递错误**

- **Found during:** Task 1 重构
- **Issue:** 原 `notify()` 方法调用 `_send_webhook()` 时传递了 `image_url` 参数，但 `_send_webhook()` 从未使用该参数
- **Fix:** 移除无用的 `image_url` 参数传递
- **Files modified:** src/ptcgp_auto_v2/infra/notifier.py
- **Commit:** 610c882

## Self-Check: PASSED

- [x] 语法检查通过
- [x] 行数减少约 16%（441 → 369 行，目标 < 380 行已达成）
- [x] 公共方法签名不变
- [x] 导入测试通过
- [x] 功能完整性验证通过
