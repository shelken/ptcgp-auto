# Web 模块质量审计报告

**审计范围**: `src/ptcgp_auto_v2/web/`
**审计日期**: 2026-03-10
**Lighthouse 评分**: Accessibility 91 / Best Practices 100 / SEO 80

---

## Anti-Patterns 判定

**判定: 通过 — 不像 AI 生成的模板站。**

项目有明确的设计语言（brutalist/retro 等 8 套主题）、自定义组件体系（custom select、notification panel、3D 卡牌预览）、完整的 i18n 和筛选缓存系统。没有以下 AI slop 特征：
- 无渐变文字、无 hero metrics 大数字网格（metadata 页的数字是功能性计数器）
- 无泛滥 glassmorphism（仅 modal/preview overlay 的 blur 遮罩，合理）
- 无 generic card grids、无 "Sign up for newsletter"
- 无 generic 字体堆栈（每个主题有专属字体）

**一个值得注意的点**: 8 个字体家族全量加载（~每个主题只用 1-2 个），这在技术上是浪费但不是 AI slop。

---

## 执行摘要

| 严重度 | 数量 |
|--------|------|
| Critical | 4 |
| High | 12 |
| Medium | 16 |
| Low | 12 |
| **总计** | **44** |

### Top 5 最关键问题

1. **Custom Select 完全不可访问** — 无 ARIA 角色、不可键盘聚焦、屏幕阅读器完全不可见（Critical, A11y）
2. **Tailwind Play CDN 用于生产** — 运行时生成 CSS，~100KB+ JS 开销，官方文档明确标注"不适合生产"（Critical, Performance）
3. **CSS @import 瀑布流** — 18 个串行 HTTP 请求加载 CSS（High, Performance）
4. **luxury/playful 主题分类互换** — luxury（深色 #0f0f0f）被归为 Light，playful（浅色 #fff9c4）被归为 Dark（High, Theming）
5. **card_preview.js 内存泄漏** — document 级别拖拽监听器从不移除（High, Performance）

---

## 详细发现

### Critical 问题

#### C-01. Custom Select 组件对屏幕阅读器完全不可见
- **位置**: `static/js/modules/custom_select.js`
- **分类**: Accessibility
- **WCAG**: 4.1.2 Name, Role, Value / 2.1.1 Keyboard
- **描述**: 原生 `<select>` 被 `display: none !important` 隐藏，替换为纯 `<div>` 元素。trigger div 无 `role="combobox"`、无 `aria-expanded`、无 `tabindex`（不可键盘聚焦）。option div 无 `role="option"`、无 `aria-selected`。搜索输入无 `aria-label`。
- **影响**: 使用辅助技术的用户完全无法操作下拉选择器。项目中大量核心筛选器依赖此组件。
- **建议**: `/harden` — 完整重写 ARIA 属性，添加 `tabindex="0"`，实现 `aria-activedescendant` 模式

#### C-02. Tailwind Play CDN 用于生产
- **位置**: `templates/index.html:9`
- **分类**: Performance
- **描述**: `<script src="https://cdn.tailwindcss.com">` 是 Tailwind 的 Play CDN — 运行时扫描 DOM 生成 CSS。Tailwind 官方文档明确标注 "designed for development only"。
- **影响**: 每次页面加载增加 ~100KB+ JS 解析开销，可能导致 FOUC（无样式闪烁），且阻塞渲染。
- **建议**: `/optimize` — 迁移到构建时 Tailwind（Tailwind CLI 或 PostCSS），或者提取使用的 Tailwind 类为静态 CSS

#### C-03. `<html>` 缺少有效 `lang` 属性
- **位置**: `templates/index.html`
- **分类**: Accessibility / SEO
- **WCAG**: 3.1.1 Language of Page
- **描述**: Lighthouse 报告 `<html>` 元素没有有效的 `[lang]` 属性。
- **影响**: 屏幕阅读器无法确定页面语言，SEO 受损。
- **建议**: `/harden` — 在 `<html>` 标签添加 `lang="{{ current_lang|replace('_','-') }}"`

