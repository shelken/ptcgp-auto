import { getModal } from './modal.js';
import { isElementInActiveTab } from './utils.js';
import { initCustomSelects } from './custom_select.js';
import {
    restoreFilters,
    restoreOwnedFilters,
    restoreTasksFilters,
    updateOwnedFilterGroupsState,
    saveOwnedFilters,
} from './filters.js';
import { restoreOwnedGridCols } from './owned_cards.js';
import { initSortable } from './tasks.js';
import { cardPreviewState, closeCardPreview } from './card_preview.js';
import { restoreTab, currentTabName } from './tabs.js';

const STORAGE_KEY_LANG = 'ptcgp_lang';
const STORAGE_KEY_VIEW_MODE = 'ptcgp_view_mode';
const STORAGE_KEY_THEME = 'ptcgp_theme';

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

// --- 主题设置 ---
export function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY_THEME, theme);
}

// --- 恢复主题 ---
export function restoreTheme() {
    const theme = localStorage.getItem(STORAGE_KEY_THEME) || 'brutalist';
    document.documentElement.setAttribute('data-theme', theme);

    const selector = document.getElementById('theme-selector');
    if (selector) {
        selector.value = theme;
    }
}

// --- 自动刷新列表 ---
function autoRefreshList(container) {
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

// --- 相对时间文本 ---
function getRelativeLabels(container) {
    return {
        locale: container.dataset.relativeLocale || 'en',
        justNow: container.dataset.relativeJustNow || 'just now',
        soon: container.dataset.relativeSoon || 'soon',
        minutes: container.dataset.relativeMinutes || 'min',
        hours: container.dataset.relativeHours || 'hr',
        days: container.dataset.relativeDays || 'day',
        ago: container.dataset.relativeAgo || 'ago',
        in: container.dataset.relativeIn || 'in'
    };
}

// --- 格式化相对时间 ---
function formatRelativeTime(target, labels) {
    const diffMs = target.getTime() - Date.now();
    const future = diffMs > 0;
    const absSec = Math.abs(diffMs) / 1000;

    if (absSec < 60) {
        return future ? labels.soon : labels.justNow;
    }

    let value = 0;
    let unit = labels.minutes;
    if (absSec < 3600) {
        value = Math.round(absSec / 60);
        unit = labels.minutes;
    } else if (absSec < 86400) {
        value = Math.round(absSec / 3600);
        unit = labels.hours;
    } else {
        value = Math.round(absSec / 86400);
        unit = labels.days;
    }

    if (labels.locale.startsWith('en')) {
        return future ? `${labels.in} ${value} ${unit}` : `${value} ${unit} ${labels.ago}`;
    }

    return `${value}${unit}${future ? labels.in : labels.ago}`;
}

// --- 更新相对时间 ---
export function updateRelativeTimes(root = document) {
    const containers = [];
    if (root && root.nodeType === 1 && root.matches && root.matches('[data-relative-locale]')) {
        containers.push(root);
    }
    if (root && root.nodeType === 1 && root.closest) {
        const closestContainer = root.closest('[data-relative-locale]');
        if (closestContainer && !containers.includes(closestContainer)) {
            containers.push(closestContainer);
        }
    }
    if (root && root.querySelectorAll) {
        containers.push(...root.querySelectorAll('[data-relative-locale]'));
    }
    containers.forEach((container) => {
        const labels = getRelativeLabels(container);
        container.querySelectorAll('.relative-time').forEach((el) => {
            const iso = el.dataset.iso;
            if (!iso) return;
            const date = new Date(iso);
            if (Number.isNaN(date.getTime())) return;
            el.textContent = formatRelativeTime(date, labels);
            if (el.dataset.tooltip) {
                el.setAttribute('data-tooltip', el.dataset.tooltip);
            }
        });
    });
}

// --- 初始化入口 ---
export function initApp() {
    document.addEventListener('DOMContentLoaded', () => {
        initLang();
        restoreTheme();
        restoreTab();
        if (currentTabName === 'records') {
            restoreFilters();
        }
        if (currentTabName === 'owned-cards') {
            restoreOwnedFilters();
        }
        updateOwnedFilterGroupsState();
        restoreViewMode();
        restoreOwnedGridCols();
        initCustomSelects(document);

        const hash = window.location.hash.replace('#', '');
        if (hash && ['accounts', 'plans', 'metadata'].includes(hash)) {
            const activeBtn = document.querySelector(`.sidebar-btn.active[data-hash="${hash}"]`);
            if (!activeBtn) {
                setTimeout(() => {
                    const targetBtn = document.querySelector(`.sidebar-btn[data-hash="${hash}"]`);
                    if (targetBtn) {
                        targetBtn.click();
                    }
                }, 0);
            }
        }

        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
        if (mediaQuery.matches) {
            document.documentElement.classList.add('reduce-motion');
        }
        mediaQuery.addEventListener('change', () => {
            if (mediaQuery.matches) {
                document.documentElement.classList.add('reduce-motion');
            } else {
                document.documentElement.classList.remove('reduce-motion');
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && cardPreviewState.isOpen) {
                closeCardPreview();
            }
        });

        document.body.addEventListener('htmx:load', function(evt) {
            initCustomSelects(evt.detail.elt);
            updateRelativeTimes(evt.detail.elt);
            restoreTasksFilters(evt.detail.elt);
        });

        document.body.addEventListener('change', (event) => {
            if (event.target && event.target.classList.contains('owned-filter-checkbox')) {
                updateOwnedFilterGroupsState();
            }
        });

        const ownedFilterForm = document.getElementById('owned-filter-form');
        if (ownedFilterForm) {
            ownedFilterForm.addEventListener('click', (event) => {
                const target = event.target;
                if (target && target.tagName === 'LABEL' && target.classList.contains('filter-label')) {
                    requestAnimationFrame(() => {
                        updateOwnedFilterGroupsState();
                    });
                }
            });

            ownedFilterForm.addEventListener('change', (event) => {
                if (event.target && event.target.classList.contains('owned-filter-checkbox')) {
                    requestAnimationFrame(() => {
                        saveOwnedFilters();
                        updateOwnedFilterGroupsState();
                    });
                }
            });
        }

        document.body.addEventListener('htmx:afterSwap', function(evt) {
            if (evt.detail && evt.detail.target && evt.detail.target.id === 'modal-content') {
                getModal().openFromSwap();
            }
            if (evt.detail && evt.detail.target) {
                updateRelativeTimes(evt.detail.target);
            }
        });

        document.addEventListener('modal:opened', (e) => {
            const modalContent = e.detail.modal.content;
            if (typeof initCustomSelects === 'function') {
                initCustomSelects(modalContent);
            }
            if (typeof initSortable === 'function' && modalContent.querySelector('.sortable-list')) {
                initSortable(modalContent);
            }
        });

        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                document.querySelectorAll('[data-auto-refresh]').forEach(container => {
                    autoRefreshList(container);
                });
            }
        });

        document.body.addEventListener('htmx:beforeRequest', (event) => {
            const elt = event.detail && event.detail.elt;
            const target = event.detail && event.detail.target;
            if (elt && !isElementInActiveTab(elt)) {
                event.preventDefault();
                return;
            }
            if (target && !isElementInActiveTab(target)) {
                event.preventDefault();
                return;
            }

            const trigger = elt ? elt.getAttribute('hx-trigger') || '' : '';
            const hxGet = elt ? elt.getAttribute('hx-get') || '' : '';
            if (
                trigger.includes('revealed')
                && hxGet.includes('/api/owned-cards')
                && !window.ownedCardsUserScrolled
            ) {
                event.preventDefault();
            }
        });

        window.addEventListener('scroll', () => {
            if (currentTabName === 'owned-cards') {
                window.ownedCardsUserScrolled = true;
            }
        }, { passive: true });

        updateRelativeTimes(document);
        if (!window.relativeTimeTimer) {
            window.relativeTimeTimer = setInterval(() => {
                updateRelativeTimes(document);
            }, 60000);
        }

        if (!window.customSelectObserver) {
            const observer = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    mutation.addedNodes.forEach((node) => {
                        if (!(node instanceof Element)) return;
                        if (node.matches && node.matches('select.js-custom-select')) {
                            initCustomSelects(node.parentNode || node);
                            return;
                        }
                        if (node.querySelector) {
                            const select = node.querySelector('select.js-custom-select:not(.custom-select-initialized)');
                            if (select) {
                                initCustomSelects(node);
                            }
                        }
                    });
                }
            });
            observer.observe(document.body, { childList: true, subtree: true });
            window.customSelectObserver = observer;
        }
    });
}
