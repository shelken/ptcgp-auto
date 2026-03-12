import { isElementInActiveTab } from './utils.js';

/**
 * 收集自动刷新需要带上的查询参数，保留同名字段的多值顺序。
 * @param {Element | null} element - 表单或单个输入控件
 * @returns {Array<[string, string]>}
 */
function collectRefreshEntries(element) {
    if (!element) return [];

    if (element.tagName === 'FORM') {
        const entries = [];
        const formData = new FormData(element);
        formData.forEach((value, key) => {
            entries.push([key, String(value)]);
        });
        return entries;
    }

    if (!element.name) return [];
    return [[element.name, element.value || '']];
}

// --- 构建自动刷新 URL ---
export function buildAutoRefreshUrl(container) {
    if (!container) return null;

    const baseUrl = container.dataset.autoRefresh;
    if (!baseUrl) return null;

    const parsedUrl = new URL(baseUrl, window.location.origin);
    const params = new URLSearchParams(parsedUrl.search);
    params.set('page', '0');

    if (!params.has('lang')) {
        const urlParams = new URLSearchParams(window.location.search);
        const lang = urlParams.get('lang') || 'en';
        params.set('lang', lang);
    }

    const includeSelector = container.dataset.refreshInclude;
    if (!includeSelector) {
        parsedUrl.search = params.toString();
        return parsedUrl.pathname + (parsedUrl.search ? parsedUrl.search : '');
    }

    const selectors = includeSelector.split(',').map((item) => item.trim()).filter(Boolean);
    const includedEntries = [];
    selectors.forEach((selector) => {
        const element = document.querySelector(selector);
        if (!element) return;
        includedEntries.push(...collectRefreshEntries(element));
    });

    const includedKeys = new Set();
    includedEntries.forEach(([key]) => {
        if (key) {
            includedKeys.add(key);
        }
    });
    includedKeys.forEach((key) => {
        params.delete(key);
    });
    includedEntries.forEach(([key, value]) => {
        if (!key) return;
        params.append(key, value);
    });

    parsedUrl.search = params.toString();
    return parsedUrl.pathname + (parsedUrl.search ? parsedUrl.search : '');
}

/**
 * 解析自动刷新请求配置。
 * @param {HTMLElement | null} container - 刷新容器
 * @returns {{ url: string, target: HTMLElement | null, swap: string } | null}
 */
export function resolveAutoRefreshRequest(container) {
    if (!(container instanceof HTMLElement)) return null;
    if (!container.dataset.autoRefresh) return null;

    const url = buildAutoRefreshUrl(container);
    if (!url) return null;

    const targetSelector = container.dataset.refreshTarget;
    const target = targetSelector
        ? document.querySelector(targetSelector)
        : container;
    const swap = container.dataset.refreshSwap || container.getAttribute('hx-swap') || 'innerHTML';

    return {
        url,
        target: target instanceof HTMLElement ? target : null,
        swap
    };
}

/**
 * 重放单个自动刷新容器的最近一次请求。
 * @param {HTMLElement | null} container - 刷新容器
 * @param {{ requireVisible?: boolean }} options - 触发约束
 * @returns {boolean}
 */
export function requestAutoRefresh(container, options = {}) {
    const { requireVisible = false } = options;
    if (!(container instanceof HTMLElement)) return false;
    if (!isElementInActiveTab(container)) return false;
    if (requireVisible && document.visibilityState !== 'visible') return false;
    const pauseUntil = container.dataset.pauseAutoRefreshUntil;
    if (pauseUntil && Date.now() < parseInt(pauseUntil, 10)) return false;

    const request = resolveAutoRefreshRequest(container);
    if (!request?.target) return false;
    if (request.target.dataset.refreshing === '1') return false;

    request.target.dataset.refreshing = '1';
    if (request.target.dataset.loaded !== undefined) {
        request.target.dataset.loading = 'true';
    }

    htmx.ajax('GET', request.url, {
        target: request.target,
        swap: request.swap
    });
    return true;
}

function collectAutoRefreshContainers(root) {
    const containers = [];
    if (root instanceof HTMLElement && root.matches('[data-auto-refresh]')) {
        containers.push(root);
    }

    const scope = root === document ? document : root;
    if (!(scope instanceof Document) && !(scope instanceof HTMLElement)) {
        return containers;
    }

    scope.querySelectorAll('[data-auto-refresh]').forEach((container) => {
        if (container instanceof HTMLElement) {
            containers.push(container);
        }
    });
    return containers;
}

/**
 * 刷新当前激活区域内所有自动刷新容器。
 * @param {Document | HTMLElement} root - 根节点
 * @param {{ requireVisible?: boolean }} options - 触发约束
 * @returns {number}
 */
export function refreshAutoRefreshContainers(root = document, options = {}) {
    let refreshedCount = 0;
    collectAutoRefreshContainers(root).forEach((container) => {
        if (requestAutoRefresh(container, options)) {
            refreshedCount += 1;
        }
    });
    return refreshedCount;
}
