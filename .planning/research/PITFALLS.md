# 通知中心 UI 陷阱研究

**Domain:** 通知中心 UI (Slide-out Panel + Infinite Scroll + HTMX)
**Researched:** 2026-02-23
**Confidence:** HIGH

---

## Critical Pitfalls

### Pitfall 1: HTMX `revealed` 触发器的竞态条件与重复请求

**What goes wrong:**
快速滚动时 `hx-trigger="revealed"` 可能触发多次请求，导致：
- 重复加载同一页数据
- 数据条目在列表中出现多次
- 后端收到大量冗余请求

**Why it happens:**
HTMX 的 `revealed` 事件在元素进入视口时触发，但没有内置的请求去重机制。用户快速滚动时，`revealed` 可能在上一个请求完成前多次触发。

**How to avoid:**
1. 在触发元素上添加 `hx-trigger="revealed once"` 确保只触发一次
2. 后端返回的新触发元素使用新 page 参数，避免重复
3. 考虑使用 `hx-trigger="intersect once threshold:0.1"` 替代 `revealed` 获得更精细控制

**Warning signs:**
- 网络面板显示相同 page 参数的重复请求
- 列表中出现重复的通知项
- 控制台出现 HTMX 请求堆积警告

**Phase to address:** Phase 1 - 基础面板与滚动加载

---

### Pitfall 2: 滑出面板滚动穿透 (Scroll Chaining)

**What goes wrong:**
打开滑出面板后，滚动面板内容时，背后的主页面也跟着滚动。用户体验极其混乱。

**Why it happens:**
浏览器默认的滚动链接 (scroll chaining) 行为。当面板内容滚动到边界时，滚动事件传递给父级容器。

**How to avoid:**
```javascript
// 参考 modal.js 的实现
lockBodyScroll() {
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
}
```
必须同时锁定 `body` 和 `document.documentElement`（即 `<html>`）。

**Warning signs:**
- 面板滚动到底部时，背景页面开始滚动
- iOS Safari 上尤其明显（橡皮筋效果）

**Phase to address:** Phase 1 - 基础面板与滚动加载

---

### Pitfall 3: 未读 Badge 更新不同步

**What goes wrong:**
- 用户标记通知已读后，badge 数字不更新
- 多标签页打开时，badge 状态不一致
- 面板内标记已读后，badge 延迟更新或根本不更新

**Why it happens:**
badge 和面板内容来自不同的 API 响应，缺乏统一的状态同步机制。

**How to avoid:**
1. 使用 HTMX OOB (Out of Band) swap 同时更新 badge 和列表
2. 标记已读的响应同时返回新的未读数量
3. 监听 `htmx:afterSwap` 事件更新 badge

```html
<!-- 标记已读响应示例 -->
<div hx-swap-oob="true" id="notification-badge">3</div>
<li class="notification-item read">...</li>
```

**Warning signs:**
- 点击通知后 badge 数字不变
- 刷新页面后 badge 与实际未读数不符

**Phase to address:** Phase 2 - 已读状态与 Badge 同步

---

### Pitfall 4: 键盘焦点陷阱与无障碍访问失败

**What goes wrong:**
- Tab 键焦点逃离面板，跑到背后页面元素
- 屏幕阅读器无法正确识别面板为对话框
- ESC 键无法关闭面板

**Why it happens:**
没有正确实现焦点陷阱 (focus trap)，缺少 `aria-modal`、`role="dialog"` 等无障碍属性。

**How to avoid:**
1. 面板打开时设置 `aria-modal="true"` 和 `role="dialog"`
2. 实现 Tab/Shift+Tab 循环焦点
3. 绑定 ESC 键关闭面板
4. 打开时保存当前焦点，关闭时恢复

```javascript
// 参考 modal.js 的 trapFocus 实现
trapFocus() {
    const focusables = this.panel.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (focusables.length > 0) focusables[0].focus();
}
```

**Warning signs:**
- Tab 键可以跳出面板
- 无障碍检测工具报告 WCAG 2.1.2 失败
- ESC 键无响应

**Phase to address:** Phase 1 - 基础面板与滚动加载

---

### Pitfall 5: HTMX 替换边界不一致导致嵌套膨胀

**What goes wrong:**
无限滚动加载后，DOM 结构变成：
```html
<div id="notification-panel">
    <div id="notification-panel">  <!-- 嵌套了！ -->
        ...通知列表...
    </div>
</div>
```

**Why it happens:**
`hx-target` 指向的是 `#notification-panel`，但服务器返回的 HTML 也包含 `<div id="notification-panel">`，导致嵌套。

