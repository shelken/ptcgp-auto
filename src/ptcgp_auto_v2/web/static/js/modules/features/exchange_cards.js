// --- 交换卡牌账号搜索 ---
function searchExchangeAccounts(query) {
    const tbody = document.getElementById('exchange-accounts-tbody');
    if (!tbody) return;
    const rows = tbody.querySelectorAll('.exchange-account-row');
    const normalizedQuery = (query || '').toLowerCase().trim();

    rows.forEach((row) => {
        const accountId = (row.dataset.accountId || '').toLowerCase();
        const friendId = (row.dataset.friendId || '').toLowerCase();
        const nickname = (row.dataset.nickname || '').toLowerCase();
        const visible = !normalizedQuery
            || accountId.includes(normalizedQuery)
            || friendId.includes(normalizedQuery)
            || nickname.includes(normalizedQuery);
        row.style.display = visible ? '' : 'none';
    });
}

// --- 初始化交换卡牌搜索 ---
export function initExchangeCards(context = document) {
    const root = context instanceof Element ? context : document;
    const searchInput = root.querySelector('[data-action="search-exchange-accounts"]');
    if (!(searchInput instanceof HTMLInputElement)) return;
    if (searchInput.dataset.exchangeSearchBound === 'true') return;

    searchInput.addEventListener('input', () => {
        searchExchangeAccounts(searchInput.value);
    });

    searchInput.dataset.exchangeSearchBound = 'true';
}

// --- 展示交换表单 ---
export function showExchangeForm(button) {
    const container = document.getElementById('exchange-form-container');
    const fromAccountIdInput = document.getElementById('exchange-from-account-id');
    const fromAccountDisplay = document.getElementById('exchange-from-account-display');
    const toFriendIdInput = document.getElementById('exchange-to-friend-id');
    const submitBtn = document.getElementById('exchange-submit-btn');
    const warningEl = document.getElementById('exchange-active-warning');

    if (!container || !fromAccountIdInput || !fromAccountDisplay || !toFriendIdInput) return;

    const accountId = button.dataset.accountId || '';
    const nickname = button.dataset.nickname || '';
    const hasActive = button.dataset.hasActive === 'true';

    fromAccountIdInput.value = accountId;
    fromAccountDisplay.textContent = nickname ? `#${accountId} · ${nickname}` : `#${accountId}`;
    toFriendIdInput.value = '';

    if (hasActive) {
        if (warningEl) warningEl.classList.remove('hidden');
        if (submitBtn) submitBtn.disabled = true;
    } else {
        if (warningEl) warningEl.classList.add('hidden');
        if (submitBtn) submitBtn.disabled = false;
    }

    container.classList.remove('hidden');
    toFriendIdInput.focus();
}

// --- 取消交换表单 ---
export function cancelExchangeForm() {
    const container = document.getElementById('exchange-form-container');
    const fromAccountIdInput = document.getElementById('exchange-from-account-id');
    const fromAccountDisplay = document.getElementById('exchange-from-account-display');
    const toFriendIdInput = document.getElementById('exchange-to-friend-id');
    const submitBtn = document.getElementById('exchange-submit-btn');
    const warningEl = document.getElementById('exchange-active-warning');

    if (fromAccountIdInput) fromAccountIdInput.value = '';
    if (fromAccountDisplay) fromAccountDisplay.textContent = '-';
    if (toFriendIdInput) toFriendIdInput.value = '';
    if (submitBtn) submitBtn.disabled = true;
    if (warningEl) warningEl.classList.add('hidden');
    if (container) container.classList.add('hidden');
}