#### C-04. 对比度不足 (retro 主题)
- **位置**: 多个元素，Lighthouse 实测
- **分类**: Accessibility
- **WCAG**: 1.4.3 Contrast (Minimum)
- **描述**: retro 主题下 "EN" 语言按钮前景色 `#05855c` 在背景 `#0a0a1a` 上对比度仅 4.21:1（要求 4.5:1，14px bold 文字）。
- **影响**: 低视力用户难以阅读。
- **建议**: `/normalize` — 检查所有主题的 `--accent-color` / `--active-color` 在对应背景上的对比度

---

### High 问题

#### H-01. Tab 导航缺少 ARIA Tab 模式
- **位置**: `templates/index.html:123-157`
- **分类**: Accessibility
- **WCAG**: 4.1.2
- **描述**: Tab 按钮无 `role="tab"`、容器无 `role="tablist"`、面板无 `role="tabpanel"`。无 `aria-selected`、无箭头键导航。
- **建议**: `/harden`

#### H-02. HTMX 动态内容区域缺少 `aria-live`
- **位置**: `index.html:244,467,620`（三个主内容容器）
- **分类**: Accessibility
- **WCAG**: 4.1.3 Status Messages
- **描述**: 内容通过 HTMX swap 更新时，屏幕阅读器不会收到通知。
- **建议**: `/harden`

#### H-03. Modal 焦点陷阱不完整
- **位置**: `static/js/modules/modal.js:87-95`
- **分类**: Accessibility
- **WCAG**: 2.1.2 No Keyboard Trap
- **描述**: `trapFocus()` 仅聚焦第一个可聚焦元素，未实现 Tab/Shift+Tab 循环。用户可以 Tab 到 modal 后方的页面。Modal 内也无 Escape 键处理。
- **建议**: `/harden`

#### H-04. 卡牌预览无焦点陷阱、无焦点恢复
- **位置**: `static/js/modules/features/card_preview.js`
- **分类**: Accessibility
- **WCAG**: 2.1.1, 2.1.2
- **描述**: overlay 无 `role="dialog"`、无 `aria-modal`、无焦点陷阱、关闭后不恢复焦点。
- **建议**: `/harden`

#### H-05. 图标按钮仅用 `title` 未用 `aria-label`
- **位置**: `templates/partials/account_list.html:110-128`
- **分类**: Accessibility
- **WCAG**: 1.1.1
- **描述**: 编辑/配置按钮仅含 SVG 图标和 `title` 属性，`title` 不被屏幕阅读器可靠播报。
- **建议**: `/harden`

#### H-06. CSS @import 瀑布流（18 个串行请求）
- **位置**: `static/css/main.css:5-41`
- **分类**: Performance
- **描述**: 18 个 `@import url()` 语句导致 CSS 加载串行化，每个需要前一个下载解析完才能开始。
- **建议**: `/optimize` — 合并为单文件或使用 CSS bundler

#### H-07. CDN 脚本全部阻塞渲染（无 defer/async）
- **位置**: `templates/index.html:9-21`
- **分类**: Performance
- **描述**: 5 个 `<script>` 标签（Tailwind CDN, HTMX, Marked, DOMPurify, SortableJS）同步加载。其中 Marked/DOMPurify/SortableJS 仅在特定功能中使用。
- **建议**: `/optimize` — 非关键脚本添加 `defer`，或按需加载

#### H-08. card_preview.js 内存泄漏
- **位置**: `static/js/modules/features/card_preview.js:100-106`
- **分类**: Performance
- **描述**: `bindDragEvents()` 在每次打开预览时向 `document` 添加 mousemove/mouseup/touchmove/touchend 监听器，`closeCardPreview()` 从不移除。N 次打开后有 N 组孤立监听器。
- **建议**: `/optimize`

#### H-09. luxury/playful 主题分类互换
- **位置**: `static/js/modules/theme.js:12-13`
- **分类**: Theming
- **描述**: `LIGHT_THEMES` 包含 luxury（bg: #0f0f0f，纯黑），`DARK_THEMES` 包含 playful（bg: #fff9c4，浅黄）。auto 模式跟随系统偏好时会选到错误的主题。
- **建议**: `/normalize`

