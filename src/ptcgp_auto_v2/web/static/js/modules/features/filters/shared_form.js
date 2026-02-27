import { reinitCustomSelect } from '../../custom_select.js';

const FILTER_CACHE_KEY_FALLBACK = {
    'metadata-state-form': 'ptcgp_filter:metadata',
};

function getCacheKey(form) {
    if (!(form instanceof HTMLFormElement)) return '';
    const explicitKey = String(form.dataset.filterCacheKey || '').trim();
    if (explicitKey) return explicitKey;
    return FILTER_CACHE_KEY_FALLBACK[form.id] || '';
}

function parseStored(raw) {
    if (!raw) return null;
    try {
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch {
        return null;
    }
}

function appendParam(params, key, rawValue) {
    if (!key) return;
    if (Array.isArray(rawValue)) {
        rawValue.forEach((item) => appendParam(params, key, item));
        return;
    }
    if (rawValue === '' || rawValue === null || rawValue === undefined) return;
    const text = String(rawValue).trim();
    if (!text) return;
    params.append(key, text);
}

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

export function applyFormFilters(form, filters, extraSelectors = []) {
    if (!filters) return;

    Object.entries(filters).forEach(([name, rawValue]) => {
        const values = Array.isArray(rawValue) ? rawValue : [rawValue];
        const elements = Array.from(form.querySelectorAll(`[name="${name}"]`));
        if (form.id) {
            document.querySelectorAll(`[form="${form.id}"][name="${name}"]`).forEach((element) => {
                elements.push(element);
            });
        }
        extraSelectors.forEach((selector) => {
            const element = document.querySelector(selector);
            if (element && element.name === name) {
                elements.push(element);
            }
        });

        elements.forEach((element) => {
            if (element.type === 'checkbox' || element.type === 'radio') {
                element.checked = values.includes(element.value);
                return;
            }

            element.value = values[0] ?? '';
            if (element.classList.contains('custom-select-initialized')) {
                reinitCustomSelect(element);
            }
        });
    });
}

export function getStoredFiltersByKey(cacheKey) {
    if (!cacheKey) return null;
    return parseStored(localStorage.getItem(cacheKey));
}

export function getStoredFiltersByForm(form) {
    return getStoredFiltersByKey(getCacheKey(form));
}

export function saveFilterCache(form, extraSelectors = []) {
    if (!(form instanceof HTMLFormElement)) return null;
    const cacheKey = getCacheKey(form);
    if (!cacheKey) return null;
    const filters = serializeFormFilters(form, extraSelectors);
    localStorage.setItem(cacheKey, JSON.stringify(filters));
    return filters;
}

export function saveFilterCacheByElement(element, extraSelectors = []) {
    if (!(element instanceof Element)) return null;
    const form = element instanceof HTMLFormElement ? element : element.closest('form');
    if (!(form instanceof HTMLFormElement)) return null;
    return saveFilterCache(form, extraSelectors);
}

export function saveFilterCachesInContext(context = document) {
    if (!(context instanceof Element) && context !== document) return;

    if (context instanceof HTMLFormElement && getCacheKey(context)) {
        saveFilterCache(context);
    }

    const root = context === document ? document : context;
    root.querySelectorAll('form[data-filter-cache-key]').forEach((form) => {
        if (form instanceof HTMLFormElement) {
            saveFilterCache(form);
        }
    });
}

export function restoreFilterCache(form, extraSelectors = []) {
    if (!(form instanceof HTMLFormElement)) return null;
    const filters = getStoredFiltersByForm(form);
    if (!filters) return null;
    applyFormFilters(form, filters, extraSelectors);
    return filters;
}

export function restoreFilterCachesInContext(context = document) {
    if (!(context instanceof Element) && context !== document) return;

    if (context instanceof HTMLFormElement && getCacheKey(context)) {
        restoreFilterCache(context);
    }

    const root = context === document ? document : context;
    root.querySelectorAll('form[data-filter-cache-key]').forEach((form) => {
        if (form instanceof HTMLFormElement) {
            restoreFilterCache(form);
        }
    });
}

export function restoreAllFilterCaches() {
    restoreFilterCachesInContext(document);
}

export function clearFilterCache(form) {
    if (!(form instanceof HTMLFormElement)) return;
    const cacheKey = getCacheKey(form);
    if (!cacheKey) return;
    localStorage.removeItem(cacheKey);
}

export function clearFilterCacheByFormId(formId) {
    const form = document.getElementById(formId);
    if (!(form instanceof HTMLFormElement)) return;
    clearFilterCache(form);
}

export function buildUrlWithFilters(baseUrl, filters, paramKeys = null) {
    if (!baseUrl) return '';
    const url = new URL(baseUrl, window.location.origin);
    const keys = Array.isArray(paramKeys) && paramKeys.length > 0
        ? paramKeys.filter(Boolean)
        : Object.keys(filters || {});

    keys.forEach((key) => {
        url.searchParams.delete(key);
    });

    keys.forEach((key) => {
        appendParam(url.searchParams, key, filters ? filters[key] : null);
    });

    return `${url.pathname}${url.search}`;
}

export function syncSidebarRequestParams(button) {
    if (!(button instanceof Element)) return;

    const cacheKey = String(button.dataset.filterCacheKey || '').trim();
    if (!cacheKey) return;

    const existing = button.dataset.baseUrl || button.getAttribute('hx-get') || '';
    if (!button.dataset.baseUrl && existing) {
        button.dataset.baseUrl = existing;
    }
    const baseUrl = button.dataset.baseUrl || existing;
    if (!baseUrl) return;

    const filters = getStoredFiltersByKey(cacheKey);
    const rawParamKeys = String(button.dataset.filterParamKeys || '').trim();
    const paramKeys = rawParamKeys
        ? rawParamKeys.split(',').map((item) => item.trim()).filter(Boolean)
        : null;
    const url = buildUrlWithFilters(baseUrl, filters, paramKeys);
    button.setAttribute('hx-get', url);

    if (window.htmx && typeof window.htmx.process === 'function') {
        window.htmx.process(button);
    }
}
