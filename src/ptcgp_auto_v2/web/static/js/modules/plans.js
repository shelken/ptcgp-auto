import { showToast } from './utils.js';

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
        alert(messages.duplicateMessage);
        return;
    }

    const template = `
        <div class="plan-item flex items-center gap-3 p-3 border border-subtle bg-card shadow-sm group select-none cursor-move" 
             data-id="${planId}">
            <div class="cursor-move text-muted hover:text-theme p-1">☰</div>
            <div class="flex-grow">
                <div class="font-bold text-lg text-theme">${planName}</div>
                <div class="text-xs text-muted">ID: ${planId}</div>
            </div>
            <label class="flex items-center gap-2 cursor-pointer">
                <span class="text-xs font-bold uppercase text-theme">${messages.labelActive}</span>
                <input type="checkbox" class="plan-active-checkbox w-5 h-5 accent-theme border-theme focus:ring-0" checked>
            </label>
            <button type="button" onclick="removePlan(this)" class="text-red-500 font-bold px-2 hover:bg-subtle rounded transition-colors">
                ✕
            </button>
        </div>
    `;

    const msg = document.getElementById('empty-message');
    if (msg) msg.style.display = 'none';

    const div = document.createElement('div');
    div.innerHTML = template.trim();
    const newItem = div.firstChild;
    list.appendChild(newItem);

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
export function savePlans() {
    const list = document.getElementById('plans-list');
    if (!list) return;
    const messages = getPlansMessages(list);
    const accountId = list.dataset.accountId;
    const lang = list.dataset.lang || 'en';

    if (!accountId) return;

    const items = list.querySelectorAll('.plan-item');
    const data = [];

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
            closeModal();
            const refreshBtn = document.querySelector('[hx-get*="/management/accounts"]');
            if (refreshBtn) {
                htmx.trigger(refreshBtn, 'click');
            } else {
                htmx.ajax('GET', `/management/accounts?lang=${lang}`, '#management-content');
            }
            showToast(messages.saveSuccessMessage);
        } else {
            alert(messages.saveErrorMessage);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert(messages.saveErrorMessage);
    });
}
