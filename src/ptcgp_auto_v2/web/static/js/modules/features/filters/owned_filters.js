import { showToast, setButtonLoading } from '../../utils.js';
import { reinitCustomSelect } from '../../custom_select.js';
import { clearFilterCacheByFormId } from './shared_form.js';

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

    htmx.ajax('GET', `/api/owned-cards?${params.toString()}`, { target: '#owned-cards-container', swap: 'innerHTML' });
}

// --- 更新筛选组摘要 ---
function updateOwnedFilterGroupSummary(group) {
    const summary = group.querySelector('[data-filter-summary]');
    if (!summary) return;

    const checkedInputs = Array.from(group.querySelectorAll('input[type="checkbox"]')).filter((input) => input.checked);

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
    form.dispatchEvent(new Event('change', { bubbles: true }));
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

// --- 监听全局筛选事件 ---
document.addEventListener('filter:saved', (event) => {
    const { formId } = event.detail;
    if (formId === 'owned-filter-form') {
        updateOwnedFilterGroupsState();
    }
});

document.addEventListener('filter:changed', (event) => {
    const { formId } = event.detail;
    if (formId === 'owned-filter-form') {
        updateOwnedFilterGroupsState();
    }
});

// --- 清除已拥有卡牌筛选 ---
export function clearOwnedFilters() {
    window.pauseOwnedCardsAutoRefreshUntil = Date.now() + 1500;

    const sortSelect = document.getElementById('owned-sort-select');
    const currentSortBy = (sortSelect && sortSelect.value) ? sortSelect.value : 'acquired';

    document.querySelectorAll('.owned-filter-checkbox').forEach((el) => {
        el.checked = false;
    });
    const accountInput = document.querySelector('#owned-filter-form input[name="account_id"]');
    if (accountInput) accountInput.value = '';
    if (sortSelect) {
        sortSelect.value = currentSortBy;
        if (sortSelect.classList.contains('custom-select-initialized')) {
            reinitCustomSelect(sortSelect);
        }
    }
    clearFilterCacheByFormId('owned-filter-form');

    document.querySelectorAll('[data-filter-group]').forEach((group) => {
        updateOwnedFilterGroupSummary(group);
        group.classList.remove('is-open');
    });

    const form = document.getElementById('owned-filter-form');
    if (form) {
        form.dispatchEvent(new Event('change', { bubbles: true }));
    }

    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    htmx.ajax('GET', `/api/owned-cards?page=0&lang=${lang}&sort_by=${encodeURIComponent(currentSortBy)}`, { target: '#owned-cards-container', swap: 'innerHTML' });
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
    htmx.ajax('GET', `/api/owned-cards?${params.toString()}`, { target: '#owned-cards-container', swap: 'innerHTML' });
    showToast('已刷新');
}
