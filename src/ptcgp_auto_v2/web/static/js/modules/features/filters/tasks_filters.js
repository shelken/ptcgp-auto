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
