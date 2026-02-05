import { showToast, isElementInActiveTab } from './utils.js';
import { initCustomSelects, reinitCustomSelect } from './custom_select.js';

const STORAGE_KEY_FILTERS = 'ptcgp_filters';
const STORAGE_KEY_OWNED_FILTERS = 'ptcgp_owned_filters';
const STORAGE_KEY_TASKS_FILTERS = 'ptcgp_tasks_filters';

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
    saveFormFilters('owned-filter-form', STORAGE_KEY_OWNED_FILTERS, ['#owned-sort-select']);
    updateOwnedFilterGroupsState();
}

// --- 保存任务筛选 ---
export function saveTasksFilters() {
    saveFormFilters('task-filter-form', STORAGE_KEY_TASKS_FILTERS);
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

    if (form.dataset.restoreTrigger === 'true' && form.dataset.restoreApplied !== 'true') {
        form.dataset.restoreApplied = 'true';
        form.dispatchEvent(new Event('change', { bubbles: true }));
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
        const currentSort = sortInput.value || 'last_completed_at';
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
        summary.innerHTML = '';
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
    summary.innerHTML = items.map((item) => (
        `<button type="button" class="owned-filter-chip" data-input-id="${item.id}" onclick="toggleOwnedFilterChip('${item.id}')">${item.text}</button>`
    )).join('');
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
    document.querySelectorAll('.owned-filter-checkbox').forEach(el => el.checked = false);
    const accountInput = document.querySelector('#owned-filter-form input[name="account_id"]');
    if (accountInput) accountInput.value = '';
    localStorage.removeItem(STORAGE_KEY_OWNED_FILTERS);

    const sortSelect = document.getElementById('owned-sort-select');
    if (sortSelect) {
        sortSelect.value = 'rarity';
        if (sortSelect.classList.contains('custom-select-initialized')) {
            reinitCustomSelect(sortSelect);
        }
    }

    document.querySelectorAll('[data-filter-group]').forEach((group) => {
        updateOwnedFilterGroupSummary(group);
        group.classList.remove('is-open');
    });

    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    htmx.ajax('GET', `/api/owned-cards?page=0&lang=${lang}`, {target: '#owned-cards-container', swap: 'innerHTML'});
}

// --- 刷新记录列表 ---
export function refreshRecords() {
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

    htmx.ajax('GET', `/api/records?${params.toString()}`, {target: '#records-container', swap: 'innerHTML'});
    showToast('已刷新');
}

// --- 刷新已拥有卡牌列表 ---
export function refreshOwnedCards() {
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

    htmx.ajax('GET', `/api/owned-cards?${params.toString()}`, {target: '#owned-cards-container', swap: 'innerHTML'});
    showToast('已刷新');
}
