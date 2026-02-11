import { getModal } from './modal.js';
import { isElementInActiveTab, showToast } from './utils.js';
import { initCustomSelects } from './custom_select.js';
import {
    clearFilters,
    restoreFilters,
    refreshRecords,
    refreshOwnedCards,
    clearOwnedFilters,
    clearOwnedFilterGroup,
    restoreOwnedFilters,
    restoreTasksFilters,
    updateOwnedFilterGroupsState,
    toggleOwnedFilterGroup,
    toggleOwnedFilterChip,
    saveTasksFilters,
    updateTaskResetButtonState,
    saveOwnedFilters,
    saveFilters,
    initTaskSortControls,
} from './filters.js';
import { restoreOwnedGridCols, setOwnedGridCols, toggleOwnedCounts } from './owned_cards.js';
import { initSortable, updateIntervalSeconds, updateTaskItemState } from './tasks.js';
import { addPlan, removePlan, savePlans } from './plans.js';
import { cardPreviewState, closeCardPreview, openCardPreview } from './card_preview.js';
import { restoreTab, currentTabName, switchTab, updateSidebarState } from './tabs.js';
import { initDailyGiftDatePickers } from './daily_gift.js';

const STORAGE_KEY_LANG = 'ptcgp_lang';
const STORAGE_KEY_VIEW_MODE = 'ptcgp_view_mode';
const STORAGE_KEY_THEME = 'ptcgp_theme';
const STORAGE_KEY_RECORD_FILTER_PANEL = 'ptcgp_records_filter_panel_open';
const htmxLoadingButtons = new WeakMap();

function setButtonLoading(button, loading) {
    if (!button) return;

    if (loading) {
        if (button.dataset.loadingActive === '1') return;
        button.dataset.loadingActive = '1';
        button.dataset.prevDisabled = button.disabled ? '1' : '0';
        button.disabled = true;
        button.classList.add('btn-loading');
        button.setAttribute('aria-busy', 'true');
        return;
    }

    if (button.dataset.loadingActive !== '1') return;
    button.classList.remove('btn-loading');
    button.removeAttribute('aria-busy');
    if (button.dataset.prevDisabled !== '1') {
        button.disabled = false;
    }
    delete button.dataset.loadingActive;
    delete button.dataset.prevDisabled;
}

function resolveRequestButton(detail) {
    const elt = detail && detail.elt;
    if (!elt || !(elt instanceof Element)) return null;

    if (elt.matches('button, input[type="submit"]')) {
        return elt;
    }

    if (elt.tagName === 'FORM') {
        const active = document.activeElement;
        if (active instanceof Element
            && elt.contains(active)
            && active.matches('button, input[type="submit"]')) {
            return active;
        }
        return elt.querySelector('button[type="submit"], button:not([type]), input[type="submit"]');
    }

    return elt.closest('button, input[type="submit"]');
}

function toggleSection(sectionId, iconId = null) {
    if (!sectionId) return;
    const section = document.getElementById(sectionId);
    if (!section) return;

    const shouldShow = section.classList.contains('hidden');
    section.classList.toggle('hidden', !shouldShow);

    if (!iconId) return;
    const icon = document.getElementById(iconId);
    if (!icon) return;
    icon.style.transform = shouldShow ? 'rotate(0deg)' : 'rotate(-90deg)';
}

async function copyTextWithToast(text, message) {
    if (!text) return;
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
        } else {
            const input = document.createElement('textarea');
            input.value = text;
            input.style.position = 'fixed';
            input.style.opacity = '0';
            document.body.appendChild(input);
            input.focus();
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
        }
        showToast(message || 'Copied!');
    } catch (error) {
        console.error('复制失败:', error);
    }
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

function setRecordFilterPanelOpen(open) {
    const panel = document.getElementById('records-filter-panel');
    const toggleBtn = document.querySelector('[data-action="toggle-record-filters"]');
    if (!panel || !toggleBtn) return;

    panel.classList.toggle('is-collapsed', !open);
    toggleBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    toggleBtn.classList.toggle('active', open);
}

