# Architecture: 通知中心 UI 组件

**Domain:** 通知中心面板组件架构
**Researched:** 2026-02-23
**Confidence:** HIGH

## 推荐架构

通知中心采用**右侧滑出面板 (Slide-out Panel)** 模式，复用现有 Modal 基础设施，通过 HTMX 局部更新实现通知列表的动态加载与交互。

```
┌─────────────────────────────────────────────────────────────┐
│  Header (index.html)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Logo        Tab Nav        🔔 Bell Icon [badge]   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                          │                  │
│                                          ▼                  │
│                            ┌──────────────────────┐         │
│                            │ #notification-panel  │         │
│                            │ (右侧滑出面板)        │         │
│                            │ ┌──────────────────┐ │         │
│                            │ │ Header: 标题+关闭 │ │         │
│                            │ ├──────────────────┤ │         │
│                            │ │ #notification-   │ │         │
│                            │ │   list-content   │ │         │
│                            │ │ (滚动区域)        │ │         │
│                            │ │  - 通知项 1      │ │         │
│                            │ │  - 通知项 2      │ │         │
│                            │ │  ...             │ │         │
│                            │ ├──────────────────┤ │         │
│                            │ │ Footer: 全部已读  │ │         │
│                            │ └──────────────────┘ │         │
│                            └──────────────────────┘         │
│                                                             │
│  Main Content (Tab Area)                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  #records-container / #management-content / ...     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 组件文件结构

```
src/ptcgp_auto_v2/web/
├── templates/
│   ├── index.html                      # 添加铃铛图标入口
│   └── partials/
│       └── notification_panel.html     # 通知中心面板模板（新增）
│           ├── notification_panel_header   # 头部（标题+关闭）
│           ├── notification_list_content   # 列表内容（可替换）
│           └── notification_item           # 单条通知项
├── static/
│   ├── css/
│   │   └── components/
│   │       └── notification-panel.css  # 面板样式（新增）
│   └── js/
│       └── modules/
│           └── features/
│               └── notification_panel.js  # 面板交互逻辑（新增）
└── routers/
    └── notifications.py                # 现有路由扩展
```

## HTMX 集成策略

### 铃铛图标入口 (index.html)

```html
<!-- 在 header 右侧添加 -->
<div class="relative">
    <button
        type="button"
        id="notification-bell"
        class="brutal-btn p-2"
        data-action="toggle-notification-panel"
        aria-label="{{ t.notification_center or '通知中心' }}">
        <!-- 铃铛 SVG 图标 -->
        <svg>...</svg>
        <!-- 未读徽标（通过 hx-get 动态加载） -->
        <span id="notification-badge"
              hx-get="/notifications/count"
              hx-trigger="load, notificationsUpdated from:body"
              hx-swap="innerHTML">
        </span>
    </button>
</div>
```

### 面板容器结构

```html
<!-- 通知中心面板（添加到 index.html body 末尾，#modal-container 之后） -->
<div id="notification-panel-container"
     class="notification-panel-overlay hidden"
     role="dialog"
     aria-modal="true"
     aria-labelledby="notification-panel-title">
    <div id="notification-panel"
         class="notification-panel"
         hx-get="/notifications/panel"
         hx-trigger="load, notificationsUpdated from:body"
         hx-swap="innerHTML">
        <!-- 内容通过 HTMX 动态加载 -->
    </div>
</div>
```

### Swap 策略矩阵

| 场景 | Target | Swap | 说明 |
|------|--------|------|------|
| 打开面板加载全部 | `#notification-panel` | `innerHTML` | 首次打开加载完整内容 |
| 刷新列表 | `#notification-panel` | `innerHTML` | 保持面板结构，替换内部 |
| 加载更多 | `#notification-list-content` | `beforeend` | 追加到列表末尾 |
| 标记已读单条 | `#notification-panel` | `innerHTML` | 刷新整个面板更新 badge |
| 标记全部已读 | `#notification-panel` | `innerHTML` | 刷新整个面板 |
| 更新未读数量 | `#notification-badge` | `innerHTML` | 仅更新徽标数字 |

### HX-Trigger 事件驱动

```python
# 后端响应头触发前端事件
response.headers["HX-Trigger"] = json.dumps({
    "notificationsUpdated": True,  # 触发 badge 和 panel 刷新
    "showToast": {"message": "已标记为已读"}
}, ensure_ascii=True)
```

```html
<!-- 前端监听事件刷新 -->
<span hx-get="/notifications/count"
      hx-trigger="notificationsUpdated from:body"
      hx-swap="innerHTML">

<div hx-get="/notifications/panel"
     hx-trigger="notificationsUpdated from:body"
     hx-swap="innerHTML">
```

## 事件委托模式集成

遵循现有 `data-action` 模式，在 `action_handlers.js` 添加分发分支：

