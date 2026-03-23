// --- 更新重置按钮状态 ---
function updateTaskResetButtonState(form) {
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

// --- 监听全局筛选事件 ---
document.addEventListener('filter:saved', (event) => {
    const { formId, form } = event.detail;
    if (formId === 'task-filter-form') {
        updateTaskResetButtonState(form);
    }
});

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

    const syncSortInputsWithUrl = () => {
        const params = new URLSearchParams(window.location.search);
        const urlSortBy = params.get('sort_by');
        const urlSortOrder = params.get('sort_order');
        const allowedSortBy = new Set([
            'dispatch_priority',
            'last_completed_at',
            'last_duration_seconds',
            'next_run_at',
        ]);

        if (urlSortBy && allowedSortBy.has(urlSortBy)) {
            sortInput.value = urlSortBy;
        }
        if (sortInput.value === 'dispatch_priority') {
            orderInput.value = 'asc';
            return;
        }
        if (urlSortOrder === 'asc' || urlSortOrder === 'desc') {
            orderInput.value = urlSortOrder;
        }
    };

    const updateArrows = () => {
        const currentSort = sortInput.value || 'dispatch_priority';
        const currentOrder = currentSort === 'dispatch_priority'
            ? 'asc'
            : (orderInput.value === 'asc' ? 'asc' : 'desc');
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

    syncSortInputsWithUrl();
    updateArrows();

    buttons.forEach((button) => {
        if (button.dataset.bound) return;
        button.addEventListener('click', () => {
            const sortBy = button.dataset.sortBy || 'last_completed_at';
            const defaultOrder = button.dataset.defaultOrder || 'desc';
            if (sortBy === 'dispatch_priority') {
                setSort(sortBy, 'asc');
                return;
            }
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
