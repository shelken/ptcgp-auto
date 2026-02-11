import { showToast, isElementInActiveTab } from './utils.js';
import { initCustomSelects, reinitCustomSelect } from './custom_select.js';

const STORAGE_KEY_FILTERS = 'ptcgp_filters';
const STORAGE_KEY_OWNED_FILTERS = 'ptcgp_owned_filters';
const STORAGE_KEY_TASKS_FILTERS = 'ptcgp_tasks_filters';

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

function refreshOwnedCardsByForm(form) {
    if (!form) return;
    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    const params = new URLSearchParams();
    params.set('page', '0');
    params.set('lang', lang);

    const formData = new FormData(form);
    formData.forEach((value, key) => {
        params.append(key, value);
    });

    htmx.ajax('GET', `/api/owned-cards?${params.toString()}`, {target: '#owned-cards-container', swap: 'innerHTML'});
}

// --- 筛选序列化 ---
export function serializeFormFilters(form, extraSelectors = []) {
    const formData = new FormData(form);
    const filters = {};

    for (const [key, value] of formData.entries()) {
        if (filters[key]) {
            if (Array.isArray(filters[key])) {
                filters[key].push(value);
            } else {
                filters[key] = [filters[key], value];
            }
        } else {
            filters[key] = value;
        }
    }

    extraSelectors.forEach((selector) => {
        const element = document.querySelector(selector);
        if (!element || !element.name) return;
        filters[element.name] = element.value || '';
    });

    return filters;
}

// --- 筛选回填 ---
export function applyFormFilters(form, filters, extraSelectors = []) {
    if (!filters) return;

    Object.entries(filters).forEach(([name, rawValue]) => {
        const values = Array.isArray(rawValue) ? rawValue : [rawValue];
        const elements = Array.from(form.querySelectorAll(`[name="${name}"]`));
        extraSelectors.forEach((selector) => {
            const element = document.querySelector(selector);
            if (element && element.name === name) {
                elements.push(element);
            }
        });

        elements.forEach((element) => {
            if (element.type === 'checkbox' || element.type === 'radio') {
                element.checked = values.includes(element.value);
            } else {
                element.value = values[0] ?? '';
                if (element.classList.contains('custom-select-initialized')) {
                    reinitCustomSelect(element);
                }
            }
        });
    });
}

// --- 构建查询参数 ---
export function buildQueryParts(filters) {
    const parts = [];
    if (!filters) return parts;
    Object.entries(filters).forEach(([name, rawValue]) => {
        const values = Array.isArray(rawValue) ? rawValue : [rawValue];
        values.forEach((value) => {
            if (value === '' || value === null || value === undefined) return;
            parts.push(`${encodeURIComponent(name)}=${encodeURIComponent(value)}`);
        });
    });
    return parts;
}

// --- 保存筛选 ---
export function saveFormFilters(formId, storageKey, extraSelectors = []) {
    const form = document.getElementById(formId);
    if (!form) return;
    const filters = serializeFormFilters(form, extraSelectors);
    localStorage.setItem(storageKey, JSON.stringify(filters));
}

// --- 保存记录筛选 ---
export function saveFilters() {
    saveFormFilters('filter-form', STORAGE_KEY_FILTERS);
}

// --- 保存已拥有卡牌筛选 ---
export function saveOwnedFilters() {
    if (window.suppressOwnedFilterSave) return;
    saveFormFilters('owned-filter-form', STORAGE_KEY_OWNED_FILTERS, ['#owned-sort-select']);
    updateOwnedFilterGroupsState();
}

// --- 保存任务筛选 ---
export function saveTasksFilters() {
    saveFormFilters('task-filter-form', STORAGE_KEY_TASKS_FILTERS);
    const form = document.getElementById('task-filter-form');
    updateTaskResetButtonState(form);
}