```javascript
// action_handlers.js
import { toggleNotificationPanel, markNotificationRead, loadMoreNotifications } from './features/notification_panel.js';

export function handleActionClick(event) {
    // ... 现有处理 ...

    if (action === 'toggle-notification-panel') {
        toggleNotificationPanel();
        return;
    }

    if (action === 'mark-notification-read' && actionButton.dataset.id) {
        markNotificationRead(actionButton.dataset.id);
        return;
    }

    if (action === 'load-more-notifications') {
        loadMoreNotifications();
        return;
    }
}
```

### 新模块: notification_panel.js

```javascript
// modules/features/notification_panel.js
import { showToast, setButtonLoading } from '../utils.js';

const PANEL_CONTAINER_ID = 'notification-panel-container';
const PANEL_ID = 'notification-panel';
const SCROLL_LOCK_CLASS = 'notification-panel-open';

let isOpen = false;
let previousActiveElement = null;

export function toggleNotificationPanel() {
    if (isOpen) {
        closeNotificationPanel();
    } else {
        openNotificationPanel();
    }
}

export function openNotificationPanel() {
    if (isOpen) return;

    const container = document.getElementById(PANEL_CONTAINER_ID);
    if (!container) return;

    previousActiveElement = document.activeElement;
    container.classList.remove('hidden');
    document.body.classList.add(SCROLL_LOCK_CLASS);
    document.documentElement.classList.add(SCROLL_LOCK_CLASS);
    isOpen = true;

    // 触发 HTMX 加载内容
    const panel = document.getElementById(PANEL_ID);
    if (panel && !panel.dataset.loaded) {
        htmx.trigger(panel, 'load');
    }

    document.dispatchEvent(new CustomEvent('notification-panel:opened'));
}

export function closeNotificationPanel() {
    if (!isOpen) return;

    const container = document.getElementById(PANEL_CONTAINER_ID);
    if (container) {
        container.classList.add('hidden');
    }
    document.body.classList.remove(SCROLL_LOCK_CLASS);
    document.documentElement.classList.remove(SCROLL_LOCK_CLASS);
    isOpen = false;

    if (previousActiveElement && previousActiveElement.focus) {
        previousActiveElement.focus();
    }

    document.dispatchEvent(new CustomEvent('notification-panel:closed'));
}

export function markNotificationRead(notificationId) {
    // 由 HTMX hx-post 处理，此处仅用于非 HTMX 场景
}

export function loadMoreNotifications() {
    const sentinel = document.querySelector('[data-notification-sentinel]');
    if (sentinel) {
        htmx.trigger(sentinel, 'revealed');
    }
}

// 点击遮罩关闭
export function initNotificationPanelEvents() {
    const container = document.getElementById(PANEL_CONTAINER_ID);
    if (container) {
        container.addEventListener('click', (event) => {
            if (event.target === container) {
                closeNotificationPanel();
            }
        });
    }

    // ESC 键关闭
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && isOpen) {
            closeNotificationPanel();
        }
    });
}
```

## 数据流

```
用户点击铃铛
    │
    ▼
handleActionClick → toggleNotificationPanel()
    │
    ├── 添加 .hidden 移除
    ├── 锁定 body/html 滚动
    └── 触发 HTMX: hx-get="/notifications/panel"
                │
                ▼
        FastAPI Router: /notifications/panel
                │
                ├── NotificationRepository.list_unread_first()
                ├── build_notification_panel_context()
                └── render_template("partials/notification_panel.html")
                │
                ▼
        HTML Fragment 返回
                │
                ▼
        HTMX swap → #notification-panel.innerHTML
                │
                ├── 初始化相对时间
                ├── 初始化自定义 Select（如有筛选）
                └── 绑定滚动加载监听
```

### 滚动加载流程

```html
<!-- 列表末尾的哨兵元素 -->
<div data-notification-sentinel
     hx-get="/notifications/panel?page={{ next_page }}"
     hx-trigger="revealed"
     hx-target="#notification-list-content"
     hx-swap="beforeend">
</div>
```

## 滚动锁定策略

复用现有 Modal 滚动锁定模式，统一在 `body` 和 `html` 上添加类：

```css
/* notification-panel.css */
.notification-panel-open body,
.notification-panel-open html {
    overflow: hidden;
}
```

在 JS 中同步操作：

```javascript
// 打开时
document.body.classList.add('notification-panel-open');
document.documentElement.classList.add('notification-panel-open');

// 关闭时
document.body.classList.remove('notification-panel-open');
document.documentElement.classList.remove('notification-panel-open');
```

## CSS 架构

### 组件文件: notification-panel.css

