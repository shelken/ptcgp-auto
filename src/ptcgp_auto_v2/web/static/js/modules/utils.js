/**
 * 通用工具函数模块
 */

/**
 * 显示 Toast 提示
 * @param {string} message - 提示消息
 * @param {number} duration - 显示时长（毫秒）
 */
export function showToast(message, duration = 2000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'true');
        container.className = 'fixed bottom-4 right-4 z-50 flex flex-col gap-2';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'bg-black text-white px-4 py-2 rounded shadow-lg transition-opacity duration-300';
    toast.textContent = message;
    toast.setAttribute('role', 'alert');

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
            if (container.children.length === 0 && container.parentNode) {
                container.parentNode.removeChild(container);
            }
        }, 300);
    }, duration);
}

/**
 * Focus 管理
 */
let previousActiveElement = null;

export function saveFocus() {
    previousActiveElement = document.activeElement;
}

export function restoreFocus() {
    if (previousActiveElement && previousActiveElement.focus) {
        previousActiveElement.focus();
    }
}

/**
 * 节流函数
 * @param {Function} func - 要节流的函数
 * @param {number} limit - 时间限制（毫秒）
 */
export function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * 防抖函数
 * @param {Function} func - 要防抖的函数
 * @param {number} wait - 等待时间（毫秒）
 */
export function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

/**
 * 检查元素是否在激活的 Tab 中
 * @param {HTMLElement} element - 要检查的元素
 * @returns {boolean}
 */
export function isElementInActiveTab(element) {
    const tabContent = element.closest('.tab-content');
    if (!tabContent) return true;
    return !tabContent.classList.contains('hidden');
}

// 导出到全局（供内联 onclick 使用）
if (typeof window !== 'undefined') {
    window.showToast = showToast;
    window.saveFocus = saveFocus;
    window.restoreFocus = restoreFocus;
    window.throttle = throttle;
    window.debounce = debounce;
    window.isElementInActiveTab = isElementInActiveTab;
}
