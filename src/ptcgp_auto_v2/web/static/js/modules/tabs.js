import { syncSidebarRequestParams } from './features/filters/index.js';
import { refreshAutoRefreshContainers } from './auto_refresh.js';
import { isManagementHash } from './constants.js';

const STORAGE_KEY_TAB = 'ptcgp_active_tab';
const STORAGE_KEY_MANAGEMENT_HASH = 'ptcgp_management_hash';

// --- 当前 Tab 状态 ---
export let currentTabName = null;

// --- 切换 Tab ---
export function switchTab(tabName, options = {}) {
    const {
        preserveHash = false,
        preferHash = null,
        skipAutoSelect = false
    } = options;
    const currentHash = window.location.hash.replace('#', '');
    let initialHash = preferHash !== null ? preferHash : currentHash;
    if (
        tabName === 'management'
        && !isManagementHash(initialHash)
    ) {
        const rememberedHash = localStorage.getItem(STORAGE_KEY_MANAGEMENT_HASH);
        if (rememberedHash) {
            initialHash = rememberedHash;
        }
    }

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

    document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.remove('active');
        el.setAttribute('aria-selected', 'false');
    });
    const activeBtn = document.getElementById(`tab-btn-${tabName}`);
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.setAttribute('aria-selected', 'true');

        const newTitle = activeBtn.getAttribute('data-title');
        const titleEl = document.getElementById('main-title');
        if (newTitle && titleEl) {
            titleEl.textContent = newTitle;
        }

        const hash = activeBtn.getAttribute('data-hash');
        if (hash && !preserveHash) {
            if (tabName === 'management') {
                const rememberedHash = localStorage.getItem(STORAGE_KEY_MANAGEMENT_HASH);
                window.location.hash = rememberedHash || hash;
            } else {
                window.location.hash = hash;
            }
        }
    }

    const filters = document.getElementById('records-filters');
    if (filters) {
        filters.classList.toggle('hidden', tabName !== 'records');
    }

    if (tabName === 'owned-cards') {
        window.ownedCardsUserScrolled = false;
    }

    localStorage.setItem(STORAGE_KEY_TAB, tabName);

    // 派发 Tab 切换事件
    document.dispatchEvent(new CustomEvent('tab:switched', {
        detail: { tabName }
    }));

    let shouldRefreshSelectedTab = true;
    if (tabName === 'management' && !skipAutoSelect) {
        syncManagementSidebarRequestUrls();
        const content = document.getElementById('management-content');
        const hasContent = content.querySelector('table') || content.querySelector('form');

        if (!hasContent) {
            const hash = initialHash;
            let targetBtn = null;
            if (hash && isManagementHash(hash)) {
                targetBtn = document.querySelector(`.sidebar-btn[data-hash="${hash}"]`);
            }
            if (!targetBtn) {
                targetBtn = document.querySelector('#tab-content-management .sidebar-btn');
            }
            if (targetBtn) {
                shouldRefreshSelectedTab = false;
                targetBtn.click();
            }
        }
    }

    if (shouldRefreshSelectedTab && selected) {
        refreshAutoRefreshContainers(selected);
    }
}

// --- 更新侧边栏状态 ---
export function updateSidebarState(btn) {
    document.querySelectorAll('.sidebar-btn').forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    const hash = btn.getAttribute('data-hash');
    syncSidebarRequestParams(btn);
    if (hash) {
        if (isManagementHash(hash)) {
            localStorage.setItem(STORAGE_KEY_MANAGEMENT_HASH, hash);
        }
        window.location.hash = hash;
    }
}

export function syncManagementSidebarRequestUrls() {
    document.querySelectorAll('#tab-content-management .sidebar-btn[data-filter-cache-key][data-filter-param-keys]')
        .forEach((btn) => {
            syncSidebarRequestParams(btn);
        });
}

// --- 恢复 Tab ---
export function restoreTab() {
    let hash = window.location.hash.replace('#', '');
    if (hash === 'management') {
        const rememberedHash = localStorage.getItem(STORAGE_KEY_MANAGEMENT_HASH);
        if (rememberedHash) {
            hash = rememberedHash;
        }
    }
    let tabName = null;

    if (hash === 'records' || hash === 'management' || hash === 'owned-cards') {
        tabName = hash;
    } else if (isManagementHash(hash)) {
        tabName = 'management';
    } else {
        tabName = localStorage.getItem(STORAGE_KEY_TAB);
    }

    if (!tabName) {
        tabName = 'records';
    }
    if (hash && isManagementHash(hash)) {
        switchTab('management', { preserveHash: true, preferHash: hash });
        return;
    }
    const btn = document.getElementById(`tab-btn-${tabName}`);
    if (btn) {
        btn.click();
    }
}
