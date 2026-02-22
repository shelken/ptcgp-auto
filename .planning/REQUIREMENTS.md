# Requirements: PTCGP Auto - 通知中心功能

**Defined:** 2026-02-23
**Core Value:** 用户能快速查看未读通知，了解系统运行状态，无需跳转到管理页面

## v1 Requirements

### 入口与触发

- [ ] **ENTR-01**: 首页右上角显示铃铛图标
- [ ] **ENTR-02**: 铃铛图标旁显示未读数量 badge（无未读时隐藏）
- [ ] **ENTR-03**: 点击铃铛图标从右侧滑出通知面板

### 面板基础

- [ ] **PANEL-01**: 面板从右侧滑出，宽度 320-400px
- [ ] **PANEL-02**: 面板包含标题栏（"通知"）+ "全部已读" 按钮 + 关闭按钮
- [ ] **PANEL-03**: 点击面板外部区域关闭面板
- [ ] **PANEL-04**: 按 ESC 键关闭面板
- [ ] **PANEL-05**: 面板打开时锁定 body 滚动（防止滚动穿透）
- [ ] **PANEL-06**: 面板关闭后恢复 body 滚动

### 通知列表

- [ ] **LIST-01**: 列表显示全部通知（未读优先排序）
- [ ] **LIST-02**: 未读通知与已读通知有视觉区分（粗细/颜色）
- [ ] **LIST-03**: 每条通知显示标题、时间（相对时间格式）
- [ ] **LIST-04**: 滚动到底部自动加载更多（HTMX revealed trigger）
- [ ] **LIST-05**: 加载更多时显示 loading 状态

### 通知交互

- [ ] **INTR-01**: 点击通知项展开详情（显示 markdown 内容）
- [ ] **INTR-02**: 点击通知项自动标记为已读
- [ ] **INTR-03**: 展开详情后可收起
- [ ] **INTR-04**: 点击 "全部已读" 按钮批量标记所有未读通知
- [ ] **INTR-05**: 标记已读后实时更新 badge 数量（HTMX OOB swap）

### Markdown 渲染

- [ ] **MD-01**: 通知详情支持 markdown 渲染
- [ ] **MD-02**: markdown 渲染前进行 XSS 过滤（DOMPurify）

### 无障碍

- [ ] **A11Y-01**: 面板支持键盘导航（Tab 键循环）
- [ ] **A11Y-02**: 焦点在面板打开时被捕获，关闭时恢复到触发元素

## v2 Requirements

Deferred to future release.

### 筛选与搜索

- **FILT-01**: 面板内提供场景筛选（稀有卡牌/任务状态/系统警告）
- **FILT-02**: 面板内提供搜索功能

### 高级功能

- **ADV-01**: 通知分组显示（按场景分组）
- **ADV-02**: 通知严重级别图标
- **ADV-03**: 单条通知删除功能

## Out of Scope

| Feature | Reason |
|---------|--------|
| 实时推送更新 | 会造成 UI 跳动，用户阅读时丢失位置；使用打开时刷新即可 |
| Modal 覆盖层 | 阻挡主内容，不如滑出面板保持上下文 |
| 自动关闭面板 | 用户正在阅读时关闭会打断操作 |
| 声音提醒 | 通知疲劳问题，用户会完全关闭 |
| 全页面通知中心作为主入口 | 需要导航离开当前页面，打断工作流 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENTR-01 | Phase 1 | Pending |
| ENTR-02 | Phase 1 | Pending |
| ENTR-03 | Phase 1 | Pending |
| PANEL-01 | Phase 1 | Pending |
| PANEL-02 | Phase 1 | Pending |
| PANEL-03 | Phase 1 | Pending |
| PANEL-04 | Phase 1 | Pending |
| PANEL-05 | Phase 1 | Pending |
| PANEL-06 | Phase 1 | Pending |
| A11Y-01 | Phase 1 | Pending |
| A11Y-02 | Phase 1 | Pending |
| LIST-01 | Phase 1 | Pending |
| LIST-02 | Phase 1 | Pending |
| LIST-03 | Phase 1 | Pending |
| LIST-04 | Phase 1 | Pending |
| LIST-05 | Phase 1 | Pending |
| INTR-04 | Phase 1 | Pending |
| INTR-05 | Phase 1 | Pending |
| INTR-01 | Phase 2 | Pending |
| INTR-02 | Phase 2 | Pending |
| INTR-03 | Phase 2 | Pending |
| MD-01 | Phase 2 | Pending |
| MD-02 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-23*
*Last updated: 2026-02-23 after initial definition*
