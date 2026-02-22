/**
 * Notification Drawer Manager
 * 通知面板管理模块
 * 
 * 提供通知面板的打开/关闭控制，包括：
 * - 滚动锁定机制
 * - 外部点击关闭
 * - ESC 键关闭
 * - 焦点陷阱（Tab 键循环导航）
 * - 焦点恢复
 * - 安全 Markdown 渲染（XSS 防护）
 * 
 * 参考模态框管理模块 (modal.js) 的实现模式
 */

// ============================================================================
// DOMPurify Hook 初始化
// ============================================================================

/**
 * 初始化 DOMPurify hook
 * 为所有链接添加 target="_blank" 和 rel="noopener noreferrer"
 */
function initDOMPurifyHooks() {
    if (typeof DOMPurify === 'undefined') {
        console.warn('DOMPurify not loaded');
        return;
    }
    
    DOMPurify.addHook('afterSanitizeAttributes', (node) => {
        // 为所有链接添加安全属性
        if (node.tagName === 'A' && node.hasAttribute('href')) {
            node.setAttribute('target', '_blank');
            node.setAttribute('rel', 'noopener noreferrer');
        }
    });
}

// 初始化 hooks（模块加载时立即执行）
initDOMPurifyHooks();

// ============================================================================
// Markdown 渲染配置
// ============================================================================

/**
 * Markdown 渲染配置
 * 最小语法集：粗体、斜体、链接、自动链接
 */
const MARKED_OPTIONS = {
    gfm: true,           // 启用 GFM（包含 autolink）
    breaks: true,        // 换行转 <br>
    pedantic: false,
};

/**
 * DOMPurify 白名单配置
 * 仅允许：粗体、斜体、链接、段落、换行
 */
const PURIFY_CONFIG = {
    ALLOWED_TAGS: ['b', 'strong', 'i', 'em', 'a', 'p', 'br'],
    ALLOWED_ATTR: ['href', 'title', 'target', 'rel'],
    ALLOW_DATA_ATTR: false,
};

/**
 * 安全渲染 Markdown 内容
 * @param {string} markdown - 原始 Markdown 文本
 * @returns {string} - 清理后的安全 HTML
 */
function renderMarkdownSafely(markdown) {
    if (!markdown) return '';
    
    // 检查依赖是否加载
    if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
        console.warn('marked or DOMPurify not loaded, returning plain text');
        return escapeHtml(markdown);
    }
    
    try {
        // 1. Markdown 解析
        const rawHtml = marked.parse(markdown, MARKED_OPTIONS);
        
        // 2. XSS 过滤
        const cleanHtml = DOMPurify.sanitize(rawHtml, PURIFY_CONFIG);
        
        return cleanHtml;
    } catch (error) {
        console.error('Markdown rendering error:', error);
        return escapeHtml(markdown);
    }
}

