import {
    restoreFilters,
    restoreOwnedFilters,
    updateOwnedFilterGroupsState,
    getStoredTasksFilters,
    buildQueryParts,
} from './filters.js';

const STORAGE_KEY_TAB = 'ptcgp_active_tab';

// --- 当前 Tab 状态 ---
export let currentTabName = null;

// --- 切换 Tab ---
export function switchTab(tabName, options = {}) {
    const {
        preserveHash = false,
        preferHash = null,
        skipAutoSelect = false
    } = options;
    const initialHash = preferHash !== null ? preferHash : window.location.hash.replace('#', '');

    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.add('hidden');
        el.classList.remove('block');
    });

    const selected = document.getElementById(`tab-content-${tabName}`);
    if (selected) {
        selected.classList.remove('hidden');
        selected.classList.add('block');
    }

    currentTabName = tabName;

    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    const activeBtn = document.getElementById(`tab-btn-${tabName}`);
    if (activeBtn) {
        activeBtn.classList.add('active');

        const newTitle = activeBtn.getAttribute('data-title');
        const titleEl = document.getElementById('main-title');
        if (newTitle && titleEl) {
            titleEl.textContent = newTitle;
        }

        const hash = activeBtn.getAttribute('data-hash');
        if (hash && !preserveHash) {
            window.location.hash = hash;
        }
    }

    const filters = document.getElementById('records-filters');
    if (filters) {
        filters.classList.toggle('hidden', tabName !== 'records');
    }

    if (tabName === 'records') {
        const container = document.getElementById('records-container');
        if (container && container.dataset.loaded !== 'true') {
            restoreFilters();
        }
        if (container && container.dataset.autoRefresh) {
            triggerAutoRefresh(container);
        }
    }

    if (tabName === 'owned-cards') {
        window.ownedCardsUserScrolled = false;
        const container = document.getElementById('owned-cards-container');
        if (container && container.dataset.loaded !== 'true') {
            restoreOwnedFilters();
        }
        updateOwnedFilterGroupsState();
    }

    localStorage.setItem(STORAGE_KEY_TAB, tabName);

    if (tabName === 'management' && !skipAutoSelect) {
        const content = document.getElementById('management-content');
        const hasContent = content.querySelector('table') || content.querySelector('form');

        if (!hasContent) {
            const hash = initialHash;
            let targetBtn = null;
            if (hash && ['accounts', 'plans', 'tasks', 'metadata', 'friendships'].includes(hash)) {
                targetBtn = document.querySelector(`.sidebar-btn[data-hash="${hash}"]`);
            }
            if (!targetBtn) {
                targetBtn = document.querySelector('#tab-content-management .sidebar-btn');
            }
            if (targetBtn) targetBtn.click();
        }
    }
}

function triggerAutoRefresh(container) {
    if (!container) return;
    if (!isElementInActiveTab(container)) return;

    const baseUrl = container.dataset.autoRefresh;
    const includeSelector = container.dataset.refreshInclude;
    let url = baseUrl;

    if (includeSelector) {
        const form = document.querySelector(includeSelector);
        const params = new URLSearchParams();
        params.set('page', '0');

        const urlParams = new URLSearchParams(window.location.search);
        const lang = urlParams.get('lang') || 'en';
        params.set('lang', lang);

        if (form) {
            const formData = new FormData(form);
            formData.forEach((value, key) => {
                params.append(key, value);
            });
        }

        url = `${baseUrl}?${params.toString()}`;
    }

    htmx.ajax('GET', url, {
        target: container,
        swap: 'innerHTML'
    });
}

// --- 更新侧边栏状态 ---
export function updateSidebarState(btn) {
    document.querySelectorAll('.sidebar-btn').forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    const hash = btn.getAttribute('data-hash');
    if (hash === 'tasks') {
        applyTaskFiltersToSidebar(btn);
    }
    if (hash) {
        window.location.hash = hash;
    }
}

function applyTaskFiltersToSidebar(btn) {
    const filters = getStoredTasksFilters();
    const baseUrl = btn.dataset.baseUrl || btn.getAttribute('hx-get') || '';
    if (!btn.dataset.baseUrl) {
        btn.dataset.baseUrl = baseUrl;
    }
    if (!filters) {
        btn.setAttribute('hx-get', btn.dataset.baseUrl || baseUrl);
        return;
    }
    const base = btn.dataset.baseUrl || baseUrl;
    if (!base) return;
    const url = new URL(base, window.location.origin);
    ['status', 'task_type', 'account_id'].forEach((key) => {
        url.searchParams.delete(key);
    });
    const queryParts = buildQueryParts(filters);
    queryParts.forEach((part) => {
        const [key, value] = part.split('=');
        if (!key) return;
        url.searchParams.append(decodeURIComponent(key), decodeURIComponent(value || ''));
    });
    btn.setAttribute('hx-get', url.pathname + url.search);
}

// --- 恢复 Tab ---
export function restoreTab() {
    const hash = window.location.hash.replace('#', '');
    let tabName = null;

    if (hash === 'records' || hash === 'management' || hash === 'owned-cards') {
        tabName = hash;
    } else if (['accounts', 'plans', 'tasks', 'metadata', 'friendships'].includes(hash)) {
        tabName = 'management';
    } else {
        tabName = localStorage.getItem(STORAGE_KEY_TAB);
    }

    if (!tabName) {
        tabName = 'records';
    }
    if (hash && ['accounts', 'plans', 'tasks', 'metadata', 'friendships'].includes(hash)) {
        switchTab('management', { preserveHash: true, preferHash: hash });
        return;
    }
    const btn = document.getElementById(`tab-btn-${tabName}`);
    if (btn) {
        btn.click();
    }
}
