const STORAGE_KEY_LANG = 'ptcgp_lang';
const STORAGE_KEY_VIEW_MODE = 'ptcgp_view_mode';
const STORAGE_KEY_RECORD_FILTER_PANEL = 'ptcgp_records_filter_panel_open';

// --- 语言持久化 ---
export function setLang(lang) {
    localStorage.setItem(STORAGE_KEY_LANG, lang);
    document.cookie = `ptcgp_lang=${encodeURIComponent(lang)}; path=/; max-age=31536000`;
    const url = new URL(window.location);
    url.searchParams.set('lang', lang);
    window.location.href = url.toString();
}

// --- 初始化语言 ---
export function initLang() {
    const urlParams = new URLSearchParams(window.location.search);
    const currentLang = urlParams.get('lang');
    const storedLang = localStorage.getItem(STORAGE_KEY_LANG);

    if (!currentLang && storedLang) {
        const url = new URL(window.location);
        url.searchParams.set('lang', storedLang);
        window.location.replace(url.toString());
    } else if (currentLang && currentLang !== storedLang) {
        localStorage.setItem(STORAGE_KEY_LANG, currentLang);
    }
    if (currentLang) {
        document.cookie = `ptcgp_lang=${encodeURIComponent(currentLang)}; path=/; max-age=31536000`;
    }
}

// --- 视图模式 ---
export function setViewMode(mode) {
    const container = document.getElementById('records-container');
    const btnList = document.getElementById('btn-view-list');
    const btnGrid = document.getElementById('btn-view-grid');

    if (!container || !btnList || !btnGrid) return;

    if (mode === 'grid') {
        container.classList.add('view-grid-layout');
        container.classList.remove('space-y-12');
        btnList.classList.remove('active');
        btnGrid.classList.add('active');
    } else {
        container.classList.remove('view-grid-layout');
        container.classList.add('space-y-12');
        btnList.classList.add('active');
        btnGrid.classList.remove('active');
    }

    localStorage.setItem(STORAGE_KEY_VIEW_MODE, mode);
}

// --- 恢复视图模式 ---
export function restoreViewMode() {
    const mode = localStorage.getItem(STORAGE_KEY_VIEW_MODE) || 'grid';
    setViewMode(mode);
}

function setRecordFilterPanelOpen(open) {
    const panel = document.getElementById('records-filter-panel');
    const toggleBtn = document.querySelector('[data-action="toggle-record-filters"]');
    if (!panel || !toggleBtn) return;

    panel.classList.toggle('is-collapsed', !open);
    toggleBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    toggleBtn.classList.toggle('active', open);
}

export function restoreRecordFilterPanelState() {
    const panel = document.getElementById('records-filter-panel');
    const toggleBtn = document.querySelector('[data-action="toggle-record-filters"]');
    if (!panel || !toggleBtn) return;

    if (window.innerWidth >= 1024) {
        setRecordFilterPanelOpen(true);
        return;
    }

    const stored = localStorage.getItem(STORAGE_KEY_RECORD_FILTER_PANEL);
    const isOpen = stored === '1';
    setRecordFilterPanelOpen(isOpen);
}

export function toggleRecordFilterPanel() {
    const panel = document.getElementById('records-filter-panel');
    if (!panel) return;
    const shouldOpen = panel.classList.contains('is-collapsed');
    setRecordFilterPanelOpen(shouldOpen);
    localStorage.setItem(STORAGE_KEY_RECORD_FILTER_PANEL, shouldOpen ? '1' : '0');
}