/**
 * HTML 转义（fallback 用）
 * @param {string} text - 原始文本
 * @returns {string} - 转义后的文本
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

export class NotificationDrawerManager {
    constructor() {
        this.container = document.getElementById('notification-panel-container');
        this.panel = document.getElementById('notification-panel');
        this.previousBodyOverflow = null;
        this.previousHtmlOverflow = null;
        this.isOpen = false;
        this.previousActiveElement = null;

        // 预绑定事件处理程序���确保可以正确移除）
        this._boundHandleKeydown = this._handleKeydown.bind(this);
        this._boundHandleOutsideClick = this._handleOutsideClick.bind(this);
    }

    /**
     * 打开通知面板
     * - 保存当前焦点元素
     * - 显示面板，锁定滚动
     * - 添加事件监听器
     * - 设置焦点陷阱
     * - 分发 opened 自定义事件
     */
    open() {
        if (this.isOpen || !this.container) return;

        // 保存当前焦点元素（用于关闭时恢复）
        this.previousActiveElement = document.activeElement;

        // 移除 hidden 类，添加 open 类
        this.container.classList.remove('hidden');
        this.container.classList.add('open');
        this.container.setAttribute('aria-hidden', 'false');

        // 锁定滚动
        this.lockBodyScroll();

        // 添加事件监听器
        document.addEventListener('keydown', this._boundHandleKeydown);
        this.container.addEventListener('click', this._boundHandleOutsideClick);

        // 加载通知列表
        this.loadPanelContent();

        // 设置焦点陷阱（延迟执行，等待 DOM 渲染完成）
        requestAnimationFrame(() => {
            this._trapFocus();
        });

        this.isOpen = true;

        // 分发自定义事件
        document.dispatchEvent(new CustomEvent('notification-drawer:opened', {
            detail: { drawer: this }
        }));
    }

    /**
     * 关闭通知面板
     * - 隐藏面板，恢复滚动
     * - 移除事件监听器
     * - 恢复焦点到触发元素
     * - 分发 closed 自定义事件
     */
    close() {
        if (!this.isOpen || !this.container) return;

        // 移除 open 类，添加 hidden 类
        this.container.classList.remove('open');
        this.container.classList.add('hidden');
        this.container.setAttribute('aria-hidden', 'true');

        // 恢复滚动
        this.unlockBodyScroll();

        // 移除事件监听器
        document.removeEventListener('keydown', this._boundHandleKeydown);
        this.container.removeEventListener('click', this._boundHandleOutsideClick);

        // 恢复焦点到触发元素
        if (this.previousActiveElement && typeof this.previousActiveElement.focus === 'function') {
            this.previousActiveElement.focus();
        }

        this.isOpen = false;

        // 分发自定义事件
        document.dispatchEvent(new CustomEvent('notification-drawer:closed'));
    }

    /**
     * 切换面板状态
     */
    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    /**
     * 加载面板内容
     * 通过 HTMX 从后端加载
     */
    loadPanelContent() {
        const content = document.getElementById('notification-list-content');
        if (!content) return;

        // 使用 HTMX 加载内容
        if (typeof htmx !== 'undefined') {
            htmx.trigger(content, 'loadPanel');
        }
    }

    /**
     * 锁定 body 和 html 滚动
     * 防止面板打开时背景页面滚动
     */
    lockBodyScroll() {
        // 保存当前 overflow 值
        if (this.previousBodyOverflow === null) {
            this.previousBodyOverflow = document.body.style.overflow;
        }
        if (this.previousHtmlOverflow === null) {
            this.previousHtmlOverflow = document.documentElement.style.overflow;
        }

        // 同时锁定 body 和 html
        document.body.style.overflow = 'hidden';
        document.documentElement.style.overflow = 'hidden';
    }

    /**
     * 恢复 body 和 html 滚动
     */
    unlockBodyScroll() {
        // 恢复 body overflow
        if (this.previousBodyOverflow !== null) {
            document.body.style.overflow = this.previousBodyOverflow;
            this.previousBodyOverflow = null;
        } else {
            document.body.style.overflow = '';
        }

        // 恢复 html overflow
        if (this.previousHtmlOverflow !== null) {
            document.documentElement.style.overflow = this.previousHtmlOverflow;
            this.previousHtmlOverflow = null;
        } else {
            document.documentElement.style.overflow = '';
        }
    }

    /**
     * 键盘事件处理
     * @param {KeyboardEvent} event
     * @private
     */
    _handleKeydown(event) {
        if (!this.isOpen) return;

        // ESC 键关闭面板
        if (event.key === 'Escape') {
            event.preventDefault();
            this.close();
            return;
        }

        // Tab 键焦点陷阱
        if (event.key === 'Tab') {
            this._handleTabKey(event);
        }
    }

    /**
     * 外部点击处理
     * 点击面板外部区域（容器背景）时关闭面板
     * @param {MouseEvent} event
     * @private
     */
    _handleOutsideClick(event) {
        // 仅当点击的是容器本身（不是面板内容）时关闭
        if (event.target === this.container) {
            this.close();
        }
    }

    /**
     * Tab 键焦点陷阱
     * 在面板内循环导航，防止焦点泄漏到背景
     * @param {KeyboardEvent} event
     * @private
     */
    _handleTabKey(event) {
        if (!this.panel) return;

        // 获取面板内所有可聚焦元素
        const focusableElements = this.panel.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );

        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        // Shift+Tab：从第一个元素跳到最后一个
        if (event.shiftKey && document.activeElement === firstElement) {
            event.preventDefault();
            lastElement.focus();
        }
        // Tab：从最后一个元素跳到第一个
        else if (!event.shiftKey && document.activeElement === lastElement) {
            event.preventDefault();
            firstElement.focus();
        }
    }

    /**
     * 焦点陷阱初始化
     * 打开面板时将焦点移到第一个可聚焦元素
     * @private
     */
    _trapFocus() {
        if (!this.panel) return;

        // 获取面板内所有可聚焦元素
        const focusableElements = this.panel.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );

        if (focusableElements.length > 0) {
            focusableElements[0].focus();
        }
    }
}

// 单例实例
let drawerInstance = null;

/**
 * 获取通知面板管理器单例
 * @returns {NotificationDrawerManager}
 */
