# Stack Research: Notification Center UI

**Domain:** Slide-out notification panel for HTMX-based web app
**Researched:** 2026-02-23
**Confidence:** HIGH

## Executive Summary

为现有 FastAPI + HTMX + Jinja2 + ES6 Modules 架构添加右侧滑出通知中心。核心决策：**客户端 Markdown 渲染**（marked.js）、**纯 CSS 动画**（transform + transition）、**HTMX revealed trigger** 实现无限滚动。完全复用现有 `data-action` 委托模式和 CSS 变量主题系统。

## Recommended Stack

### 1. Markdown 渲染：客户端 marked.js

| 选项 | 推荐度 | 理由 |
|------|--------|------|
| **marked.js (客户端)** | ✅ 推荐 | 轻量（~40KB）、零后端依赖、支持按需渲染、与 HTMX 天然兼容 |
| Python markdown (服务端) | ❌ 不推荐 | 需要 Jinja2 filter、增加后端负担、无法动态更新已渲染内容 |
| markdown-it | ⚠️ 备选 | 功能更多但体积更大（~150KB），过度工程 |

**决策：marked.js 客户端渲染**

**为什么：**
1. 通知内容存储为 markdown 字符串，按需在客户端渲染
2. 展开详情时动态渲染，无需重新请求后端
3. 可配合 DOMPurify 做 XSS 防护（marked 本身不 sanitise）
4. 与 HTMX 局部替换完美配合：`htmx:afterSwap` 后调用渲染

**使用方式：**
```javascript
// CDN 引入（无需构建）
<script src="https://cdn.jsdelivr.net/npm/marked/lib/marked.umd.js"></script>

// 渲染
const html = marked.parse(markdownContent, { breaks: true, gfm: true });
element.innerHTML = html;
```

**安全考虑：** 必须配合 DOMPurify 防止 XSS（通知内容可能包含用户输入）
```javascript
import DOMPurify from 'https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.es.mjs';
const clean = DOMPurify.sanitize(marked.parse(content));
```

### 2. 滑出面板动画：纯 CSS Transform

| 选项 | 推荐度 | 理由 |
|------|--------|------|
| **CSS transform + transition** | ✅ 推荐 | 性能最优（GPU 加速）、零 JS 依赖、与现有 modal.css 模式一致 |
| CSS @keyframes | ⚠️ 可选 | 更灵活但代码量更大，现有 motion.css 已有类似模式 |
| JavaScript 动画库 | ❌ 不推荐 | gsap/anime.js 过重，违反「无构建系统」约束 |

**决策：CSS transform + transition**

**实现模式（复用现有 modal.css 风格）：**
```css
/* 面板容器 */
.notification-drawer {
    position: fixed;
    top: 0;
    right: 0;
    width: min(420px, 90vw);
    height: 100vh;
    z-index: 1000;
    background-color: var(--bg-surface);
    border-left: var(--border-width) solid var(--border-color);
    box-shadow: var(--shadow-offset) 0 0 var(--shadow-color);
    transform: translateX(100%);
    transition: transform 0.3s ease;
}

.notification-drawer.open {
    transform: translateX(0);
}

/* 遮罩层 */
.drawer-overlay {
    position: fixed;
    inset: 0;
    z-index: 999;
    background-color: var(--bg-overlay);
    backdrop-filter: blur(4px);
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.25s ease, visibility 0.25s ease;
}

.drawer-overlay.open {
    opacity: 1;
    visibility: visible;
}
```

**JS 控制（复用 ModalManager 模式）：**
```javascript
// 复用现有的 getModal().lockBodyScroll() 机制
open() {
    this.drawer.classList.add('open');
    this.overlay.classList.add('open');
    this.lockBodyScroll();  // 复用 modal.js 的方法
}

close() {
    this.drawer.classList.remove('open');
    this.overlay.classList.remove('open');
    this.unlockBodyScroll();
}
```

### 3. 无限滚动：HTMX revealed trigger

| 选项 | 推荐度 | 理由 |
|------|--------|------|
| **HTMX hx-trigger="revealed"** | ✅ 推荐 | 零 JS 代码、声明式、与现有架构一致 |
| HTMX hx-trigger="intersect" | ⚠️ 可选 | 更精确控制但配置复杂 |
| JS IntersectionObserver | ❌ 不推荐 | 违反「优先 HTMX」原则、代码冗余 |

**决策：HTMX revealed trigger**

**实现模式：**
```html
<!-- 通知列表容器 -->
<div id="notification-drawer-list">
    {% for n in notifications %}
    <div class="notification-item" data-id="{{ n.id }}">...</div>
    {% endfor %}
    
    <!-- 最后一个元素触发加载更多 -->
    {% if has_more %}
    <div hx-get="/notifications/load-more?offset={{ next_offset }}"
         hx-trigger="revealed"
         hx-target="#notification-drawer-list"
         hx-swap="beforeend">
        <span class="loading-indicator">Loading...</span>
    </div>
    {% endif %}
</div>
```