function restoreRecordFilterPanelState() {
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

function toggleRecordFilterPanel() {
    const panel = document.getElementById('records-filter-panel');
    if (!panel) return;
    const shouldOpen = panel.classList.contains('is-collapsed');
    setRecordFilterPanelOpen(shouldOpen);
    localStorage.setItem(STORAGE_KEY_RECORD_FILTER_PANEL, shouldOpen ? '1' : '0');
}

// --- 自动刷新列表 ---
function autoRefreshList(container) {
    if (!container) return;
    if (!isElementInActiveTab(container)) return;
    if (container.dataset.loaded && container.dataset.loaded !== 'true') return;
    if (
        container.id === 'owned-cards-container'
        && window.pauseOwnedCardsAutoRefreshUntil
        && Date.now() < window.pauseOwnedCardsAutoRefreshUntil
    ) {
        return;
    }

    const baseUrl = container.dataset.autoRefresh;
    const includeSelector = container.dataset.refreshInclude;
    const swap = container.dataset.refreshSwap || 'innerHTML';
    const targetSelector = container.dataset.refreshTarget;
    const target = targetSelector ? document.querySelector(targetSelector) : container;
    if (target && target.dataset && target.dataset.refreshing === '1') {
        return;
    }
    if (target && target.dataset) {
        if (target.dataset.refreshing === '1') {
            return;
        }
        target.dataset.refreshing = '1';
    }

    let url = baseUrl;

    if (includeSelector) {
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

        url = `${baseUrl}?${params.toString()}`;
    }

    htmx.ajax('GET', url, {
        target: target || container,
        swap
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

function handleActionClick(event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const actionButton = target.closest('[data-action]');
    if (!actionButton) return;
    const { action } = actionButton.dataset;

    if (action === 'set-lang' && actionButton.dataset.lang) {
        setLang(actionButton.dataset.lang);
        return;
    }

    if (action === 'switch-tab' && actionButton.dataset.tab) {
        switchTab(actionButton.dataset.tab);
        return;
    }

    if (action === 'set-view-mode' && actionButton.dataset.mode) {
        setViewMode(actionButton.dataset.mode);
        return;
    }

    if (action === 'toggle-owned-filter-group') {
        toggleOwnedFilterGroup(actionButton);
        return;
    }

    if (action === 'toggle-owned-filter-chip') {
        const inputId = actionButton.dataset.inputId;
        if (inputId) {
            toggleOwnedFilterChip(inputId);
        }
        return;
    }

    if (action === 'set-owned-grid-cols') {
        setOwnedGridCols(actionButton.dataset.cols);
        return;
    }

    if (action === 'toggle-owned-counts') {
        toggleOwnedCounts();
        return;
    }

    if (action === 'update-sidebar-state') {
        updateSidebarState(actionButton);
        return;
    }

    if (action === 'refresh-records') {
        refreshRecords(actionButton);
        return;
    }

    if (action === 'clear-record-filters') {
        clearFilters();
        return;
    }

    if (action === 'toggle-record-filters') {
        toggleRecordFilterPanel();
        return;
    }

    if (action === 'refresh-owned-cards') {
        refreshOwnedCards(actionButton);
        return;
    }

    if (action === 'clear-owned-filters') {
        clearOwnedFilters();
        return;
    }

    if (action === 'clear-owned-filter-group') {
        clearOwnedFilterGroup(actionButton);
        return;
    }

    if (action === 'save-account-plans') {
        savePlans(actionButton);
        return;
    }

    if (action === 'remove-plan') {
        removePlan(actionButton);
        return;
    }

    if (action === 'open-card-preview') {
        openCardPreview(actionButton);
        return;
    }

    if (action === 'close-modal') {
        getModal().close();
        return;
    }

    if (action === 'toggle-section') {
        toggleSection(actionButton.dataset.targetId, actionButton.dataset.iconId || null);
        return;
    }

    if (action === 'copy-text') {
        copyTextWithToast(actionButton.dataset.copyText, actionButton.dataset.copyToast);
        return;
    }

    if (action === 'set-daily-gift-date' && actionButton.dataset.date) {
        const dateValue = actionButton.dataset.date;
        const form = actionButton.closest('form');
        if (form) {
            const valueInput = form.querySelector('[data-role="value"]');
            const labelEl = form.querySelector('[data-role="label"]');
            if (valueInput) valueInput.value = dateValue;
            if (labelEl) labelEl.textContent = dateValue;
        }
        const stateInput = document.querySelector('#daily-gift-state-form input[name="biz_date_local"]');
        if (stateInput) stateInput.value = dateValue;
    }
}

// --- 初始化入口 ---
export function initApp() {
    document.addEventListener('DOMContentLoaded', () => {
        initLang();
        restoreTheme();
        document.body.addEventListener('click', handleActionClick);
        restoreTab();
        if (currentTabName === 'records') {
            restoreFilters();
        }
        if (currentTabName === 'owned-cards') {
            restoreOwnedFilters();
        }
        updateOwnedFilterGroupsState();
        restoreViewMode();
        restoreRecordFilterPanelState();
        restoreOwnedGridCols();
        initCustomSelects(document);
        initDailyGiftDatePickers(document);

        const hash = window.location.hash.replace('#', '');
        if (hash && ['accounts', 'plans', 'tasks', 'metadata', 'friendships', 'daily-gift'].includes(hash)) {
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
            initDailyGiftDatePickers(evt.detail.elt);
            updateRelativeTimes(evt.detail.elt);
            restoreTasksFilters(evt.detail.elt);
            initTaskSortControls(evt.detail.elt);
        });

        document.body.addEventListener('change', (event) => {
            if (event.target && event.target.classList.contains('owned-filter-checkbox')) {
                updateOwnedFilterGroupsState();
            }
        });

        document.body.addEventListener('change', (event) => {
            const target = event.target;
            if (!(target instanceof Element)) return;
            const actionElement = target.closest('[data-action]');
            if (!actionElement) return;
            const action = actionElement.dataset.action;
            if (action === 'set-theme') {
                if (!(actionElement instanceof HTMLSelectElement)) return;
                setTheme(actionElement.value);
                return;
            }
            if (action === 'save-record-filters') {
                saveFilters();
                return;
            }
            if (action === 'save-owned-filters') {
                saveOwnedFilters();
                return;
            }
            if (action === 'save-tasks-filters') {
                if (!(actionElement instanceof HTMLFormElement)) return;
                saveTasksFilters();
                updateTaskResetButtonState(actionElement);
                return;
            }
            if (action === 'add-plan') {
                if (!(actionElement instanceof HTMLSelectElement)) return;
                addPlan();
                return;
            }
            if (action === 'update-task-item-state') {
                if (!(actionElement instanceof HTMLInputElement)) return;
                updateTaskItemState(actionElement);
                return;
            }
            if (action === 'toggle-interval-input') {
                if (!(actionElement instanceof HTMLSelectElement)) return;
                const targetId = actionElement.dataset.intervalTarget;
                if (!targetId) return;
                const intervalInput = document.getElementById(targetId);
                if (!intervalInput) return;
                intervalInput.classList.toggle('hidden', actionElement.value !== 'interval');
                return;
            }
            if (action === 'sync-friendship-state') {
                if (!(actionElement instanceof HTMLSelectElement)) return;
                const stateName = actionElement.dataset.stateName;
                if (!stateName) return;
                const stateInput = document.querySelector(`#friendship-state-form input[name="${stateName}"]`);
                if (stateInput) stateInput.value = actionElement.value;
            }
        });

        document.body.addEventListener('input', (event) => {
            const target = event.target;
            if (!(target instanceof Element)) return;
            const actionElement = target.closest('[data-action]');
            if (!actionElement) return;
            const action = actionElement.dataset.action;
            if (action === 'save-owned-filters-input') {
                saveOwnedFilters();
                return;
            }
            if (action === 'update-interval-seconds') {
                if (!(actionElement instanceof HTMLInputElement)) return;
                updateIntervalSeconds(actionElement);
            }
        });

        document.addEventListener('submit', (event) => {
            const form = event.target;
            if (!(form instanceof HTMLFormElement)) return;
            const action = form.dataset.action;
            if (!action) return;

            if (action === 'sync-daily-gift-submit') {
                const valueInput = form.querySelector('[data-role="value"]');
                const stateInput = document.querySelector('#daily-gift-state-form input[name="biz_date_local"]');
                if (valueInput && stateInput) {
                    stateInput.value = valueInput.value;
                }
                return;
            }

            if (action === 'sync-plan-intervals-submit') {
                form.querySelectorAll('[data-interval-group] input[data-interval-unit]').forEach((input) => {
                    if (input instanceof HTMLInputElement) {
                        updateIntervalSeconds(input);
                    }
                });
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

        const triggerAutoRefreshAll = () => {
            if (document.visibilityState !== 'visible') {
                return;
            }
            const now = Date.now();
            if (window.lastAutoRefreshAt && now - window.lastAutoRefreshAt < 500) {
                return;
            }
            window.lastAutoRefreshAt = now;
            document.querySelectorAll('[data-auto-refresh]').forEach(container => {
                autoRefreshList(container);
            });
        };

        document.addEventListener('visibilitychange', triggerAutoRefreshAll);
        window.addEventListener('focus', triggerAutoRefreshAll);
        window.addEventListener('resize', restoreRecordFilterPanelState);

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
            if (target && target.dataset) {
                target.dataset.refreshing = '1';
            }

            const trigger = elt ? elt.getAttribute('hx-trigger') || '' : '';
            const hxGet = elt ? elt.getAttribute('hx-get') || '' : '';
            if (
                trigger.includes('revealed')
                && hxGet.includes('/api/owned-cards')
                && !window.ownedCardsUserScrolled
            ) {
                event.preventDefault();
                return;
            }

            const requestButton = resolveRequestButton(event.detail);
            if (requestButton) {
                if (elt) {
                    htmxLoadingButtons.set(elt, requestButton);
                }
                setButtonLoading(requestButton, true);
            }
        });

        document.body.addEventListener('htmx:afterRequest', (event) => {
            const elt = event.detail && event.detail.elt;
            const target = event.detail && event.detail.target;
            if (target && target.dataset) {
                target.dataset.refreshing = '0';
                if (target.id === 'records-container' || target.id === 'owned-cards-container') {
                    target.dataset.loaded = 'true';
                    target.dataset.loading = 'false';
                }
            }

            const requestButton = elt ? htmxLoadingButtons.get(elt) : null;
            if (requestButton) {
                setButtonLoading(requestButton, false);
                htmxLoadingButtons.delete(elt);
            }

            if (event.detail && event.detail.successful && elt instanceof Element) {
                if (elt.matches('[data-close-modal-on-success="true"]')) {
                    getModal().close();
                }
            }
        });

        document.body.addEventListener('closeModal', () => {
            getModal().close();
        });

        document.body.addEventListener('showToast', (event) => {
            const detail = event.detail;
            if (!detail) return;
            if (typeof detail === 'string') {
                showToast(detail);
                return;
            }
            if (detail.message) {
                showToast(detail.message);
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

        initTaskSortControls(document);
    });
}
