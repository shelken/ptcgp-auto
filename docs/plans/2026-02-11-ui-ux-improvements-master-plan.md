# [UI/UX] Web 界面改进总体计划

> **对于 Claude:** 必需子技能：使用 superpowers:executing-plans 逐个任务执行此计划。

**目标：** 解决 PTCGP Auto Web 界面中已识别的 UI/UX 问题，重点关注用户反馈、无障碍性、代码结构和特定页面改进。

**架构：** 改进将逐步实施，首先修复关键的 UX 问题（如 Alert 替换），然后进行代码清理和特定页面的增强。

**技术栈：** HTML, CSS (Tailwind/custom utility classes), JavaScript (ES6 Modules), Python (FastAPI/Jinja2)。

---

## 当前进度（更新于 2026-02-12）

- [x] 任务 1.1：`plans.js` 中 `alert()` 已替换为 `showToast()`，并修复了计划重名时后端唯一约束报错（改为前端 Toast 友好提示）。
- [x] 任务 1.2：全局 Focus 可见性问题已修复（移除/替换不可见焦点样式，补充焦点可见规则）。
- [x] 任务 1.3：全局按钮 loading 状态已接入（HTMX + fetch 场景），覆盖刷新/保存等关键按钮。
- [x] 任务 2.1：已完成 `onclick/onchange/oninput/onsubmit` 迁移到 `data-action + 事件委托`，并移除 `main.js/modal.js` 中不再需要的 `window` 导出。
- [x] 任务 2.2：已完成 `plans.js` 与 `filters.js` 中的 `innerHTML` 动态拼接替换，改为 `createElement/replaceChildren` 的安全 DOM 构建。
- [x] 阶段 2：代码结构与维护目标已阶段性完成（事件委托迁移 + DOM 安全改造）。
- [~] 阶段 3：已开始落地部分页面改动（每日送卡、记录页、账号/好友页面有进展），但尚未完成整体验收。
- [ ] 阶段 4：最终无障碍审查与视觉回归尚未开始。

### 本轮关键问题与处理

1. **计划保存唯一键冲突**：创建同名计划触发 `UNIQUE constraint failed: task_plans.name`，已改为服务层前置重名检查 + 路由返回 Toast 错误提示。
2. **记录页双请求问题**：`records` 首次加载存在重复请求，已调整 `tabs.js` 初始化逻辑避免双发。
3. **图片兜底回退问题**：清理了 `card_back` 相关引用，统一改为透明 data URI 兜底，并避免 `onerror` 循环。

---

## 阶段 1：关键 UX 修复（用户反馈与无障碍性）

### 任务 1.1：用 `showToast()` 或 Modals 替换 `alert()`

**文件：**
- 修改：`src/ptcgp_auto_v2/web/static/js/modules/plans.js`
- 修改：`src/ptcgp_auto_v2/web/static/js/modules/utils.js`（如果需要增强功能）

**步骤 1：定位 alert() 调用**
识别 JS 文件中 `alert()` 的使用（已在 `plans.js` 中找到）。

**步骤 2：替换为 showToast()**
用现有的 `showToast()` 工具函数替换侵入式的 Alert。

```javascript
// plans.js 中的替换示例
// alert(messages.saveErrorMessage);
showToast(messages.saveErrorMessage, 3000);
```

**步骤 3：验证**
触发以前会导致 Alert 的操作（例如重复添加计划、保存错误），确认出现 Toast 通知。

### 任务 1.2：修复 Focus 状态与无障碍性

**文件：**
- 修改：`src/ptcgp_auto_v2/web/static/css/main.css`
- 修改：`src/ptcgp_auto_v2/web/templates/**/*.html`（按需）

**步骤 1：移除全局 `outline: none`**
移除或修改 `main.css` 中的全局 `outline: none` 规则，确保键盘 Focus 可见。如果缺失，添加 `:focus-visible` 样式。

