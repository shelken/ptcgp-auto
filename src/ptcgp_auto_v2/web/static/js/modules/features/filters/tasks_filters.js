import { initCustomSelects } from '../../custom_select.js';
import { saveFormFilters, applyFormFilters } from './shared_form.js';

const STORAGE_KEY_TASKS_FILTERS = 'ptcgp_tasks_filters';

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

/**
 * 将缓存的任务筛选参数应用到侧栏 tasks 按钮请求中。
 * 仅负责任务页业务参数，不影响全局事件层。
 */
export function applyTasksSidebarRequestParams(button) {
    if (!(button instanceof Element)) return;

    const baseUrl = button.dataset.baseUrl || button.getAttribute('hx-get') || '';
    if (!button.dataset.baseUrl && baseUrl) {
        button.dataset.baseUrl = baseUrl;
    }

    const base = button.dataset.baseUrl || baseUrl;
    if (!base) return;

    const filters = getStoredTasksFilters();
    const url = new URL(base, window.location.origin);

    ['status', 'task_type', 'account_id', 'sort_by', 'sort_order', 'page', 'page_size'].forEach((key) => {
        url.searchParams.delete(key);
    });

    const appendParam = (key, value) => {
        if (value === '' || value === null || value === undefined) return;
        if (Array.isArray(value)) {
            value
                .map((item) => (item == null ? '' : String(item).trim()))
                .filter(Boolean)
                .forEach((item) => url.searchParams.append(key, item));
            return;
        }
        const text = String(value).trim();
        if (!text) return;
        url.searchParams.set(key, text);
    };

    if (filters) {
        appendParam('status', filters.status);
        appendParam('task_type', filters.task_type);
        appendParam('account_id', filters.account_id);
        appendParam('sort_by', filters.sort_by);
        appendParam('sort_order', filters.sort_order);
        appendParam('page', filters.page);
        appendParam('page_size', filters.page_size);
    }

    button.setAttribute('hx-get', url.pathname + url.search);
    if (window.htmx && typeof window.htmx.process === 'function') {
        window.htmx.process(button);
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

    // 只做 UI 回填，不在恢复阶段主动触发请求。
    // 任务列表首次数据应由入口请求一次性返回，避免出现双请求。
    form.dataset.restoreApplied = 'true';
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
