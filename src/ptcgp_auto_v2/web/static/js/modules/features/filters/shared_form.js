import { initCustomSelects, reinitCustomSelect } from '../../custom_select.js';

// --- 筛选序列化 ---
export function serializeFormFilters(form, extraSelectors = []) {
    const formData = new FormData(form);
    const filters = {};

    for (const [key, value] of formData.entries()) {
        if (filters[key]) {
            if (Array.isArray(filters[key])) {
                filters[key].push(value);
            } else {
                filters[key] = [filters[key], value];
            }
        } else {
            filters[key] = value;
        }
    }

    extraSelectors.forEach((selector) => {
        const element = document.querySelector(selector);
        if (!element || !element.name) return;
        filters[element.name] = element.value || '';
    });

    return filters;
}

// --- 筛选回填 ---
export function applyFormFilters(form, filters, extraSelectors = []) {
    if (!filters) return;

    Object.entries(filters).forEach(([name, rawValue]) => {
        const values = Array.isArray(rawValue) ? rawValue : [rawValue];
        const elements = Array.from(form.querySelectorAll(`[name="${name}"]`));
        extraSelectors.forEach((selector) => {
            const element = document.querySelector(selector);
            if (element && element.name === name) {
                elements.push(element);
            }
        });

        elements.forEach((element) => {
            if (element.type === 'checkbox' || element.type === 'radio') {
                element.checked = values.includes(element.value);
            } else {
                element.value = values[0] ?? '';
                if (element.classList.contains('custom-select-initialized')) {
                    reinitCustomSelect(element);
                }
            }
        });
    });
}

// --- 构建查询参数 ---
export function buildQueryParts(filters) {
    const parts = [];
    if (!filters) return parts;
    Object.entries(filters).forEach(([name, rawValue]) => {
        const values = Array.isArray(rawValue) ? rawValue : [rawValue];
        values.forEach((value) => {
            if (value === '' || value === null || value === undefined) return;
            parts.push(`${encodeURIComponent(name)}=${encodeURIComponent(value)}`);
        });
    });
    return parts;
}

// --- 保存筛选 ---
export function saveFormFilters(formId, storageKey, extraSelectors = []) {
    const form = document.getElementById(formId);
    if (!form) return;
    const filters = serializeFormFilters(form, extraSelectors);
    localStorage.setItem(storageKey, JSON.stringify(filters));
}

export function initAndApplyFormFilters(form, filters, extraSelectors = []) {
    initCustomSelects(form);
    applyFormFilters(form, filters, extraSelectors);
}
