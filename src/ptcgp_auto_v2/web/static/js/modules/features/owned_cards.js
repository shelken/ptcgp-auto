import { throttle } from '../utils.js';

const STORAGE_KEY_OWNED_COLS = 'ptcgp_owned_cols';
const STORAGE_KEY_OWNED_MODAL_PAGE_SIZE = 'ptcgp_owned_modal_page_size';
const OWNED_MODAL_PAGE_SIZE_RESIZE_THROTTLE_MS = 150;
let ownedCardModalProbeHost = null;
let ownedCardModalPageSize = null;
let ownedCardModalPageSizeStable = false;
let ownedCardModalPageSizeLastMeasured = null;
let ownedCardModalPageSizeStableCount = 0;
let ownedCardModalPageSizeTimer = null;
let pendingOwnedCardModalButton = null;
let replayingOwnedCardModalClick = false;
const throttledOwnedCardModalWarmup = throttle(scheduleOwnedCardModalPageSizeWarmup, OWNED_MODAL_PAGE_SIZE_RESIZE_THROTTLE_MS);

function restoreOwnedCardModalPageSize() {
    const rawValue = window.localStorage.getItem(STORAGE_KEY_OWNED_MODAL_PAGE_SIZE);
    const pageSize = Number.parseInt(rawValue || '', 10);
    if (Number.isNaN(pageSize) || pageSize <= 0) {
        return null;
    }
    return pageSize;
}

function persistOwnedCardModalPageSize(pageSize) {
    if (!Number.isInteger(pageSize) || pageSize <= 0) {
        return;
    }
    ownedCardModalPageSize = pageSize;
    window.localStorage.setItem(STORAGE_KEY_OWNED_MODAL_PAGE_SIZE, String(pageSize));
}

function ensureOwnedCardModalProbe() {
    if (ownedCardModalProbeHost instanceof HTMLElement) {
        return ownedCardModalProbeHost;
    }

    const template = document.getElementById('owned-card-modal-page-size-probe');
    if (!(template instanceof HTMLTemplateElement)) {
        return null;
    }

    const host = document.createElement('div');
    host.id = 'owned-card-modal-page-size-probe-host';
    host.setAttribute('aria-hidden', 'true');
    host.style.position = 'fixed';
    host.style.left = '-10000px';
    host.style.top = '0';
    host.style.visibility = 'hidden';
    host.style.pointerEvents = 'none';
    host.style.zIndex = '-1';
    host.appendChild(template.content.cloneNode(true));
    document.body.appendChild(host);
    ownedCardModalProbeHost = host;
    return host;
}

function updateOwnedCardModalProbeLayout(host) {
    const modalContainer = document.getElementById('modal-container');
    const modalContent = document.getElementById('modal-content');
    if (!(host instanceof HTMLElement) || !(modalContainer instanceof HTMLElement) || !(modalContent instanceof HTMLElement)) {
        return;
    }

    const containerStyle = window.getComputedStyle(modalContainer);
    const contentStyle = window.getComputedStyle(modalContent);
    const horizontalPadding = (
        parseFloat(containerStyle.paddingLeft || '0')
        + parseFloat(containerStyle.paddingRight || '0')
    );
    const maxWidth = parseFloat(contentStyle.maxWidth || '0');
    const availableWidth = Math.max(0, window.innerWidth - horizontalPadding);
    host.style.width = `${Math.min(availableWidth, maxWidth || availableWidth)}px`;
}

/**
 * 基于隐藏探针实测当前 DOM/CSS，计算拥有卡牌弹窗的表格 page_size。
 */
export function calculateOwnedCardModalPageSize() {
    const host = ensureOwnedCardModalProbe();
    if (!(host instanceof HTMLElement)) {
        return 10;
    }

    updateOwnedCardModalProbeLayout(host);

    const frame = host.querySelector('.owned-card-exchange-table-frame');
    const header = host.querySelector('.owned-card-exchange-table-frame thead');
    const sampleRow = host.querySelector('.owned-card-exchange-table-frame tbody tr');
    if (!(frame instanceof HTMLElement) || !(header instanceof HTMLElement) || !(sampleRow instanceof HTMLElement)) {
        return 10;
    }

    const headerHeight = header.getBoundingClientRect().height;
    const rowHeight = sampleRow.getBoundingClientRect().height;
    if (rowHeight <= 0) {
        return 10;
    }

    const availableHeight = Math.max(0, frame.clientHeight - headerHeight);
    const pageSize = Math.floor(availableHeight / rowHeight);
    return Math.max(1, pageSize);
}

function replayPendingOwnedCardModalRequest() {
    if (!(pendingOwnedCardModalButton instanceof HTMLElement) || !document.contains(pendingOwnedCardModalButton)) {
        pendingOwnedCardModalButton = null;
        return;
    }

    const button = pendingOwnedCardModalButton;
    pendingOwnedCardModalButton = null;
    replayingOwnedCardModalClick = true;
    window.setTimeout(() => {
        button.click();
        replayingOwnedCardModalClick = false;
    }, 0);
}

function warmOwnedCardModalPageSize() {
    window.clearTimeout(ownedCardModalPageSizeTimer);
    ownedCardModalPageSizeTimer = null;

    const pageSize = calculateOwnedCardModalPageSize();
    if (!Number.isInteger(pageSize) || pageSize <= 0) {
        ownedCardModalPageSizeStable = false;
        ownedCardModalPageSizeTimer = window.setTimeout(warmOwnedCardModalPageSize, 120);
        return;
    }

    persistOwnedCardModalPageSize(pageSize);
    if (ownedCardModalPageSizeLastMeasured === pageSize) {
        ownedCardModalPageSizeStableCount += 1;
    } else {
        ownedCardModalPageSizeLastMeasured = pageSize;
        ownedCardModalPageSizeStableCount = 1;
    }

    if (ownedCardModalPageSizeStableCount >= 2) {
        ownedCardModalPageSizeStable = true;
        replayPendingOwnedCardModalRequest();
        return;
    }

    ownedCardModalPageSizeStable = false;
    ownedCardModalPageSizeTimer = window.setTimeout(warmOwnedCardModalPageSize, 120);
}

