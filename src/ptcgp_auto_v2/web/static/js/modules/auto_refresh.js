// --- 构建自动刷新 URL ---
export function buildAutoRefreshUrl(container) {
    if (!container) return null;

    const baseUrl = container.dataset.autoRefresh;
    if (!baseUrl) return null;

    const includeSelector = container.dataset.refreshInclude;
    if (!includeSelector) {
        return baseUrl;
    }

    const params = new URLSearchParams();
    params.set('page', '0');

    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    params.set('lang', lang);

    const selectors = includeSelector.split(',').map((item) => item.trim()).filter(Boolean);
    selectors.forEach((selector) => {
        const element = document.querySelector(selector);
        if (!element) return;

        if (element.tagName === 'FORM') {
            const formData = new FormData(element);
            formData.forEach((value, key) => {
                params.append(key, value);
            });
            return;
        }

        if (element.name) {
            params.append(element.name, element.value || '');
        }
    });

    return `${baseUrl}?${params.toString()}`;
}
