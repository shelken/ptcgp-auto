import { getModal } from './modal.js';
import { isElementInActiveTab, setButtonLoading, showToast, throttle } from './utils.js';
import { initCustomSelects } from './custom_select.js';
import { initTaskRemoteAccountSearch } from './features/filters/tasks_remote_account.js';
import {
    saveFilterCache,
    saveFilterCacheByElement,
    restoreFilterCachesInContext,
    initTaskSortControls,
} from './features/filters/index.js';
import { initSortable, initTasks } from './features/tasks.js';
import { initPlans } from './features/plans.js';
import { initInlineCardDrag, cardPreviewState, closeCardPreview } from './features/card_preview.js';
import { initDailyGiftDatePickers } from './features/daily_gift.js';
import { refreshAutoRefreshContainers } from './auto_refresh.js';
import { updateRelativeTimes } from './relative_time.js';
import { initExchangeCards } from './features/exchange_cards.js';
import { initTooltipLayer } from './features/tooltips.js';
import { handleActionClick } from './action_handlers.js';
import { syncManagementSidebarRequestUrls } from './tabs.js';
import {
    initOwnedCardModalPageSizeWarmup,
    refreshOwnedCardsStats,
    syncOwnedCardListState,
    updateOwnedCardModalRequest,
} from './features/owned_cards.js';

const htmxLoadingButtons = new WeakMap();
const RESIZE_THROTTLE_MS = 150;
const CUSTOM_SELECT_OBSERVER_ROOT_IDS = ['tab-content', 'modal-content', 'notification-panel-container', 'management-content'];
let inlineCardDragCleanup = null;

function hideGlobalLoader() {
    const loader = document.querySelector('.htmx-indicator');
    if (!(loader instanceof HTMLElement)) return;
    loader.classList.remove('flex');
    loader.classList.add('hidden');
}

function syncPartialState(root = document) {
    if (!(root instanceof Element) && root !== document) return;

    const scope = root === document ? document : root;
    syncOwnedCardListState(scope);

    const hasRecordsEndMarker = scope instanceof Element
        && scope.matches('[data-records-end="true"]');
    if (hasRecordsEndMarker || scope.querySelector('[data-records-end="true"]')) {
        const endMarker = document.getElementById('end-of-records');
        if (endMarker instanceof HTMLElement) {
            endMarker.classList.remove('hidden');
        }
        hideGlobalLoader();
    }
}

function shouldBlockSearchSubmit(form) {
    if (!(form instanceof HTMLFormElement)) return false;
    if (!form.matches('form[hx-get]')) return false;
    if (!form.closest('#management-content')) return false;
    const searchInput = form.querySelector('input[name="q"]');
    if (!(searchInput instanceof HTMLInputElement)) return false;
    const keyword = searchInput.value.trim();
    return keyword.length === 1;
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

// --- 绑定筛选表单通用事件 ---
function bindFilterFormEvents(form) {
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.dataset.filterCacheKey) return;

    // 处理筛选组摘要更新（data-update-filter-summary 属性）
    form.addEventListener('click', (event) => {
        const target = event.target;
        if (target?.tagName === 'LABEL' && target.classList.contains('filter-label')) {
            const updateSummary = form.dataset.updateFilterSummary;
            if (updateSummary) {
                requestAnimationFrame(() => {
                    // 触发筛选摘要更新事件
                    document.dispatchEvent(new CustomEvent('filter:updateSummary', {
                        detail: { formId: form.id }
                    }));
                });
            }
        }
    });

    // 处理筛选变更（data-track-filters 属性）
    form.addEventListener('change', (event) => {
        const trackSelector = form.dataset.trackFilters;
        if (trackSelector && event.target?.matches(trackSelector)) {
            requestAnimationFrame(() => {
                saveFilterCache(form);
                // 触发筛选变更事件供特定模块处理
                document.dispatchEvent(new CustomEvent('filter:changed', {
                    detail: { formId: form.id, input: event.target }
                }));
            });
        }
    });
}

// --- 初始化所有带缓存 key 的表单事件 ---
function bindAllFilterFormEvents() {
    document.querySelectorAll('form[data-filter-cache-key]').forEach((form) => {
        bindFilterFormEvents(form);
    });
}

