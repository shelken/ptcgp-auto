import { checkEmpty } from './plans.js';

// --- 初始化任务模块事件 ---
export function initTasks(context = document) {
    const root = context instanceof Element ? context : document;

    // 监听 update-task-item-state change 事件
    root.querySelectorAll('[data-action="update-task-item-state"]').forEach((checkbox) => {
        if (checkbox.dataset.tasksBound === 'true') return;
        checkbox.addEventListener('change', () => {
            if (checkbox instanceof HTMLInputElement) {
                updateTaskItemState(checkbox);
            }
        });
        checkbox.dataset.tasksBound = 'true';
    });
}

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

// form:submitted 监听器已移除，计划表单的 interval 计算改为在 hx-on::before-request 中处理