#### H-10. art_deco 暗色主题缺少 hover/focus 覆盖
- **位置**: `static/css/utilities/colors.css`, `components/buttons.css`, `components/custom-select.css`, `components/inputs.css`
- **分类**: Theming
- **描述**: art_deco（bg: #2b2b2b）没有像 retro/luxury 那样获得 hover 覆盖。默认的 `rgba(0,0,0,0.05)` 在深色背景上完全不可见。交互元素无视觉反馈。
- **建议**: `/normalize`

#### H-11. card-preview.css 主题变体硬编码颜色
- **位置**: `static/css/components/card-preview.css:176,181,186`
- **分类**: Theming
- **描述**: `[data-theme="retro"]` 和 `[data-theme="luxury"]` 选择器内使用 `#000`、`#1a1a1a`、`rgba(212,175,55,0.3)` 硬编码色值，违反 Token 驱动原则。
- **建议**: `/normalize`

#### H-12. 好友管理表格强制 980px 最小宽度
- **位置**: `static/css/utilities/layout.css:75`
- **分类**: Responsive
- **描述**: `.friendship-table-wrap table { min-width: 980px; }` 在 375px 手机上需要水平滚动近 3 倍屏宽。
- **建议**: `/adapt`

---

### Medium 问题

| # | 问题 | 分类 | 位置 |
|---|------|------|------|
| M-01 | 通知触发按钮缺少 `aria-expanded` | A11y | `index.html:44-59` |
| M-02 | Modal 容器在隐藏时就有 `role="dialog"` | A11y | `index.html:639` |
| M-03 | Tab 导航未包裹在 `<nav>` 中 | A11y | `index.html:123` |
| M-04 | 无 `<h1>`，heading 层级跳跃 | A11y | 多个文件 |
| M-05 | 筛选 checkbox `display:none` 脱离无障碍树 | A11y | `index.html:214-217` |
| M-06 | 必填字段星号对屏幕阅读器不可见 | A11y | `macros/forms.html:8` |
| M-07 | 多个搜索输入缺少 `<label>` 或 `aria-label` | A11y | `task_list.html:214`, `account_list.html:36` |
| M-08 | 加载指示器缺少 `role="status"` | A11y | `index.html:263-266` |
| M-09 | 8 个字体家族全量加载 | Performance | `index.html:24` |
| M-10 | resize 事件无 throttle/debounce | Performance | `event_bindings.js:413`, `owned_cards.js:193` |
| M-11 | 组件 CSS 约 15 处 `rgba(0,0,0,...)` 在暗色主题下不可见 | Theming | 多个组件文件 |
| M-12 | 模板中 `text-red-500` 硬编码颜色 | Theming | `edit_account_plans.html:60` |
| M-13 | 多个触摸目标 < 44px | Responsive | notification panel close(32px), bell(36px), filter clear btn |
| M-14 | 7 个翻译 key 在 zh_CN 有但 en 缺失 | i18n | `locales/en.json` |
| M-15 | 6+ 个模板引用的翻译 key 两个 locale 文件都不存在 | i18n | `account_list.html`, `metadata_list.html` |
| M-16 | JS 中 2 处硬编码中文 toast 消息 | i18n | `event_bindings.js:217,359` |

---

### Low 问题