function handleFilterCacheOnForm(form) {
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.dataset.filterCacheKey) return;

    saveFilterCache(form);

    // 触发表单缓存保存事件，供需要额外处理的模块监听
    document.dispatchEvent(new CustomEvent('filter:saved', {
        detail: { formId: form.id, form }
    }));

    syncManagementSidebarRequestUrls();
}

function saveFilterCacheForElement(element) {
    if (!(element instanceof Element)) return;
    saveFilterCacheByElement(element);
    syncManagementSidebarRequestUrls();
}

function observeCustomSelectRoots(observer) {
    if (!(observer instanceof MutationObserver)) return;

    CUSTOM_SELECT_OBSERVER_ROOT_IDS.forEach((rootId) => {
        const root = document.getElementById(rootId);
        if (!(root instanceof HTMLElement)) return;
        if (root.dataset.customSelectObserved === 'true') return;
        observer.observe(root, { childList: true, subtree: true });
        root.dataset.customSelectObserved = 'true';
    });
}

function bindMutationObserver() {
    if (window.customSelectObserver) return;

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
    window.customSelectObserver = observer;
    observeCustomSelectRoots(observer);
}

function bindHtmxRequestEvents() {
    document.body.addEventListener('htmx:configRequest', (event) => {
        updateOwnedCardModalRequest(event);
    });

    document.body.addEventListener('htmx:beforeRequest', (event) => {
        const elt = event.detail && event.detail.elt;
        const target = event.detail && event.detail.target;

        const requestForm = elt instanceof HTMLFormElement
            ? elt
            : (elt instanceof Element ? elt.closest('form') : null);
        if (shouldBlockSearchSubmit(requestForm)) {
            event.preventDefault();
            showToast(document.body.dataset.msgSearchMinLength || 'Search keyword must be at least 2 characters');
            return;
        }

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
            if (target.dataset.loaded !== undefined || target.dataset.trackLoadingState === 'true') {
                target.dataset.loading = 'true';
            }
        }

        // 处理懒加载触发器（data-lazy-load-scroll-aware 属性）
        const trigger = elt?.getAttribute('hx-trigger') || '';
        if (trigger.includes('revealed') && elt?.dataset.lazyLoadScrollAware === 'true') {
            const scrollKey = elt?.dataset.scrollKey;
            if (scrollKey && !window[scrollKey]) {
                event.preventDefault();
                return;
            }
        }

        // 请求前保存表单缓存
        if (requestForm?.dataset.filterCacheKey) {
            saveFilterCache(requestForm);
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
            // 只要容器显式声明了 data-loaded，就在成功请求后转为已加载。
            if (target.dataset.loaded !== undefined || target.dataset.trackLoadingState === 'true') {
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
}

export function bindAppEventHandlers(restoreRecordFilterPanelState) {
    const throttledRestoreRecordFilterPanelState = throttle(restoreRecordFilterPanelState, RESIZE_THROTTLE_MS);

    document.body.addEventListener('click', handleActionClick);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && cardPreviewState.isOpen) {
            closeCardPreview();
        }
    });

    document.body.addEventListener('htmx:load', (evt) => {
        // 先恢复缓存到表单字段，再初始化组件
        restoreFilterCachesInContext(evt.detail.elt);
        initCustomSelects(evt.detail.elt);
        initDailyGiftDatePickers(evt.detail.elt);
        updateRelativeTimes(evt.detail.elt);
        initTaskSortControls(evt.detail.elt);
        initTaskRemoteAccountSearch(evt.detail.elt);
        initExchangeCards(evt.detail.elt);
        initPlans(evt.detail.elt);
        initTasks(evt.detail.elt);
        syncManagementSidebarRequestUrls();
        syncPartialState(evt.detail.elt);
    });

    document.body.addEventListener('change', (event) => {
        const target = event.target;
        if (!(target instanceof Element)) return;

        const linkedForm = target instanceof HTMLElement ? target.form : null;
        const cachedForm = target.closest('form[data-filter-cache-key]')
            || (linkedForm instanceof HTMLFormElement ? linkedForm : null);
        handleFilterCacheOnForm(cachedForm);

        const actionElement = target.closest('[data-action]');
        if (!actionElement) return;
        const action = actionElement.dataset.action;
        if (action === 'save-tasks-filters') {
            if (!(actionElement instanceof HTMLFormElement)) return;
            const pageInput = actionElement.querySelector('#task-page');
            if (pageInput instanceof HTMLInputElement) {
                pageInput.value = '0';
            }
            handleFilterCacheOnForm(actionElement);
            return;
        }
    });

    document.body.addEventListener('input', (event) => {
        const target = event.target;
        if (!(target instanceof Element)) return;

        saveFilterCacheForElement(target);
    });

    document.body.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter') return;
        if (event.isComposing) return;
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        if (target.tagName === 'TEXTAREA') return;
        if (target.classList.contains('custom-select-search')) return;

        const form = target.closest('form[hx-get]');
        if (!(form instanceof HTMLFormElement)) return;
        if (!form.closest('#management-content')) return;

        event.preventDefault();
        form.requestSubmit();
    });

    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;

        if (shouldBlockSearchSubmit(form)) {
            event.preventDefault();
            showToast(document.body.dataset.msgSearchMinLength || 'Search keyword must be at least 2 characters');
            return;
        }

        const action = form.dataset.action;
        handleFilterCacheOnForm(form);
        if (!action) return;

        // 触发表单提交事件，供特定模块监听处理
        document.dispatchEvent(new CustomEvent('form:submitted', {
            detail: { action, form }
        }));
    });

    bindAllFilterFormEvents();

    document.body.addEventListener('htmx:afterSwap', (evt) => {
        if (evt.detail && evt.detail.target && evt.detail.target.id === 'modal-content') {
            getModal().openFromSwap();
        }
        if (evt.detail && evt.detail.target && evt.detail.target.id === 'owned-cards-container') {
            refreshOwnedCardsStats();
        }
        // 使用 evt.detail.elt（新加载的元素）而不是 target（旧目标）
        const newContent = evt.detail.elt || evt.detail.target;
        if (newContent) {
            updateRelativeTimes(newContent);
            syncManagementSidebarRequestUrls();
            syncPartialState(newContent);
            observeCustomSelectRoots(window.customSelectObserver);
        }
    });

    document.addEventListener('modal:opened', (e) => {
        const modalContent = e.detail.modal.content;
        initCustomSelects(modalContent);
        if (modalContent.querySelector('.sortable-list')) {
            initSortable(modalContent);
        }
        if (inlineCardDragCleanup) {
            inlineCardDragCleanup();
            inlineCardDragCleanup = null;
        }
        inlineCardDragCleanup = initInlineCardDrag('modal-card-preview', '.owned-card-shine');
    });

    document.addEventListener('modal:closed', () => {
        if (!inlineCardDragCleanup) return;
        inlineCardDragCleanup();
        inlineCardDragCleanup = null;
    });

    const triggerAutoRefreshAll = () => {
        const now = Date.now();
        if (window.lastAutoRefreshAt && now - window.lastAutoRefreshAt < 500) {
            return;
        }
        const refreshedCount = refreshAutoRefreshContainers(document, { requireVisible: true });
        if (refreshedCount > 0) {
            window.lastAutoRefreshAt = now;
        }
    };

    document.addEventListener('visibilitychange', triggerAutoRefreshAll);
    window.addEventListener('focus', triggerAutoRefreshAll);
    window.addEventListener('resize', throttledRestoreRecordFilterPanelState);

    bindHtmxRequestEvents();

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
        // 标记当前激活的滚动感知标签为已滚动
        if (window.activeScrollAwareTab) {
            window[window.activeScrollAwareTab] = true;
        }
    }, { passive: true });

    updateRelativeTimes(document);
    if (!window.relativeTimeTimer) {
        window.relativeTimeTimer = setInterval(() => {
            updateRelativeTimes(document);
        }, 60000);
    }

    bindMutationObserver();

    initTaskSortControls(document);
    initTaskRemoteAccountSearch(document);
    initExchangeCards(document);
    initPlans(document);
    initTasks(document);
    initTooltipLayer();
    initOwnedCardModalPageSizeWarmup();
    syncPartialState(document);
}