// --- 获取任务筛选缓存 ---
export function getStoredTasksFilters() {
    const stored = localStorage.getItem(STORAGE_KEY_TASKS_FILTERS);
    if (!stored) return null;
    try {
        return JSON.parse(stored);
    } catch (e) {
        console.error('Failed to parse task filters', e);
        return null;
    }
}

// --- 恢复记录筛选 ---
export function restoreFilters() {
    const stored = localStorage.getItem(STORAGE_KEY_FILTERS);
    let queryParts = [];

    if (stored) {
        try {
            const filters = JSON.parse(stored);
            const form = document.getElementById('filter-form');
            if (form) {
                initCustomSelects(form);
                applyFormFilters(form, filters);
            }
            queryParts = buildQueryParts(filters);
        } catch (e) {
            console.error('Failed to restore filters', e);
        }
    }

    const container = document.getElementById('records-container');
    if (container) {
        if (!isElementInActiveTab(container)) {
            return;
        }
        if (container.dataset.loaded === 'true' || container.dataset.loading === 'true') {
            return;
        }
        container.dataset.loading = 'true';
        const baseAttr = container.getAttribute('data-base-url') || container.getAttribute('data-url');
        let finalUrl = baseAttr;

        if (queryParts.length > 0) {
            finalUrl = baseAttr + '&' + queryParts.join('&');
        }

        htmx.ajax('GET', finalUrl, {target: '#records-container', swap: 'innerHTML'});
    }
}

// --- 恢复已拥有卡牌筛选 ---
export function restoreOwnedFilters() {
    const stored = localStorage.getItem(STORAGE_KEY_OWNED_FILTERS);
    let queryParts = [];
    const form = document.getElementById('owned-filter-form');
    if (!form) return;
    const sortSelect = document.getElementById('owned-sort-select');

    if (sortSelect && !stored) {
        sortSelect.value = 'acquired';
        if (sortSelect.classList.contains('custom-select-initialized')) {
            reinitCustomSelect(sortSelect);
        }
    }

    if (stored) {
        try {
            const filters = JSON.parse(stored);
            initCustomSelects(form);
            applyFormFilters(form, filters, ['#owned-sort-select']);
            queryParts = buildQueryParts(filters);
        } catch (e) {
            console.error('Failed to restore owned filters', e);
        }
    }

    updateOwnedFilterGroupsState();

    const container = document.getElementById('owned-cards-container');
    if (container) {
        if (!isElementInActiveTab(container)) {
            return;
        }
        if (container.dataset.loaded === 'true' || container.dataset.loading === 'true') {
            return;
        }
        container.dataset.loading = 'true';
        const baseAttr = container.getAttribute('data-base-url') || container.getAttribute('data-url');
        let finalUrl = baseAttr;

        if (queryParts.length > 0) {
            finalUrl = baseAttr + '&' + queryParts.join('&');
        }

        htmx.ajax('GET', finalUrl, {target: '#owned-cards-container', swap: 'innerHTML'});
    }
}

// --- 恢复任务筛选 ---
export function restoreTasksFilters(context = document) {
    const form = context.querySelector('#task-filter-form');
    if (!form) return;

    const filters = getStoredTasksFilters();
    if (!filters) return;
    initCustomSelects(form);
    applyFormFilters(form, filters);
    updateTaskResetButtonState(form);

    if (form.dataset.restoreTrigger === 'true' && form.dataset.restoreApplied !== 'true') {
        form.dataset.restoreApplied = 'true';
        form.dispatchEvent(new Event('change', { bubbles: true }));
    }
}