**步骤 2：修复 `href="javascript:void(0)"`**
将使用 `javascript:void(0)` 的 `<a>` 标签替换为样式化为链接的 `<button>` 元素，或者确保它们具有 `role="button"` 和键盘处理程序。

**步骤 3：验证**
使用 Tab 键导航网站。确保所有交互元素都有可见的 Focus 指示器。

### 任务 1.3：添加全局加载状态

**文件：**
- 修改：`src/ptcgp_auto_v2/web/static/js/modules/utils.js`
- 修改：`src/ptcgp_auto_v2/web/static/css/main.css`
- 修改：`src/ptcgp_auto_v2/web/templates/partials/macros/buttons.html`（如果存在）或相关模板

**步骤 1：实现按钮加载状态**
创建一个工具或 CSS 类，在异步操作（HTMX 请求或 fetch）期间在按钮上显示加载动画。

**步骤 2：应用到关键操作**
将此状态应用到“保存”、“刷新”和其他操作按钮。

---

## 阶段 2：代码结构与维护

### 任务 2.1：清理全局命名空间污染

**文件：**
- 修改：`src/ptcgp_auto_v2/web/static/js/main.js`
- 修改：`src/ptcgp_auto_v2/web/static/js/modules/*.js`
- 修改：`src/ptcgp_auto_v2/web/templates/**/*.html`

**步骤 1：移除 window 导出**
识别在 `main.js` 和模块中导出到 `window` 的函数。

**步骤 2：重构为事件委托**
将 HTML 中的 `onclick="..."` 替换为在 JS 模块中绑定的事件监听器。使用数据属性（例如 `data-action="save-plan"`）来标识元素。

**步骤 3：验证**
确保所有交互（模态框、标签页、操作）在没有 `onclick` 属性的情况下正常工作。

### 任务 2.2：安全的 DOM 操作

**文件：**
- 修改：`src/ptcgp_auto_v2/web/static/js/modules/plans.js`
- 修改：`src/ptcgp_auto_v2/web/static/js/modules/filters.js`

**步骤 1：替换 innerHTML**
识别用于构建动态内容的 `innerHTML` 用法。替换为 `document.createElement()` 或模板克隆，以防止 XSS 风险并提高性能。

---

## 阶段 3：特定页面 UI 改进

### 任务 3.1：每日送卡页面改进

**文件：**
- 修改：`src/ptcgp_auto_v2/web/templates/partials/daily_gift_list.html`
- 修改：`src/ptcgp_auto_v2/web/static/css/main.css`

**步骤 1：优化日期选择器**
重构日期选择行，以更好地处理响应式布局（例如，在移动设备上使用水平滚动或下拉菜单）。

**步骤 2：可视化状态**
通过颜色和/或图标增强“成功/失败/等待中”统计数据的展示。

### 任务 3.2：记录页面改进

**文件：**
- 修改：`src/ptcgp_auto_v2/web/templates/partials/record_list.html`

**步骤 1：修复网格布局**
确保网格视图中的卡片名称正确截断，以防止布局破坏。

**步骤 2：移动端筛选优化**
在移动屏幕上实现可折叠的筛选部分。

### 任务 3.3：账号与好友关系页面改进

**文件：**
- 修改：`src/ptcgp_auto_v2/web/templates/partials/account_list.html`
- 修改：`src/ptcgp_auto_v2/web/templates/partials/friendship_list.html`

**步骤 1：优化账号列表**
调整账号列表项中的排版层级，强调关键数据（点数、沙漏）。

**步骤 2：修复好友关系表格对齐**
检查好友记录的表格布局，确保列对齐。

---

## 阶段 4：最终润色与验证

### 任务 4.1：最终无障碍性审查

**步骤 1：自动审计**
运行无障碍审计工具（如果有）或手动检查清单。

**步骤 2：键盘导航测试**
最后一遍键盘导航测试。

### 任务 4.2：视觉回归检查

**步骤 1：跨主题检查**
验证所有更改在不同主题（复古、奢华等）下看起来都很棒。