```css
/**
 * Notification Panel Component
 * 通知中心面板样式
 */

/* 遮罩层 */
.notification-panel-overlay {
    position: fixed;
    inset: 0;
    z-index: 100; /* 低于 modal (z-50)，高于普通内容 */
    background-color: var(--bg-overlay);
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.2s ease, visibility 0.2s ease;
}

.notification-panel-overlay:not(.hidden) {
    opacity: 1;
    visibility: visible;
}

/* 面板容器 */
.notification-panel {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(420px, 90vw);
    max-width: 100%;
    background-color: var(--card-bg);
    border-left: var(--border-width) solid var(--border-color);
    box-shadow: calc(var(--shadow-offset) * -1) 0 var(--shadow-offset) var(--shadow-color);
    transform: translateX(100%);
    transition: transform 0.25s ease;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.notification-panel-overlay:not(.hidden) .notification-panel {
    transform: translateX(0);
}

/* 面板头部 */
.notification-panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: var(--border-width) solid var(--border-color);
    flex-shrink: 0;
}

/* 面板内容 */
.notification-panel-content {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
}

/* 面板底部 */
.notification-panel-footer {
    padding: 1rem 1.25rem;
    border-top: var(--border-width) solid var(--border-color);
    flex-shrink: 0;
}

/* 通知项 */
.notification-item {
    padding: 0.75rem 1rem;
    border: var(--border-width) solid var(--border-subtle);
    border-radius: var(--radius);
    background-color: var(--bg-surface);
    margin-bottom: 0.75rem;
    transition: border-color 0.15s ease;
}

.notification-item:hover {
    border-color: var(--border-color);
}

.notification-item--unread {
    border-left: 3px solid var(--active-color);
}

/* 徽标 */
.notification-badge {
    position: absolute;
    top: -4px;
    right: -4px;
    min-width: 18px;
    height: 18px;
    padding: 0 4px;
    font-size: 11px;
    font-weight: bold;
    line-height: 18px;
    text-align: center;
    border-radius: 9px;
}

/* 响应式 */
@media (max-width: 480px) {
    .notification-panel {
        width: 100%;
        max-width: 100%;
    }
}
```

### CSS 变量依赖

所有颜色/边框/阴影使用现有 CSS 变量：

| 变量 | 用途 |
|------|------|
| `--card-bg` | 面板背景 |
| `--border-color` | 主边框 |
| `--border-subtle` | 通知项边框 |
| `--bg-overlay` | 遮罩背景 |
| `--shadow-color` | 阴影颜色 |
| `--shadow-offset` | 阴影偏移 |
| `--active-color` | 未读标记色 |
| `--text-muted` | 次要文本 |

## 关键设计决策

### 1. 面板 vs Modal

**选择面板** 而非 Modal，因为：
- 通知列表需要快速浏览，不需要居中聚焦
- 右侧滑出符合 macOS/iOS 用户习惯
- 不遮挡主内容区，用户可同时参考
- 避免与现有 Modal 系统（编辑表单、卡牌选择）冲突

### 2. outerHTML vs innerHTML

**选择 innerHTML** 作为主要 swap 策略，因为：
- 保持 `#notification-panel` 容器稳定，避免重复初始化
- 面板状态（滚动位置）可在 JS 层面维护
- 符合项目现有 HTMX 模式（参考 `#notification-panel` 在 notification_page.html）

### 3. 事件委托 vs 内联事件

**必须使用 `data-action`** 事件委托模式：
- 符合项目强制规范（AGENTS.md）
- 避免内联 `onclick` 导致的 CSP 问题
- 统一在 `action_handlers.js` 分发

### 4. 滚动加载 vs 分页

**选择滚动加载**（revealed trigger）：
- 更好的连续浏览体验
- 符合项目 Records Tab 的 infinite scroll 模式
- 通过 `beforeend` swap 避免重复渲染

## 集成检查清单

- [ ] `index.html` 添加铃铛图标入口
- [ ] `index.html` body 末尾添加 `#notification-panel-container`
- [ ] 创建 `partials/notification_panel.html`
- [ ] 创建 `components/notification-panel.css` 并在 `main.css` 导入
- [ ] 创建 `modules/features/notification_panel.js`
- [ ] `action_handlers.js` 添加 `toggle-notification-panel` 分发
- [ ] `bootstrap.js` 调用 `initNotificationPanelEvents()`
- [ ] `event_bindings.js` 添加滚动加载监听
- [ ] `locales/*.json` 添加通知中心文案
- [ ] `main.css?v=X.X` 更新版本号

## 参考资源

- HTMX Swap Strategies: https://htmx.org/attributes/hx-swap/
- HTMX Event Triggering: https://htmx.org/headers/hx-trigger/
- 现有 Modal 模式: `src/ptcgp_auto_v2/web/static/js/modules/modal.js`
- 事件委托规范: `src/ptcgp_auto_v2/web/AGENTS.md`
- 现有通知路由: `src/ptcgp_auto_v2/web/routers/notifications.py`
