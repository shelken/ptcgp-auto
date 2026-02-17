import { getModal } from './modal.js';
import { isElementInActiveTab, setButtonLoading, showToast } from './utils.js';
import { initCustomSelects } from './custom_select.js';
import {
    restoreTasksFilters,
    updateOwnedFilterGroupsState,
    saveTasksFilters,
    updateTaskResetButtonState,
    saveOwnedFilters,
    saveFilters,
    initTaskSortControls,
} from './features/filters/index.js';
import { updateIntervalSeconds, updateTaskItemState, initSortable } from './features/tasks.js';
import { addPlan } from './features/plans.js';
import { initInlineCardDrag, cardPreviewState, closeCardPreview } from './features/card_preview.js';
import { currentTabName } from './tabs.js';
import { initDailyGiftDatePickers } from './features/daily_gift.js';
import { buildAutoRefreshUrl } from './auto_refresh.js';
import { updateRelativeTimes } from './relative_time.js';
import { searchExchangeAccounts } from './features/exchange_cards.js';
import { handleActionClick } from './action_handlers.js';

const htmxLoadingButtons = new WeakMap();

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

    const url = includeSelector ? buildAutoRefreshUrl(container) : container.dataset.autoRefresh;
    if (!url) return;

    htmx.ajax('GET', url, {
        target: target || container,
        swap
    });
}

function bindOwnedFilterFormEvents() {
    const ownedFilterForm = document.getElementById('owned-filter-form');
    if (!ownedFilterForm) return;

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
    observer.observe(document.body, { childList: true, subtree: true });
    window.customSelectObserver = observer;
}

function bindHtmxRequestEvents() {
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
}

export function bindAppEventHandlers(restoreRecordFilterPanelState) {
    document.body.addEventListener('click', handleActionClick);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && cardPreviewState.isOpen) {
            closeCardPreview();
        }
    });

    document.body.addEventListener('htmx:load', (evt) => {
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
            return;
        }
        if (action === 'search-exchange-accounts') {
            searchExchangeAccounts(actionElement.value);
            return;
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

    bindOwnedFilterFormEvents();

    document.body.addEventListener('htmx:afterSwap', (evt) => {
        if (evt.detail && evt.detail.target && evt.detail.target.id === 'modal-content') {
            getModal().openFromSwap();
        }
        if (evt.detail && evt.detail.target) {
            updateRelativeTimes(evt.detail.target);
        }
    });

    document.addEventListener('modal:opened', (e) => {
        const modalContent = e.detail.modal.content;
        initCustomSelects(modalContent);
        if (modalContent.querySelector('.sortable-list')) {
            initSortable(modalContent);
        }
        initInlineCardDrag('modal-card-preview', '.owned-card-shine');
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
        document.querySelectorAll('[data-auto-refresh]').forEach((container) => {
            autoRefreshList(container);
        });
    };

    document.addEventListener('visibilitychange', triggerAutoRefreshAll);
    window.addEventListener('focus', triggerAutoRefreshAll);
    window.addEventListener('resize', restoreRecordFilterPanelState);

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

    bindMutationObserver();

    initTaskSortControls(document);
}