**关键点：**
- `hx-swap="beforeend"` 追加而非替换
- 加载完成后替换触发器元素自身（更新 offset）
- 后端返回空响应表示无更多数据

### 4. 展开详情：HTMX + 客户端 Markdown 渲染

**模式：** 点击通知 → HTMX 加载完整内容 → 客户端 marked.js 渲染

```html
<div class="notification-item" 
     hx-get="/notifications/{{ n.id }}/detail"
     hx-target="#notification-detail-{{ n.id }}"
     hx-swap="innerHTML">
    <div class="notification-title">{{ n.title }}</div>
</div>

<div id="notification-detail-{{ n.id }}" 
     class="notification-detail hidden"
     data-markdown-content="{{ n.content }}">
</div>
```

```javascript
// htmx:afterSwap 后渲染 markdown
document.body.addEventListener('htmx:afterSwap', (evt) => {
    const detailEl = evt.detail.target.querySelector('[data-markdown-content]');
    if (detailEl) {
        const md = detailEl.dataset.markdownContent;
        detailEl.innerHTML = DOMPurify.sanitize(marked.parse(md));
        detailEl.classList.remove('hidden');
    }
});
```

## Integration with Existing Architecture

### 复用现有模式

| 现有组件 | 复用方式 |
|----------|----------|
| `modal.js` ModalManager | 创建 `DrawerManager` 类，复用 `lockBodyScroll`/`unlockBodyScroll` |
| `action_handlers.js` | 添加 `toggle-notification-drawer`、`mark-notification-read` 分支 |
| `data-action` 委托 | 铃铛按钮 `data-action="toggle-notification-drawer"` |
| CSS 变量系统 | 使用 `var(--bg-surface)`、`var(--border-color)` 等，主题自动适配 |
| `motion.css` | 可复用 `transition-base`、`transition-slow` 类 |

### 新增文件

```
src/ptcgp_auto_v2/web/
├── static/
│   ├── css/components/drawer.css        # 滑出面板样式
│   └── js/modules/drawer.js             # DrawerManager 类
├── templates/
│   └── partials/
│       └── notification_drawer.html     # 面板模板
```

## What NOT to Use

| 避免 | 原因 | 替代方案 |
|------|------|----------|
| **Tailwind/Bootstrap drawer 组件** | 引入额外 CSS 框架冲突 | 纯 CSS + CSS 变量 |
| **jQuery slideToggle** | 项目无 jQuery 依赖 | CSS transform |
| **React/Vue drawer 库** | 项目是 HTMX 架构 | 纯 JS + HTMX |
| **markdown-it** | 体积过大（150KB vs 40KB） | marked.js |
| **服务端 Markdown 渲染** | 无法动态更新、增加后端负担 | 客户端渲染 |
| **inline onclick** | 违反项目 `data-action` 规范 | 委托模式 |

## Security Considerations

### XSS 防护（必须）

**问题：** marked.js 不做 HTML sanitization，用户可能注入恶意脚本

**方案：** 使用 DOMPurify 过滤
```javascript
// 必须在渲染前调用
const clean = DOMPurify.sanitize(marked.parse(userContent));
```

**CDN 引入：**
```html
<script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.es.mjs"></script>
```

## Implementation Checklist

- [ ] 创建 `drawer.css`（滑出面板样式 + 遮罩层）
- [ ] 创建 `drawer.js`（DrawerManager 类，复用 modal.js 的滚动锁定）
- [ ] 在 `action_handlers.js` 添加 drawer 相关 action 分发
- [ ] 在 `index.html` 引入 marked.js + DOMPurify CDN
- [ ] 创建 `notification_drawer.html` 模板（铃铛 + 面板 + 列表）
- [ ] 后端添加 `/notifications/drawer` 接口（返回面板 partial）
- [ ] 后端添加 `/notifications/load-more` 接口（支持 offset 分页）
- [ ] 后端添加 `/notifications/{id}/detail` 接口（返回完整内容）
- [ ] 处理 `htmx:afterSwap` 事件渲染 markdown
- [ ] 点击通知时调用 `mark-read` 接口

## Sources

- [marked.js 官方文档](https://marked.js.org/) — API 使用、安全警告 — HIGH confidence
- [HTMX infinite scroll with revealed](https://dri.es/infinite-scroll-with-htmx) — revealed trigger 用法 — HIGH confidence
- [Django HTMX infinite scroll](https://dev.to/foxy4096/infinite-scroll-pagination-in-django-with-htmx-32f7) — 实现模式参考 — MEDIUM confidence
- [Hotwire drawer with CSS View Transitions](https://thoughtbot.com/blog/hotwire-drawer) — CSS 动画模式参考 — MEDIUM confidence
- 项目现有代码：`modal.js`、`action_handlers.js`、`modal.css`、`motion.css` — 架构模式复用 — HIGH confidence

---

*Stack research for: Notification Center UI*
*Researched: 2026-02-23*