**How to avoid:**
1. `hx-swap="innerHTML"` 而非默认的 `outerHTML`
2. 或者服务器返回不带外层容器的片段
3. 建立统一的替换边界约定（参考现有 `HTMX 替换边界原则`）

```html
<!-- 触发元素 -->
<div hx-get="/notifications?page=2"
     hx-trigger="revealed"
     hx-target="#notification-list"
     hx-swap="beforeend">  <!-- 追加而非替换 -->
</div>
```

**Warning signs:**
- 检查元素发现嵌套的相同 ID
- CSS 选择器失效
- 页面加载越来越慢（DOM 膨胀）

**Phase to address:** Phase 1 - 基础面板与滚动加载

---

### Pitfall 6: Z-index 堆叠上下文冲突

**What goes wrong:**
- 面板被其他元素遮挡（如 header、tooltip、modal）
- 设置 `z-index: 99999` 仍然无效
- 与现有 Modal 或 Popover 冲突

**Why it happens:**
`transform`、`opacity < 1`、`filter` 等属性会创建新的堆叠上下文。z-index 只在同一堆叠上下文内生效。

**How to avoid:**
1. 将面板 DOM 放在 `<body>` 直接子级，避免嵌套在其他堆叠上下文中
2. 使用 CSS 变量管理 z-index 层级（如 `--z-notification-panel`）
3. 建立统一的 z-index 层级体系

```css
/* 建议的 z-index 层级 */
:root {
    --z-header: 100;
    --z-notification-panel: 200;
    --z-modal-backdrop: 300;
    --z-modal: 400;
    --z-tooltip: 500;
}
```

**Warning signs:**
- 面板部分被遮挡
- z-index 设为极大值仍无效
- 不同主题下面板表现不一致

**Phase to address:** Phase 1 - 基础面板与滚动加载

---

## Moderate Pitfalls

### Pitfall 7: 通知详情展开时布局抖动

**What goes wrong:**
点击通知展开详情时，列表发生跳动，用户丢失滚动位置。

**Prevention:**
- 展开详情使用固定高度容器 + 溢出滚动
- 或使用绝对定位的浮层展示详情
- 避免改变已渲染元素的高度

**Phase to address:** Phase 2 - 详情展示与 Markdown 渲染

---

### Pitfall 8: Markdown 渲染 XSS 风险

**What goes wrong:**
通知内容包含用户可控的 Markdown，渲染时执行恶意脚本。

**Prevention:**
- 使用经过安全审计的 Markdown 库（如 marked + DOMPurify）
- 后端预渲染 Markdown 为安全 HTML
- 禁止 `<script>`、`onclick` 等危险标签

**Phase to address:** Phase 2 - 详情展示与 Markdown 渲染

---

### Pitfall 9: 无限滚动无终止提示

**What goes wrong:**
用户滚动到底部后，loading 动画一直转，没有提示"已加载全部"。

**Prevention:**
- 后端返回空列表时，替换触发元素为"没有更多"提示
- 移除最后一项的 `hx-trigger="revealed"` 属性

**Phase to address:** Phase 1 - 基础面板与滚动加载

---

### Pitfall 10: 面板关闭后滚动位置丢失

**What goes wrong:**
用户滚动浏览通知，关闭面板再打开时，滚动位置重置到顶部。

**Prevention:**
- 选项 A: 面板关闭时不清空内容，只隐藏
- 选项 B: 记住滚动位置，打开时恢复
- 选项 C: 接受此行为，每次打开从头开始（简化实现）

**Phase to address:** Phase 1 - 基础面板与滚动加载

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| 直接用 `onclick` 而非 `data-action` | 快速实现 | 违反项目规范，难以维护 | Never |
| 硬编码 z-index 数字 | 立即可用 | 主题冲突，层级混乱 | Never |
| 不实现焦点陷阱 | 减少代码量 | 无障碍失败，WCAG 不合规 | Never |
| 省略 ESC 关闭 | 简化逻辑 | 用户体验差，键盘用户受阻 | Never |
| 不做请求去重 | 减少状态管理 | 重复请求，数据重复 | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| 与现有 Modal 共存 | 面板 z-index 高于 Modal | 使用统一的 z-index 层级变量 |
| HTMX OOB swap | 忘记 `hx-swap-oob="true"` | badge 更新必须使用 OOB |
| 主题系统 | 硬编码颜色值 | 使用 CSS 变量（`--bg-overlay`、`--text-muted` 等） |
| 事件委托 | 面板内使用 `onclick` | 统一使用 `data-action` + `event_bindings.js` |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 无限滚动 DOM 膨胀 | 滚动变卡，内存占用高 | 虚拟滚动 / 限制最大条目数 | 500+ 条通知 |
| 每次打开重新请求 | 重复网络请求，闪烁 | 首次缓存 + 增量更新 | 高频打开场景 |
| Markdown 重复渲染 | 打开详情慢 | 缓存渲染结果 | 复杂 Markdown |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| 点击通知直接跳转 | 丢失当前上下文 | 先展开详情，再提供跳转链接 |
| 全部已读无确认 | 误操作无法撤销 | 提供撤销 toast 或确认对话框 |
| 无加载指示器 | 不知道是否在加载 | 显示 skeleton 或 spinner |
| 手机关闭困难 | 必须精准点击小 X | 提供滑动手势关闭 |