// --- 更新重置按钮状态 ---
export function updateTaskResetButtonState(form) {
    if (!form) return;
    const statusSelect = form.querySelector('[name="status"]');
    const resetButton = document.getElementById('task-reset-completed-btn');
    const resetWrapper = document.getElementById('task-reset-completed-wrapper');
    if (!resetButton) return;
    const currentStatus = statusSelect ? statusSelect.value : '';
    const shouldDisable = currentStatus && currentStatus !== 'completed';
    resetButton.disabled = shouldDisable;
    resetButton.setAttribute('aria-disabled', shouldDisable ? 'true' : 'false');
    resetButton.classList.toggle('opacity-50', shouldDisable);
    resetButton.classList.toggle('cursor-not-allowed', shouldDisable);
    if (resetWrapper) {
        resetWrapper.dataset.tooltip = shouldDisable
            ? (resetWrapper.dataset.disabledTooltip || '')
            : '';
    }
}

// --- 初始化任务排序控件 ---
export function initTaskSortControls(context = document) {
    const form = context.querySelector('#task-filter-form') || document.querySelector('#task-filter-form');
    if (!form) return;
    const sortInput = form.querySelector('#task-sort-by');
    const orderInput = form.querySelector('#task-sort-order');
    if (!sortInput || !orderInput) return;

    let buttons = context.querySelectorAll('.task-sort-btn');
    if (!buttons.length) {
        buttons = document.querySelectorAll('.task-sort-btn');
    }
    if (!buttons.length) return;

    const updateArrows = () => {
        const currentSort = sortInput.value || 'dispatch_priority';
        const currentOrder = orderInput.value === 'asc' ? 'asc' : 'desc';
        buttons.forEach((button) => {
            const arrow = button.querySelector('.task-sort-arrow');
            if (!arrow) return;
            if (button.dataset.sortBy === currentSort) {
                arrow.textContent = currentOrder === 'asc' ? '↑' : '↓';
            } else {
                arrow.textContent = '';
            }
        });
    };

    const setSort = (sortBy, order) => {
        sortInput.value = sortBy;
        orderInput.value = order;
        updateArrows();
        orderInput.dispatchEvent(new Event('change', { bubbles: true }));
    };

    updateArrows();

    buttons.forEach((button) => {
        if (button.dataset.bound) return;
        button.addEventListener('click', () => {
            const sortBy = button.dataset.sortBy || 'last_completed_at';
            const defaultOrder = button.dataset.defaultOrder || 'desc';
            if (sortInput.value === sortBy) {
                const nextOrder = orderInput.value === 'asc' ? 'desc' : 'asc';
                setSort(sortBy, nextOrder);
                return;
            }
            setSort(sortBy, defaultOrder);
        });
        button.dataset.bound = 'true';
    });
}

// --- 检查筛选组是否有选择 ---
function hasOwnedFilterSelection(group) {
    const inputs = group.querySelectorAll('input[type="checkbox"]');
    return Array.from(inputs).some((input) => input.checked);
}

// --- 更新筛选组摘要 ---
function updateOwnedFilterGroupSummary(group) {
    const summary = group.querySelector('[data-filter-summary]');
    if (!summary) return;

    const checkedInputs = Array.from(group.querySelectorAll('input[type="checkbox"]'))
        .filter((input) => input.checked);

    if (checkedInputs.length === 0) {
        summary.classList.remove('has-items');
        summary.replaceChildren();
        return;
    }

    const items = checkedInputs.map((input) => {
        const label = group.querySelector(`label[for="${input.id}"]`);
        return {
            id: input.id,
            text: label ? label.textContent.trim() : input.value
        };
    });

    summary.classList.add('has-items');
    const fragment = document.createDocumentFragment();
    items.forEach((item) => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'owned-filter-chip';
        chip.dataset.action = 'toggle-owned-filter-chip';
        chip.dataset.inputId = item.id;
        chip.textContent = `${item.text} ×`;
        fragment.appendChild(chip);
    });
    summary.replaceChildren(fragment);
}