| # | 问题 | 分类 | 位置 |
|---|------|------|------|
| L-01 | SVG 图标缺少 `aria-hidden="true"` | A11y | 多个文件 |
| L-02 | 通知缩略图使用泛化 alt 文字 | A11y | `notification_list_items.html:40` |
| L-03 | 工具栏 `<label>` 缺少 `for` 属性 | A11y | `macros/data_table.html:23` |
| L-04 | 图片缺少明确 width/height（CLS 影响） | Performance | `record_list.html`, `owned_card_list.html` |
| L-05 | MutationObserver 监听整个 body subtree | Performance | `event_bindings.js:179-201` |
| L-06 | `--btn-hover-text` 变量仅 luxury 定义 | Theming | 7 个 theme 文件 |
| L-07 | 2 处 `backdrop-filter: blur` | Theming | `modal.css:15`, `card-preview.css:14` |
| L-08 | `utils.js` 7 个 window 全局导出已无用（注释说"供 onclick"但 onclick 已移除） | Anti-pattern | `utils.js:126-132` |
| L-09 | Toast 使用 `bg-black text-white` 硬编码色 | Theming/Anti-pattern | `utils.js:22` |
| L-10 | metadata_list.html 多个英文标签未本地化 | i18n | `metadata_list.html` |
| L-11 | `<template>` probe 块混用中英文硬编码 | i18n | `index.html:643-715` |
| L-12 | metadata 路由 4 个 POST 端点重复表单解析样板 | Anti-pattern | `routers/metadata.py` |

---

## 系统性/模式化问题

1. **`rgba(0,0,0,...)` 滥用**: 约 15 处组件使用黑色半透明作为 hover/shadow/focus 效果。在 3 个暗色主题（retro/luxury/art_deco）中表现为"无效果"。应统一为基于 CSS 变量的方案（如 `var(--shadow-color)` 带透明度）。

2. **暗色主题覆盖不完整**: retro 和 luxury 有专门的 `[data-theme="xxx"]` CSS 覆盖，但 art_deco 几乎完全缺失。三个暗色主题应统一处理。

3. **i18n 覆盖不完整**: metadata 页面是 i18n 重灾区，大量 Step/Snapshot/Mode/Action 等标签直接写英文。JS 层的 toast 消息也有硬编码中文。

4. **ARIA 覆盖不完整**: 自定义交互组件（custom select、theme popover、card preview）的 ARIA 支持为零或近零。notification panel 是唯一做得好的（有焦点陷阱、ESC 关闭、焦点恢复）。

---

## 正面发现

| 项目 | 说明 |
|------|------|
| `:focus-visible` 样式 | `reset.css` 和 `buttons.css` 正确实现了键盘焦点指示器 |
| 通知面板 | 完整的焦点陷阱、ESC 关闭、焦点恢复、`aria-hidden` 管理、`prefers-reduced-motion` |
| Toast 系统 | 使用 `aria-live="polite"` + `role="alert"` |
| 表单宏 | `forms.html` 正确关联 `<label>` 和 `for` 属性 |
| 卡牌图片 alt 文字 | 使用 `alt="{{ item.card_display_name or item.card.name }}"` |
| 管理侧边栏语义 | 正确使用 `<nav>` + `<ul>` + `<li>` |
| `data-action` 委托 | 模板零内联事件，全部委托到 JS 模块 |
| CSS 变量主题系统 | 34 个 token、8 套主题、组件 CSS 大部分正确消费变量 |
| 图片延迟加载 | `loading="lazy"` + `decoding="async"` 正确使用 |
| Best Practices 满分 | Lighthouse Best Practices 100 分 |

---

## 按优先级排列的建议

### 立即（阻塞性）

1. **`/harden`**: 修复 Custom Select ARIA + 键盘可访问性 (C-01)
2. **`/harden`**: 添加 `<html lang>` 属性 (C-03)
3. **`/normalize`**: 交换 luxury↔playful 的主题分类 (H-09)

### 短期（本轮迭代）

4. **`/optimize`**: 替换 Tailwind Play CDN 为构建时方案 (C-02)
5. **`/optimize`**: 合并 CSS @import 为单文件 (H-06)
6. **`/optimize`**: CDN 脚本添加 `defer`，非关键库按需加载 (H-07)
7. **`/optimize`**: 修复 card_preview.js 内存泄漏 (H-08)
8. **`/harden`**: 补全 Tab ARIA 模式、Modal 焦点陷阱、aria-live 区域 (H-01~H-04)
9. **`/normalize`**: 为 art_deco 补全 hover/focus 覆盖，统一 `rgba()` 为变量 (H-10, M-11)
10. **`/harden`**: 修复 i18n 缺失：补齐 en.json 缺失 key、metadata 页面标签本地化、JS toast 本地化 (M-14~M-16)

