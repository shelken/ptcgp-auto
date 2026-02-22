/**
 * Notification Drawer Manager
 * 通知面板管理模块
 * 
 * 提供通知面板的打开/关闭控制，包括滚动锁定机制
 * 参考模态框管理模块 (modal.js) 的实现模式
 */

export class NotificationDrawerManager {
    constructor() {
        this.container = document.getElementById('notification-panel-container');
        this.panel = document.getElementById('notification-panel');
        this.previousBodyOverflow = null;
        this.previousHtmlOverflow = null;
        this.isOpen = false;

        // 绑定外部点击关闭
        if (this.container) {
            this._bindOutsideClick();
            this._bindEscapeKey();
        }
    }

    /**
     * 打开通知面板
     * - 显示面板，锁定滚动
     * - 分发 opened 自定义事件
     */
    open() {
        if (this.isOpen || !this.container) return;

        // 移除 hidden 类，添加 open 类
        this.container.classList.remove('hidden');
        this.container.classList.add('open');
        this.container.setAttribute('aria-hidden', 'false');
        
        // 锁定滚动
        this.lockBodyScroll();
        
        this.isOpen = true;

        // 分发自定义事件
        document.dispatchEvent(new CustomEvent('notification-drawer:opened', {
            detail: { drawer: this }
        }));
    }

    /**
     * 关闭通知面板
     * - 隐藏面板，恢复滚动
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
     * 绑定外部点击关闭
     * 点击面板外部区域时关闭面板
     * @private
     */
    _bindOutsideClick() {
        this.container.addEventListener('click', (event) => {
            // 仅当点击的是容器本身（不是面板）时关闭
            if (event.target === this.container) {
                this.close();
            }
        });
    }

    /**
     * 绑定 ESC 键关闭
     * @private
     */
    _bindEscapeKey() {
        document.addEventListener('keydown', (event) => {
            if (this.isOpen && event.key === 'Escape') {
                this.close();
            }
        });
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
