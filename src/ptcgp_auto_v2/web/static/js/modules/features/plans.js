import { showToast, setButtonLoading } from '../utils.js';
import { getModal } from '../modal.js';

// --- 初始化计划模块事件 ---
export function initPlans(context = document) {
    const root = context instanceof Element ? context : document;

    // 监听 add-plan change 事件
    root.querySelectorAll('[data-action="add-plan"]').forEach((select) => {
        if (select.dataset.plansBound === 'true') return;
        select.addEventListener('change', () => {
            if (select instanceof HTMLSelectElement) {
                addPlan();
            }
        });
        select.dataset.plansBound = 'true';
    });

    // 监听 toggle-interval-input change 事件
    root.querySelectorAll('[data-action="toggle-interval-input"]').forEach((el) => {
        if (el.dataset.intervalToggleBound === 'true') return;
        el.addEventListener('change', () => {
            if (!(el instanceof HTMLSelectElement)) return;
            const targetId = el.dataset.intervalTarget;
            if (!targetId) return;
            const intervalInput = document.getElementById(targetId);
            if (!intervalInput) return;
            intervalInput.classList.toggle('hidden', el.value !== 'interval');
        });
        el.dataset.intervalToggleBound = 'true';
    });
}

// --- 获取计划列表文本 ---
export function getPlansMessages(list) {
    return {
        emptyMessage: list.dataset.emptyMessage || 'No plans assigned. Add one above.',
        duplicateMessage: list.dataset.duplicateMessage || 'Plan already in list!',
        saveErrorMessage: list.dataset.saveErrorMessage || 'Error saving plans',
        saveSuccessMessage: list.dataset.saveSuccessMessage || 'Plans saved successfully!',
        labelActive: list.dataset.labelActive || 'ACTIVE'
    };
}

// --- 检查空状态 ---
export function checkEmpty(list = document.getElementById('plans-list')) {
    if (!list) return;
    const items = list.querySelectorAll('.plan-item');
    let msg = document.getElementById('empty-message');
    const messages = getPlansMessages(list);

    if (items.length === 0) {
        if (!msg) {
            msg = document.createElement('div');
            msg.id = 'empty-message';
            msg.className = 'text-center text-muted py-8 italic select-none';
            msg.textContent = messages.emptyMessage;
            list.appendChild(msg);
        }
        msg.style.display = 'block';
    } else if (msg) {
        msg.style.display = 'none';
    }
}

// --- 添加计划 ---
export function addPlan() {
    const list = document.getElementById('plans-list');
    if (!list) return;
    const messages = getPlansMessages(list);

    const select = document.getElementById('add-plan-select');
    if (!select) return;
    const planId = select.value;
    if (!planId) return;

    const option = select.options[select.selectedIndex];
    const planName = option.getAttribute('data-name');

    const existing = document.querySelector(`.plan-item[data-id="${planId}"]`);
    if (existing) {
        showToast(messages.duplicateMessage, 3000);
        return;
    }

    const item = document.createElement('div');
    item.className = 'plan-item flex items-center gap-3 p-3 border border-subtle bg-card shadow-sm group select-none cursor-move';
    item.dataset.id = planId;

    const handle = document.createElement('div');
    handle.className = 'cursor-move text-muted hover:text-theme p-1';
    handle.textContent = '☰';

    const content = document.createElement('div');
    content.className = 'flex-grow';

    const nameEl = document.createElement('div');
    nameEl.className = 'font-bold text-lg text-theme';
    nameEl.textContent = planName;

    const idEl = document.createElement('div');
    idEl.className = 'text-xs text-muted';
    idEl.textContent = `ID: ${planId}`;

    content.appendChild(nameEl);
    content.appendChild(idEl);

    const activeWrap = document.createElement('label');
    activeWrap.className = 'flex items-center gap-2 cursor-pointer';

    const activeLabel = document.createElement('span');
    activeLabel.className = 'text-xs font-bold uppercase text-theme';
    activeLabel.textContent = messages.labelActive;

    const activeInput = document.createElement('input');
    activeInput.type = 'checkbox';
    activeInput.className = 'plan-active-checkbox w-5 h-5 accent-theme border-theme focus:ring-0';
    activeInput.checked = true;

    activeWrap.appendChild(activeLabel);
    activeWrap.appendChild(activeInput);

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.dataset.action = 'remove-plan';
    removeBtn.className = 'text-red-500 font-bold px-2 hover:bg-subtle rounded transition-colors';
    removeBtn.textContent = '✕';

    item.appendChild(handle);
    item.appendChild(content);
    item.appendChild(activeWrap);
    item.appendChild(removeBtn);

    const msg = document.getElementById('empty-message');
    if (msg) msg.style.display = 'none';

    list.appendChild(item);

    select.value = '';
    select.dispatchEvent(new Event('change'));
}

// --- 删除计划 ---
export function removePlan(btn) {
    const list = document.getElementById('plans-list');
    if (!list) return;
    const item = btn.closest('.plan-item');
    if (!item) return;
    item.remove();
    checkEmpty(list);
}

// --- 保存计划 ---
export function savePlans(button = null) {
    const list = document.getElementById('plans-list');
    if (!list) return;
    const messages = getPlansMessages(list);
    const accountId = list.dataset.accountId;
    const lang = list.dataset.lang || 'en';

    if (!accountId) return;

    const items = list.querySelectorAll('.plan-item');
    const data = [];

    setButtonLoading(button, true);

    items.forEach((item) => {
        const id = item.getAttribute('data-id');
        const active = item.querySelector('.plan-active-checkbox').checked;
        data.push({
            plan_id: parseInt(id),
            is_active: active
        });
    });

    fetch(`/api/accounts/${accountId}/plans?lang=${lang}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (response.ok) {
            getModal().close();
            const refreshBtn = document.querySelector('[hx-get*="/management/accounts"]');
            if (refreshBtn) {
                htmx.trigger(refreshBtn, 'click');
            } else {
                htmx.ajax('GET', `/management/accounts?lang=${lang}`, '#management-content');
            }
            showToast(messages.saveSuccessMessage);
        } else {
            showToast(messages.saveErrorMessage, 3000);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast(messages.saveErrorMessage, 3000);
    })
    .finally(() => {
        setButtonLoading(button, false);
    });
}
