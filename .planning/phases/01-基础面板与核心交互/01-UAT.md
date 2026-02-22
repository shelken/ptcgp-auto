---
status: complete
phase: 01-基础面板与核心交互
source: 01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-05-SUMMARY.md
started: 2026-02-22T21:44:38Z
updated: 2026-02-22T21:49:02Z
---

## Current Test

[testing complete]

## Tests

### 1. 铃铛入口位置与可见性
expected: 在首页右上角（主题切换器左侧）可见铃铛按钮，且按钮可点击。
result: pass

### 2. 未读 Badge 显示与隐藏
expected: 有未读通知时显示红色数字 Badge；无未读时 Badge 隐藏。
result: pass

### 3. 铃铛开关面板动画
expected: 点击铃铛后面板从右侧滑出；再次点击铃铛面板滑回隐藏。
result: pass

### 4. 面板打开时背景滚动锁定
expected: 面板打开时页面背景不可滚动；关闭面板后恢复可滚动。
result: pass

### 5. 面板内容加载与空状态
expected: 打开面板会自动加载通知内容；无通知时展示空状态文案而非空白。
result: pass

### 6. 通知列表未读优先与视觉区分
expected: 未读通知优先出现在列表前部，并且未读项在视觉上与已读项有明显区分。
result: pass

### 7. 通知列表无限滚动
expected: 列表滚动到底部会自动加载更多通知；全部加载完后显示"已全部加载"提示。
result: pass

### 8. 全部已读功能
expected: 点击"全部已读"后，未读项变为已读样式，Badge 变为 0/隐藏，无未读时按钮禁用。
result: pass

### 9. 外部点击与 ESC 关闭
expected: 面板打开时，点击面板外区域会关闭；按 ESC 也会关闭。
result: pass

### 10. 键盘焦点陷阱与焦点恢复
expected: 面板内按 Tab/Shift+Tab 时焦点在面板内循环；关闭后焦点回到铃铛按钮。
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
