import { showToast, setButtonLoading } from '../../utils.js';
import { clearFilterCacheByFormId } from './shared_form.js';
import { buildAutoRefreshUrl } from '../../auto_refresh.js';

function bindRequestLoading(button, targetId) {
    if (!button) return;
    setButtonLoading(button, true);

    let released = false;
    const release = () => {
        if (released) return;
        released = true;
        setButtonLoading(button, false);
    };

    const onAfterRequest = (event) => {
        const target = event.detail && event.detail.target;
        if (!target || target.id !== targetId) return;
        document.body.removeEventListener('htmx:afterRequest', onAfterRequest);
        release();
    };

    document.body.addEventListener('htmx:afterRequest', onAfterRequest);
    setTimeout(() => {
        document.body.removeEventListener('htmx:afterRequest', onAfterRequest);
        release();
    }, 10000);
}

// --- 清除记录筛选 ---
export function clearFilters() {
    document.querySelectorAll('#filter-form .filter-checkbox').forEach((el) => {
        el.checked = false;
    });
    clearFilterCacheByFormId('filter-form');

    const container = document.getElementById('records-container');
    const url = container ? buildAutoRefreshUrl(container) : null;
    htmx.ajax('GET', url || '/api/records?page=0', { target: '#records-container', swap: 'innerHTML' });
}

// --- 刷新记录列表 ---
export function refreshRecords(button = null) {
    const container = document.getElementById('records-container');
    const url = container ? buildAutoRefreshUrl(container) : null;
    bindRequestLoading(button, 'records-container');
    htmx.ajax('GET', url || '/api/records?page=0', { target: '#records-container', swap: 'innerHTML' });
    showToast('已刷新');
}