function scheduleOwnedCardModalPageSizeWarmup() {
    if (ownedCardModalPageSizeTimer !== null) {
        return;
    }
    ownedCardModalPageSizeStable = false;
    ownedCardModalPageSizeLastMeasured = null;
    ownedCardModalPageSizeStableCount = 0;
    ownedCardModalPageSizeTimer = window.setTimeout(warmOwnedCardModalPageSize, 0);
}

function handleOwnedCardModalClick(event) {
    if (replayingOwnedCardModalClick) {
        return;
    }

    const target = event.target;
    if (!(target instanceof Element)) {
        return;
    }

    const button = target.closest('.owned-card[hx-get="/api/owned-cards/modal"]');
    if (!(button instanceof HTMLElement)) {
        return;
    }

    if (ownedCardModalPageSizeStable && Number.isInteger(ownedCardModalPageSize) && ownedCardModalPageSize > 0) {
        return;
    }

    pendingOwnedCardModalButton = button;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    scheduleOwnedCardModalPageSizeWarmup();
}

/**
 * 预热并缓存稳定的 page_size，避免首击时拿到样式未稳定的脏值。
 */
export function initOwnedCardModalPageSizeWarmup() {
    if (window.__ownedCardModalPageSizeWarmupBound) {
        return;
    }

    window.__ownedCardModalPageSizeWarmupBound = true;
    ownedCardModalPageSize = restoreOwnedCardModalPageSize();
    document.addEventListener('click', handleOwnedCardModalClick, true);
    window.addEventListener('load', scheduleOwnedCardModalPageSizeWarmup);
    window.addEventListener('resize', throttledOwnedCardModalWarmup);
    window.setTimeout(scheduleOwnedCardModalPageSizeWarmup, 0);
    window.setTimeout(scheduleOwnedCardModalPageSizeWarmup, 300);
}

/**
 * 在发起 modal 请求前注入 card_id/lang/page_size，确保只打开一次请求。
 */
export function updateOwnedCardModalRequest(event) {
    const elt = event.detail?.elt;
    if (!(elt instanceof Element)) return;
    if (!elt.matches('.owned-card[hx-get="/api/owned-cards/modal"]')) return;

    const { cardId, lang } = elt.dataset;
    if (!cardId || !lang) return;

    event.detail.parameters.card_id = cardId;
    event.detail.parameters.lang = lang;
    const pageSize = Number.isInteger(ownedCardModalPageSize) && ownedCardModalPageSize > 0
        ? ownedCardModalPageSize
        : calculateOwnedCardModalPageSize();
    event.detail.parameters.page_size = String(pageSize);
}

/**
 * 同步拥有卡牌列表的空状态和全局加载器。
 */
export function syncOwnedCardListState(root = document) {
    if (!(root instanceof Element) && root !== document) return;

    const scope = root === document ? document : root;
    const hasEmptyMarker = scope instanceof Element
        && scope.matches('[data-owned-cards-empty="true"]');
    if (!hasEmptyMarker && !scope.querySelector('[data-owned-cards-empty="true"]')) {
        return;
    }

    const loader = document.querySelector('.htmx-indicator');
    if (!(loader instanceof HTMLElement)) return;
    loader.classList.remove('flex');
    loader.classList.add('hidden');
}

// --- 设置已拥有卡牌网格列数 ---
export function setOwnedGridCols(value) {
    const container = document.getElementById('owned-cards-container');
    if (!container) return;
    const cols = parseInt(value, 10);
    if (Number.isNaN(cols)) return;

    container.style.setProperty('--owned-grid-cols', cols);
    const label = document.getElementById('owned-cols-value');
    if (label) label.textContent = cols;
    localStorage.setItem(STORAGE_KEY_OWNED_COLS, String(cols));

    document.querySelectorAll('.owned-cols-btn').forEach((button) => {
        const target = parseInt(button.dataset.cols, 10);
        if (target === cols) {
            button.classList.add('active');
            button.setAttribute('aria-pressed', 'true');
        } else {
            button.classList.remove('active');
            button.setAttribute('aria-pressed', 'false');
        }
    });
}

// --- 切换数量显示 ---
export function toggleOwnedCounts() {
    const container = document.getElementById('owned-cards-container');
    if (!container) return;
    container.classList.toggle('show-counts');

    const btn = document.getElementById('owned-counts-toggle');
    if (!btn) return;
    const showText = btn.dataset.showText || btn.textContent;
    const hideText = btn.dataset.hideText || btn.textContent;
    if (container.classList.contains('show-counts')) {
        btn.textContent = hideText;
    } else {
        btn.textContent = showText;
    }
}

// --- 恢复网格列数 ---
export function restoreOwnedGridCols() {
    const stored = localStorage.getItem(STORAGE_KEY_OWNED_COLS);
    const value = stored || '5';
    setOwnedGridCols(value);
}

// --- 监听 Tab 切换，设置滚动感知标签 ---
document.addEventListener('tab:switched', (event) => {
    const { tabName } = event.detail;
    // owned-cards 标签激活时，设置滚动感知键
    if (tabName === 'owned-cards') {
        window.activeScrollAwareTab = 'ownedCardsUserScrolled';
        scheduleOwnedCardModalPageSizeWarmup();
    } else {
        window.activeScrollAwareTab = null;
    }
});