export function getNotificationDrawer() {
    if (!drawerInstance) {
        drawerInstance = new NotificationDrawerManager();
    }
    return drawerInstance;
}

/**
 * Badge 更新动画辅助方法
 * 用于在 badge 内容更新时添加视觉反馈
 * @param {number} newCount - 新的未读数量（可选，仅用于记录）
 */
export function animateBadgeUpdate(newCount) {
    const badge = document.getElementById('notification-badge');
    if (!badge) return;

    // 添加更新中状态
    badge.classList.add('updating');

    // 下一帧移除状态，触发过渡动画
    requestAnimationFrame(() => {
        badge.classList.remove('updating');
    });
}

/**
 * 触发未读→已读状态过渡动画
 * 批量标记已读后，为每个通知项添加动画
 */
export function triggerUnreadToReadAnimation() {
    const content = document.getElementById('notification-list-content');
    if (!content) return;

    // 获取所有未读通知项
    const items = content.querySelectorAll('.notification-item--unread');
    items.forEach((item, index) => {
        // 错开动画，产生波浪效果
        setTimeout(() => {
            item.classList.add('to-read');
            // 动画结束后移除未读状态类
            setTimeout(() => {
                item.classList.remove('notification-item--unread', 'to-read');
            }, 300);
        }, index * 50);
    });
}

// 监听 HTMX 内容替换后的事件，触发未读→已读动画
document.addEventListener('htmx:afterSettle', (event) => {
    // 检查是否是通知列表内容的替换
    if (event.target.id === 'notification-list-content') {
        // 触发未读→已读动画
        triggerUnreadToReadAnimation();
    }
});

/**
 * 处理 details toggle 事件
 * 展开时：滚动到可见位置 + 乐观 UI 已读标记 + 异步后端调用 + Markdown 渲染
 */
document.addEventListener('toggle', (event) => {
    const details = event.target;

    // 仅处理通知项的 details 元素
    if (!details.classList.contains('notification-item')) return;

    if (details.open) {
        // 1. 滚动到可见位置
        details.scrollIntoView({ behavior: 'smooth', block: 'start' });

        // 2. 乐观 UI 已读标记（立即视觉反馈）
        markAsReadOptimistically(details);

        // 3. 异步后端调用（静默忽略失败）
        const id = details.dataset.notificationId;
        if (id) {
            markAsReadAsync(id);
        }
        
        // 4. 渲染 Markdown 内容
        renderNotificationDetail(details);
    }
}, true); // capture 阶段监听，因为 toggle 事件不冒泡

/**
 * 乐观 UI 已读标记
 * 立即更新视觉效果，不等待后端响应
 * @param {HTMLElement} element - details 元素
 */
function markAsReadOptimistically(element) {
    // 移除未读状态类
    element.classList.remove('notification-item--unread');

    // 移除竖线指示器
    const indicator = element.querySelector('.notification-item__indicator');
    if (indicator) {
        indicator.remove();
    }

    // 更新标题字重（通过动画类）
    const title = element.querySelector('.notification-item__title');
    if (title) {
        title.style.fontWeight = '500';
    }
}

/**
 * 异步后端已读标记
 * 静默忽略失败，保持 UI 变化
 * @param {string|number} id - 通知 ID
 */
async function markAsReadAsync(id) {
    try {
        const response = await fetch(`/management/notifications/mark-read?notification_id=${id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            console.warn(`Failed to mark notification ${id} as read`);
        }

        // 触发 badge 更新
        document.dispatchEvent(new CustomEvent('notificationRead'));
    } catch (error) {
        // 静默忽略失败
        console.warn('markAsReadAsync error:', error);
    }
}

/**
 * 渲染通知详情内容
 * 仅在首次展开时渲染（检查是否已渲染）
 * @param {HTMLElement} details - details 元素
 */
function renderNotificationDetail(details) {
    const detailContainer = details.querySelector('.notification-item__detail');
    if (!detailContainer) return;
    
    // 检查是否已渲染（避免重复渲染）
    if (detailContainer.dataset.rendered === 'true') return;
    
    // 获取原始 Markdown 内容
    const markdown = detailContainer.dataset.notificationContent;
    if (!markdown) return;
    
    // 渲染 Markdown
    const renderedHtml = renderMarkdownSafely(markdown);
    detailContainer.innerHTML = renderedHtml;
    
    // 标记已渲染
    detailContainer.dataset.rendered = 'true';
}

// 导出供外部访问（renderMarkdownSafely 和 renderNotificationDetail 不是 export function 声明）
export { 
    renderMarkdownSafely,
    renderNotificationDetail
};