// --- 清空单个筛选组 ---
export function clearOwnedFilterGroup(button) {
    const group = button.closest('[data-filter-group]');
    const form = document.getElementById('owned-filter-form');
    if (!group || !form) return;

    const checkedInputs = Array.from(group.querySelectorAll('.owned-filter-checkbox')).filter((input) => input.checked);
    if (checkedInputs.length === 0) return;

    checkedInputs.forEach((input) => {
        input.checked = false;
    });

    updateOwnedFilterGroupsState();
    saveOwnedFilters();
    refreshOwnedCardsByForm(form);
}

// --- 切换筛选 Chip ---
export function toggleOwnedFilterChip(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.checked = !input.checked;
    input.dispatchEvent(new Event('change', { bubbles: true }));
}

// --- 展开/收起筛选组 ---
export function toggleOwnedFilterGroup(button) {
    const group = button.closest('[data-filter-group]');
    if (!group) return;

    const isOpen = group.classList.contains('is-open');
    updateOwnedFilterGroupSummary(group);

    if (isOpen) {
        group.classList.remove('is-open');
        return;
    }

    document.querySelectorAll('[data-filter-group].is-open').forEach((other) => {
        if (other === group) return;
        other.classList.remove('is-open');
    });

    group.classList.add('is-open');
}

// --- 更新全部筛选组状态 ---
export function updateOwnedFilterGroupsState() {
    document.querySelectorAll('[data-filter-group]').forEach((group) => {
        updateOwnedFilterGroupSummary(group);
    });
}

// --- 清除记录筛选 ---
export function clearFilters() {
    document.querySelectorAll('.filter-checkbox').forEach(el => el.checked = false);
    localStorage.removeItem(STORAGE_KEY_FILTERS);

    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    htmx.ajax('GET', `/api/records?page=0&lang=${lang}`, {target: '#records-container', swap: 'innerHTML'});
}

// --- 清除已拥有卡牌筛选 ---
export function clearOwnedFilters() {
    window.pauseOwnedCardsAutoRefreshUntil = Date.now() + 1500;
    window.suppressOwnedFilterSave = true;

    const sortSelect = document.getElementById('owned-sort-select');
    const currentSortBy = (sortSelect && sortSelect.value) ? sortSelect.value : 'acquired';

    document.querySelectorAll('.owned-filter-checkbox').forEach(el => el.checked = false);
    const accountInput = document.querySelector('#owned-filter-form input[name="account_id"]');
    if (accountInput) accountInput.value = '';
    if (sortSelect) {
        sortSelect.value = currentSortBy;
        if (sortSelect.classList.contains('custom-select-initialized')) {
            reinitCustomSelect(sortSelect);
        }
    }

    localStorage.setItem(STORAGE_KEY_OWNED_FILTERS, JSON.stringify({ sort_by: currentSortBy }));

    document.querySelectorAll('[data-filter-group]').forEach((group) => {
        updateOwnedFilterGroupSummary(group);
        group.classList.remove('is-open');
    });

    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    htmx.ajax('GET', `/api/owned-cards?page=0&lang=${lang}&sort_by=${encodeURIComponent(currentSortBy)}`, {target: '#owned-cards-container', swap: 'innerHTML'});

    setTimeout(() => {
        window.suppressOwnedFilterSave = false;
    }, 0);
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
    htmx.ajax('GET', `/api/records?${params.toString()}`, {target: '#records-container', swap: 'innerHTML'});
    showToast('已刷新');
}

// --- 刷新已拥有卡牌列表 ---
export function refreshOwnedCards(button = null) {
    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';

    const form = document.getElementById('owned-filter-form');
    const formData = form ? new FormData(form) : null;
    const params = new URLSearchParams();

    params.set('page', '0');
    params.set('lang', lang);

    if (formData) {
        formData.forEach((value, key) => {
            params.append(key, value);
        });
    }

    bindRequestLoading(button, 'owned-cards-container');
    htmx.ajax('GET', `/api/owned-cards?${params.toString()}`, {target: '#owned-cards-container', swap: 'innerHTML'});
    showToast('已刷新');
}
