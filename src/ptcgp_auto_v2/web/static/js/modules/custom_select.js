// --- 文本归一化 ---
function normalizeSearchText(value) {
    return String(value || '')
        .toLowerCase()
        .replace(/\s+/g, '');
}

// --- 筛选自定义下拉选项 ---
export function filterCustomSelectOptions(selectId, query) {
    const select = document.getElementById(selectId);
    if (!select) return;
    filterCustomSelectOptionsByElement(select, query);
}

// --- 按元素筛选自定义下拉选项 ---
function filterCustomSelectOptionsByElement(select, query) {
    if (!select) return;

    const normalized = normalizeSearchText(query);
    const options = Array.from(select.options);

    options.forEach((option) => {
        if (option.value === '') return;
        const searchText = option.getAttribute('data-search') || option.text || option.value;
        const match = !normalized || normalizeSearchText(searchText).includes(normalized);
        option.hidden = !match;
        option.disabled = !match;
    });

    const container = select.closest('.custom-select-container');
    if (!container) return;

    const optionEls = container.querySelectorAll('.custom-select-option');
    optionEls.forEach((optEl) => {
        if (optEl.dataset.value === '') {
            optEl.style.display = '';
            return;
        }
        const searchText = optEl.dataset.search || optEl.textContent || '';
        const match = !normalized || normalizeSearchText(searchText).includes(normalized);
        optEl.style.display = match ? '' : 'none';
    });
}

// --- 重新初始化单个自定义选择器 ---
export function reinitCustomSelect(selectElement) {
    if (!selectElement || !selectElement.classList.contains('js-custom-select')) return;

    const originalParent = selectElement.parentNode;
    const container = selectElement.closest('.custom-select-container');
    if (container) {
        const parent = container.parentNode;
        parent.insertBefore(selectElement, container);
        container.remove();
    }

    selectElement.classList.remove('custom-select-initialized');
    initCustomSelects(originalParent);
}

