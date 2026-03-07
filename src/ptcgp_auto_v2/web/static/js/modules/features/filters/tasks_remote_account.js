function hideTaskAccountOptions(container) {
    if (!(container instanceof HTMLElement)) return;
    container.classList.add('hidden');
    container.innerHTML = '';
}

function showTaskAccountOptions(container, html) {
    if (!(container instanceof HTMLElement)) return;
    container.innerHTML = html;
    container.classList.toggle('hidden', !String(html || '').trim());
}

function getActiveIndex(container) {
    if (!(container instanceof HTMLElement)) return -1;
    const buttons = container.querySelectorAll('button[data-account-id]');
    for (let i = 0; i < buttons.length; i++) {
        if (buttons[i].classList.contains('ring-2') || buttons[i].classList.contains('bg-subtle')) {
            return i;
        }
    }
    return -1;
}

function setActiveIndex(container, index) {
    if (!(container instanceof HTMLElement)) return;
    const buttons = container.querySelectorAll('button[data-account-id]');
    if (!buttons.length) return;
    if (index < 0) index = buttons.length - 1;
    if (index >= buttons.length) index = 0;
    buttons.forEach((btn, i) => {
        btn.classList.toggle('ring-2', i === index);
        btn.classList.toggle('ring-theme', i === index);
        btn.classList.toggle('bg-subtle', i === index);
    });
    buttons[index]?.scrollIntoView({ block: 'nearest' });
}

function handleKeyboardNavigation(input, container, event) {
    if (!(input instanceof HTMLInputElement) || !(container instanceof HTMLElement)) return;

    const buttons = container.querySelectorAll('button[data-account-id]');
    const isOpen = !container.classList.contains('hidden');
    const hasOptions = buttons.length > 0;

    switch (event.key) {
        case 'ArrowDown':
        case 'ArrowUp':
            if (isOpen && hasOptions) {
                event.preventDefault();
                let currentIndex = getActiveIndex(container);
                setActiveIndex(container, event.key === 'ArrowDown' ? currentIndex + 1 : currentIndex - 1);
            }
            break;
        case 'Enter':
            event.preventDefault();
            if (isOpen && hasOptions) {
                let currentIndex = getActiveIndex(container);
                if (currentIndex >= 0 && buttons[currentIndex]) {
                    selectTaskAccountOption(buttons[currentIndex]);
                } else {
                    selectTaskAccountOption(buttons[0]);
                }
            }
            break;
        case 'Escape':
            if (isOpen) {
                event.preventDefault();
                hideTaskAccountOptions(container);
            }
            break;
    }
}

export async function searchTaskAccounts(input) {
    if (!(input instanceof HTMLInputElement)) return;
    const targetSelector = input.dataset.optionsTarget || '';
    const hiddenSelector = input.dataset.hiddenInput || '';
    const baseUrl = input.dataset.optionsUrl || '';
    const container = document.querySelector(targetSelector);
    const hiddenInput = document.querySelector(hiddenSelector);
    if (!(container instanceof HTMLElement) || !(hiddenInput instanceof HTMLInputElement) || !baseUrl) {
        return;
    }

    const query = input.value.trim();
    if (!query) {
        hiddenInput.value = '';
        hideTaskAccountOptions(container);
        hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
        return;
    }

    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set('q', query);
    const response = await fetch(url.toString(), {
        headers: { 'HX-Request': 'true' },
    });
    if (!response.ok) {
        hideTaskAccountOptions(container);
        return;
    }
    const html = await response.text();
    showTaskAccountOptions(container, html);
}

export function selectTaskAccountOption(button) {
    if (!(button instanceof HTMLElement)) return;
    const accountId = button.dataset.accountId || '';
    const accountLabel = button.dataset.accountLabel || '';
    const container = button.closest('#task-filter-account-options');
    const wrapper = button.closest('.relative');
    const input = wrapper ? wrapper.querySelector('#task-filter-account-query') : null;
    const hiddenInput = document.querySelector('#task-account-id');
    if (input instanceof HTMLInputElement) {
        input.value = accountLabel;
    }
    if (hiddenInput instanceof HTMLInputElement) {
        hiddenInput.value = accountId;
        hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
    hideTaskAccountOptions(container);
}

export function initTaskRemoteAccountSearch(context = document) {
    const root = context instanceof Element ? context : document;
    const input = root.querySelector('#task-filter-account-query') || document.querySelector('#task-filter-account-query');
    const container = root.querySelector('#task-filter-account-options') || document.querySelector('#task-filter-account-options');
    if (!(input instanceof HTMLInputElement) || !(container instanceof HTMLElement)) return;
    if (input.dataset.remoteAccountBound === 'true') return;

    let timer = null;
    input.addEventListener('input', () => {
        if (timer) window.clearTimeout(timer);
        timer = window.setTimeout(() => {
            searchTaskAccounts(input);
        }, 200);
    });

    input.addEventListener('blur', () => {
        window.setTimeout(() => hideTaskAccountOptions(container), 150);
    });

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();
        }
        handleKeyboardNavigation(input, container, event);
    });

    input.dataset.remoteAccountBound = 'true';
}
