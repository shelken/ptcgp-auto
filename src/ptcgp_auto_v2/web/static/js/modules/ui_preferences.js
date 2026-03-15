const STORAGE_KEY_LANG = 'ptcgp_lang';
const STORAGE_KEY_VIEW_MODE = 'ptcgp_view_mode';
const STORAGE_KEY_RECORD_FILTER_PANEL = 'ptcgp_records_filter_panel_open';

// 记录页双列布局的桌面断点，需与 CSS `md` 断点保持一致。
const RECORDS_GRID_DESKTOP_MIN_WIDTH = 768;

let recordsGridObserver = null;
let recordsGridCompactionFrame = 0;
let recordsGridResizeBound = false;
let recordsGridLoadBound = false;

/** 清理记录页网格压缩产生的内联偏移。 */
function resetRecordsGridCompaction(container) {
    if (!container) return;

    container.style.marginBottom = '';
    for (const item of container.children) {
        item.style.position = '';
        item.style.top = '';
    }
}

/**
 * 压缩 records 双列网格中较短列后续卡片的占位，避免批次详情展开后出现整块空白。
 */
function applyRecordsGridCompaction() {
    const container = document.getElementById('records-container');
    if (!container) return;

    resetRecordsGridCompaction(container);

    if (!container.classList.contains('view-grid-layout') || window.innerWidth < RECORDS_GRID_DESKTOP_MIN_WIDTH) {
        return;
    }

    const items = Array.from(container.children);
    if (items.length < 3) return;

    let leftOffset = 0;
    let rightOffset = 0;

    for (let index = 0; index < items.length; index += 2) {
        const leftItem = items[index];
        const rightItem = items[index + 1] || null;

        if (leftOffset > 0.5) {
            leftItem.style.position = 'relative';
            leftItem.style.top = `-${leftOffset}px`;
        }

        if (rightItem && rightOffset > 0.5) {
            rightItem.style.position = 'relative';
            rightItem.style.top = `-${rightOffset}px`;
        }

        if (!rightItem) {
            continue;
        }

        const leftHeight = leftItem.getBoundingClientRect().height;
        const rightHeight = rightItem.getBoundingClientRect().height;
        const rowGap = leftHeight - rightHeight;

        if (rowGap > 0.5) {
            rightOffset += rowGap;
        } else if (rowGap < -0.5) {
            leftOffset += -rowGap;
        }
    }

    const maxOffset = Math.max(leftOffset, rightOffset);
    if (maxOffset > 0.5) {
        container.style.marginBottom = `-${maxOffset}px`;
    }
}

/** 在布局稳定后统一重算记录页双列网格偏移。 */
export function scheduleRecordsGridCompaction() {
    if (recordsGridCompactionFrame) {
        cancelAnimationFrame(recordsGridCompactionFrame);
    }

    recordsGridCompactionFrame = requestAnimationFrame(() => {
        recordsGridCompactionFrame = requestAnimationFrame(() => {
            recordsGridCompactionFrame = 0;
            applyRecordsGridCompaction();
        });
    });
}

/** 初始化记录页双列网格压缩观察器。 */
function initRecordsGridCompaction() {
    const container = document.getElementById('records-container');
    if (!container) return;

    if (!(recordsGridObserver instanceof MutationObserver)) {
        recordsGridObserver = new MutationObserver(() => {
            scheduleRecordsGridCompaction();
        });
        recordsGridObserver.observe(container, { childList: true, subtree: true });
    }

    if (!recordsGridResizeBound) {
        window.addEventListener('resize', scheduleRecordsGridCompaction);
        recordsGridResizeBound = true;
    }

    if (!recordsGridLoadBound) {
        container.addEventListener('load', scheduleRecordsGridCompaction, true);
        recordsGridLoadBound = true;
    }

    scheduleRecordsGridCompaction();
}

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
    scheduleRecordsGridCompaction();
}

// --- 恢复视图模式 ---
export function restoreViewMode() {
    initRecordsGridCompaction();
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