// --- 初始化自定义选择器 ---
export function initCustomSelects(context = document) {
    const selects = context.querySelectorAll('select.js-custom-select:not(.custom-select-initialized)');

    selects.forEach(select => {
        select.classList.add('custom-select-initialized');

        const container = document.createElement('div');
        container.className = 'custom-select-container';

        const originalClasses = Array.from(select.classList);
        const containerClasses = [];
        const triggerClasses = [];

        originalClasses.forEach(cls => {
            if (cls.startsWith('w-') || cls.startsWith('m-')) {
                containerClasses.push(cls);
            }
            if (cls.startsWith('text-') || cls.startsWith('font-') || cls.startsWith('p-') || cls.startsWith('px-') || cls.startsWith('py-') || cls.startsWith('h-')) {
                triggerClasses.push(cls);
            }
        });

        if (containerClasses.length > 0) {
            container.classList.add(...containerClasses);
        }

        select.parentNode.insertBefore(container, select);
        container.appendChild(select);

        const trigger = document.createElement('div');
        trigger.className = 'custom-select-trigger';
        if (triggerClasses.length > 0) {
            trigger.classList.add(...triggerClasses);
        }

        const selectedOption = select.options[select.selectedIndex];
        const initialText = selectedOption ? selectedOption.text : 'Select...';
        trigger.innerHTML = `<span>${initialText}</span><span class="custom-select-arrow">▼</span>`;
        container.appendChild(trigger);

        const optionsList = document.createElement('div');
        optionsList.className = 'custom-select-options';

        Array.from(select.options).forEach(option => {
            const optDiv = document.createElement('div');
            optDiv.className = 'custom-select-option';
            if (option.selected) optDiv.classList.add('selected');
            optDiv.textContent = option.text;
            optDiv.dataset.value = option.value;
            const searchValue = option.getAttribute('data-search') || option.text || option.value;
            optDiv.dataset.search = String(searchValue).toLowerCase();

            optDiv.addEventListener('click', (e) => {
                e.stopPropagation();

                select.value = option.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));

                trigger.querySelector('span').textContent = option.text;
                container.querySelectorAll('.custom-select-option').forEach(el => el.classList.remove('selected'));
                optDiv.classList.add('selected');

                container.classList.remove('open');
                container.classList.remove('open-up');
            });

            optionsList.appendChild(optDiv);
        });

        container.appendChild(optionsList);

        if (select.dataset.searchable === 'true') {
            const searchInput = document.createElement('input');
            const placeholder = select.dataset.searchPlaceholder || 'Search';
            searchInput.type = 'text';
            searchInput.className = 'custom-select-search brutal-input text-xs w-full';
            searchInput.placeholder = placeholder;
            searchInput.addEventListener('input', () => {
                filterCustomSelectOptionsByElement(select, searchInput.value);
            });
            searchInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                }
            });
            searchInput.addEventListener('click', (e) => e.stopPropagation());
            optionsList.insertAdjacentElement('afterbegin', searchInput);
        }

        const getVisibleOptions = () => {
            return Array.from(optionsList.querySelectorAll('.custom-select-option'))
                .filter((el) => el.style.display !== 'none');
        };

        const updateFocusedOption = (nextIndex) => {
            const visible = getVisibleOptions();
            if (visible.length === 0) return null;
            const bounded = Math.max(0, Math.min(nextIndex, visible.length - 1));
            optionsList.querySelectorAll('.custom-select-option').forEach((el) => {
                el.classList.remove('focused');
            });
            const focused = visible[bounded];
            focused.classList.add('focused');
            focused.scrollIntoView({ block: 'nearest' });
            return focused;
        };

        const handleKeyNavigation = (event) => {
            const visible = getVisibleOptions();
            if (!visible.length) return;
            const currentIndex = visible.findIndex((el) => el.classList.contains('focused'));

            if (event.key === 'ArrowDown') {
                event.preventDefault();
                updateFocusedOption(currentIndex < 0 ? 0 : currentIndex + 1);
            }

            if (event.key === 'ArrowUp') {
                event.preventDefault();
                updateFocusedOption(currentIndex < 0 ? 0 : currentIndex - 1);
            }

            if (event.key === 'Enter') {
                event.preventDefault();
                const focused = currentIndex >= 0 ? visible[currentIndex] : visible[0];
                if (focused) {
                    focused.click();
                }
            }

            if (event.key === 'Escape') {
                event.preventDefault();
                container.classList.remove('open');
                container.classList.remove('open-up');
            }
        };

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();

            document.querySelectorAll('.custom-select-container.open').forEach(el => {
                if (el !== container) {
                    el.classList.remove('open');
                    el.classList.remove('open-up');
                }
            });

            if (container.classList.contains('open')) {
                container.classList.remove('open');
                container.classList.remove('open-up');
            } else {
                const rect = container.getBoundingClientRect();
                const viewportHeight = window.innerHeight;
                const spaceBelow = viewportHeight - rect.bottom;
                const spaceAbove = rect.top;

                container.classList.remove('open-up');

                if (spaceBelow < 260 && spaceAbove > 260) {
                    container.classList.add('open-up');
                }

                container.classList.add('open');
                if (select.dataset.searchable === 'true') {
                    const searchInput = container.querySelector('.custom-select-search');
                    if (searchInput) {
                        searchInput.focus();
                        searchInput.select();
                    }
                } else {
                    updateFocusedOption(0);
                }
            }
        });

        trigger.addEventListener('keydown', handleKeyNavigation);
        optionsList.addEventListener('keydown', handleKeyNavigation);
        if (select.dataset.searchable === 'true') {
            const searchInput = optionsList.querySelector('.custom-select-search');
            if (searchInput) {
                searchInput.addEventListener('keydown', handleKeyNavigation);
            }
        }

        select.addEventListener('change', () => {
            const newOption = select.options[select.selectedIndex];
            if (newOption) {
                trigger.querySelector('span').textContent = newOption.text;
                container.querySelectorAll('.custom-select-option').forEach(el => {
                    if (el.dataset.value === newOption.value) {
                        el.classList.add('selected');
                    } else {
                        el.classList.remove('selected');
                    }
                });
            }
        });
    });

    if (!window.hasCustomSelectGlobalListener) {
        document.addEventListener('click', () => {
            document.querySelectorAll('.custom-select-container.open').forEach(el => {
                el.classList.remove('open');
                el.classList.remove('open-up');
            });
        });
        window.hasCustomSelectGlobalListener = true;
    }
}