### 中期（下轮迭代）

11. **`/adapt`**: 友谊表格移动端适配 (H-12)
12. **`/adapt`**: 触摸目标尺寸统一 ≥ 44px (M-13)
13. **`/normalize`**: 清理 card-preview.css 硬编码色值 (H-11)
14. **`/normalize`**: 清理 `text-red-500` 和 toast `bg-black` 硬编码 (M-12, L-09)
15. **`/harden`**: heading 层级、搜索输入 label、必填字段可访问性 (M-04~M-07)

### 长期（优化项）

16. **`/optimize`**: 字体按主题按需加载，减少初始 payload (M-09)
17. **`/optimize`**: resize 事件 throttle、图片 width/height 属性 (M-10, L-04)
18. **清理**: 移除 `utils.js` 无用 window 全局导出 (L-08)

---

## Skill 修复映射

| Skill | 覆盖问题数 | 主要内容 |
|-------|-----------|---------|
| `/harden` | ~18 | ARIA、键盘导航、焦点管理、i18n 补全、对比度 |
| `/optimize` | ~8 | Tailwind CDN、CSS 合并、脚本 defer、内存泄漏、字体加载 |
| `/normalize` | ~7 | 主题分类修正、暗色主题 hover 覆盖、硬编码色值清理 |
| `/adapt` | ~3 | 表格移动端适配、触摸目标尺寸 |

---

## 本轮修复备注（2026-03-10）

以下为本轮按报告执行后的落地说明（含实现取舍）：

1. `C-02` 已处理：移除 Tailwind Play CDN，改为预构建 `tailwind.generated.css`。
2. `H-06` 已处理：消除 `main.css` 的 `@import` 串行瀑布；**运行时改为在 `index.html` 直接按顺序加载模块 CSS**，不使用 `main.bundle.css`。
3. `H-07` 已处理：HTMX/Marked/DOMPurify/Sortable 改为 `defer` 加载，避免阻塞渲染。
4. `H-08` 已处理：`card_preview` 拖拽事件增加完整 cleanup，关闭预览与 modal 时释放 document 级监听。
5. `M-09` 已处理：字体改为“基础字体首屏 + 主题字体按需加载”。
6. `M-10` 已处理：`resize` 事件补齐 throttle（全局绑定与 owned card modal 预热）。
7. `L-04` 已处理：记录与拥有卡牌图片补充 `width/height`，降低 CLS。
8. `L-05` 已处理：`MutationObserver` 从 `document.body subtree` 收敛到关键容器监听。
9. `H-10` 已处理：为 `art_deco` 补齐 `row/sidebar/focus` 交互 token；并让 `buttons/inputs/custom-select/colors` 统一消费 token，移除暗色主题不可见的硬编码 `rgba(0,0,0,...)`。
10. `H-11` 已处理：`card-preview.css` 去除 retro/luxury 选择器硬编码色，改为 `--card-preview-*` token（主题文件覆盖）。
11. `M-12` 已处理：`edit_account_plans.html` 与 `plans.js` 的 `text-red-500` 改为 `text-danger`（映射 `--danger-color`）。
12. `L-09` 已处理：Toast 由 `bg-black text-white` 改为 token 驱动（`--toast-*`）。
13. `H-12` 已处理：`friendship-table-wrap` 去掉固定 `980px` 最小宽；移动端允许单元格换行，桌面端保留关键列 `nowrap`。
14. `M-13` 已处理：通知铃铛、通知关闭、筛选清除按钮、modal 关闭按钮、owned card 关闭按钮统一提升到 `>=44px` 触控尺寸。
15. `L-08` 已处理：`utils.js` 移除无用 `window.*` 全局导出，统一通过 ES Module 显式导入调用。
16. `L-10` 已处理：`metadata_list.html` 的 Step/Snapshot/Mode/Action/summary/result 等英文标签改为 i18n key，`en/zh_CN` 同步补齐。

实现约束备注：
- 维护策略采用“源码直接加载”优先，不引入 `main.bundle.css` 这类需要手工同步的源码内生成物。
