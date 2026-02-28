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
    selectors.forEach((selector) => {
        const element = document.querySelector(selector);
        if (!element) return;

        if (element.tagName === 'FORM') {
            const formData = new FormData(element);
            formData.forEach((value, key) => {
                params.set(key, String(value));
            });
            return;
        }

        if (element.name) {
            params.set(element.name, element.value || '');
        }
    });

    parsedUrl.search = params.toString();
    return parsedUrl.pathname + (parsedUrl.search ? parsedUrl.search : '');
}
