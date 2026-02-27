import { checkEmpty } from './plans.js';

// --- 更新任务项状态 ---
export function updateTaskItemState(checkbox) {
    const taskItem = checkbox.closest('.task-item');
    if (!taskItem) return;
    const configContainer = taskItem.querySelector('[data-config-container]');

    if (checkbox.checked) {
        taskItem.classList.remove('opacity-50');
        if (configContainer) {
            configContainer.classList.remove('opacity-50');
        }
        taskItem.setAttribute('data-enabled', 'true');
    } else {
        taskItem.classList.add('opacity-50');
        if (configContainer) {
            configContainer.classList.add('opacity-50');
        }
        taskItem.setAttribute('data-enabled', 'false');
    }

    updateTaskOrder();
}

// --- 更新任务顺序 ---
export function updateTaskOrder() {
    const list = document.getElementById('tasks-list');
    if (!list) return;
    const items = list.querySelectorAll('.task-item');
    const orderedTaskTypes = [];

    items.forEach((item) => {
        const taskType = item.getAttribute('data-task-type');
        const isEnabled = item.getAttribute('data-enabled') === 'true';
        if (isEnabled) {
            orderedTaskTypes.push(taskType);
        }
    });

    const orderField = document.getElementById('task_order');
    if (orderField) {
        orderField.value = JSON.stringify(orderedTaskTypes);
    }
}

// --- 更新间隔秒数 ---
export function updateIntervalSeconds(inputEl) {
    if (!inputEl) return;
    const group = inputEl.closest('[data-interval-group]');
    if (!group) return;

    const parseUnit = (input, max) => {
        if (!input) return 0;
        const raw = input.value;
        if (raw === '') return 0;
        let value = parseInt(raw, 10);
        if (Number.isNaN(value)) value = 0;
        if (value < 0) {
            value = 0;
            input.value = '0';
        }
        if (typeof max === 'number' && value > max) {
            value = max;
            input.value = String(max);
        }
        return value;
    };

    const daysInput = group.querySelector("[data-interval-unit='days']");
    const hoursInput = group.querySelector("[data-interval-unit='hours']");
    const minutesInput = group.querySelector("[data-interval-unit='minutes']");
    const secondsInput = group.querySelector("[data-interval-unit='seconds']");

    const days = parseUnit(daysInput);
    const hours = parseUnit(hoursInput, 23);
    const minutes = parseUnit(minutesInput, 59);
    const seconds = parseUnit(secondsInput, 59);

    const total = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds;
    const hidden = group.querySelector('[data-interval-total]');
    if (hidden) {
        hidden.value = String(Math.max(0, total));
    }
}

// --- 初始化拖拽排序 ---
export function initSortable(context = document) {
    const taskList = context.querySelector('#tasks-list');
    if (taskList && !taskList.dataset.sortableInit) {
        new Sortable(taskList, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            dragClass: 'sortable-drag',
            handle: '.cursor-move',
            onEnd: function() {
                updateTaskOrder();
            }
        });
        taskList.dataset.sortableInit = 'true';
        updateTaskOrder();
    }

    const plansList = context.querySelector('#plans-list');
    if (plansList && !plansList.dataset.sortableInit) {
        new Sortable(plansList, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            dragClass: 'sortable-drag',
            handle: '.cursor-move',
            onEnd: function() {
                checkEmpty(plansList);
            }
        });
        plansList.dataset.sortableInit = 'true';
        checkEmpty(plansList);
    }
}

// --- 监听表单提交事件 ---
document.addEventListener('form:submitted', (event) => {
    const { action, form } = event.detail;

    if (action === 'sync-plan-intervals-submit') {
        form.querySelectorAll('[data-interval-group] input[data-interval-unit]').forEach((input) => {
            if (input instanceof HTMLInputElement) {
                updateIntervalSeconds(input);
            }
        });
    }
});
