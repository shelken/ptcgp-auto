import { showToast, setButtonLoading } from '../../utils.js';
import { clearFilterCacheByFormId } from './shared_form.js';

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
    document.querySelectorAll('.filter-checkbox').forEach((el) => {
        el.checked = false;
    });
    clearFilterCacheByFormId('filter-form');

    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    htmx.ajax('GET', `/api/records?page=0&lang=${lang}`, { target: '#records-container', swap: 'innerHTML' });
}

// --- 刷新记录列表 ---
export function refreshRecords(button = null) {
    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';

    const form = document.getElementById('filter-form');
    const formData = form ? new FormData(form) : null;
    const params = new URLSearchParams();

    params.set('page', '0');
    params.set('lang', lang);

    if (formData) {
        formData.forEach((value, key) => {
            if (key === 'rarity' || key === 'card_type') {
                params.append(key, value);
            }
        });
    }

    bindRequestLoading(button, 'records-container');
    htmx.ajax('GET', `/api/records?${params.toString()}`, { target: '#records-container', swap: 'innerHTML' });
    showToast('已刷新');
}