---

## "Looks Done But Isn't" Checklist

- [ ] **滚动锁定:** 打开面板后，鼠标滚轮/触控板滚动背景页面 — 测试 body 和 html 都被锁定
- [ ] **焦点陷阱:** Tab 键无法逃离面板 — 使用键盘完整测试
- [ ] **ESC 关闭:** 按 ESC 无响应 — 绑定 keydown 事件
- [ ] **Badge 同步:** 标记已读后 badge 不更新 — 检查 OOB swap
- [ ] **Z-index:** 面板被 header 遮挡 — 在所有主题下测试
- [ ] **无障碍:** 屏幕阅读器测试 — 添加 aria-modal、role、aria-labelledby
- [ ] **重复请求:** 快速滚动触发多次请求 — 检查网络面板
- [ ] **DOM 嵌套:** 检查元素查看是否有重复 ID — 使用正确的 hx-swap
- [ ] **终止提示:** 滚动到底部有"没有更多"提示 — 测试边界情况
- [ ] **主题兼容:** 在 Retro/Luxury/Organic 等主题下测试 — 使用 CSS 变量

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| 滚动穿透 | LOW | 添加 `lockBodyScroll()` 调用 |
| 焦点陷阱 | MEDIUM | 实现 Tab 循环 + ESC 关闭 |
| Badge 不同步 | MEDIUM | 添加 OOB swap 响应 |
| DOM 嵌套 | HIGH | 重构 HTMX 替换边界 + 清理已有代码 |
| Z-index 冲突 | HIGH | 重构层级体系，可能影响其他组件 |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 滚动穿透 | Phase 1 | 打开面板后滚动鼠标，背景不动 |
| 焦点陷阱 | Phase 1 | Tab 键循环在面板内，ESC 关闭 |
| Z-index 冲突 | Phase 1 | 所有主题下面板在最上层 |
| HTMX 重复请求 | Phase 1 | 网络面板无重复请求 |
| DOM 嵌套 | Phase 1 | 检查元素无重复 ID |
| 终止提示 | Phase 1 | 滚动到底部显示"没有更多" |
| Badge 不同步 | Phase 2 | 标记已读后 badge 立即更新 |
| 布局抖动 | Phase 2 | 展开详情时列表不跳动 |
| Markdown XSS | Phase 2 | 插入恶意脚本不执行 |
| 滚动位置丢失 | Phase 1 或接受 | 根据需求决定是否保存 |

---

## Sources

- [Smashing Magazine: Design Guidelines For Better Notifications UX](https://www.smashingmagazine.com/2025/07/design-guidelines-better-notifications-ux/) - HIGH confidence
- [HTMX Infinite Scroll Example](https://github.com/bigskysoftware/htmx/blob/master/www/content/examples/infinite-scroll.md) - HIGH confidence
- [Bootstrap Offcanvas Documentation](https://getbootstrap.com/docs/5.3/components/offcanvas/) - HIGH confidence
- [MDN: Stacking Context](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_positioned_layout/Understanding_z-index/Stacking_context) - HIGH confidence
- [CSS-Tricks: A Primer on Focus Trapping](https://css-tricks.com/a-primer-on-focus-trapping/) - HIGH confidence
- [Infinite Ajax Scroll: Common Pitfalls](https://infiniteajaxscroll.com/blog/common-pitfalls-infinite-scroll) - MEDIUM confidence
- [HTMX GitHub Issue #463: Fast Scroll reveal failure](https://github.com/bigskysoftware/htmx/issues/463) - HIGH confidence
- [Stack Overflow: HTMX revealed trigger issues](https://stackoverflow.com/questions/65961570/htmx-endless-scrolling-via-revealed-does-not-work) - MEDIUM confidence
- 项目现有 `AGENTS.md` 和 `modal.js` - HIGH confidence

---
*Pitfalls research for: 通知中心 UI (Slide-out Panel + Infinite Scroll + HTMX)*
*Researched: 2026-02-23*
