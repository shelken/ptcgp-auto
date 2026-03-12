import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

async function loadAutoRefreshModule() {
    const moduleUrl = new URL('../../static/js/modules/auto_refresh.js', import.meta.url);
    const source = await readFile(moduleUrl, 'utf8');
    const patchedSource = source
        .replace(
            "import { isElementInActiveTab } from './utils.js';",
            'const isElementInActiveTab = () => true;'
        )
        .replace(
            "import { buildUrlWithSelectorFilters } from './features/filters/shared_form.js';",
            `const buildUrlWithSelectorFilters = (baseUrl, selectors, overrides = {}) => {
                const url = new URL(baseUrl, window.location.origin);
                const selectorList = String(selectors || '').split(',').map((item) => item.trim()).filter(Boolean);
                const filters = {};
                selectorList.forEach((selector) => {
                    const element = document.querySelector(selector);
                    if (!element) return;
                    if (element.tagName === 'FORM') {
                        const formData = new FormData(element);
                        formData.forEach((value, key) => {
                            if (!filters[key]) {
                                filters[key] = [];
                            }
                            filters[key].push(String(value));
                        });
                        return;
                    }
                    if (!element.name) return;
                    filters[element.name] = [String(element.value || '')];
                });
                Object.entries(overrides).forEach(([key, value]) => {
                    filters[key] = [String(value)];
                });
                Object.keys(filters).forEach((key) => {
                    url.searchParams.delete(key);
                    filters[key].forEach((value) => {
                        url.searchParams.append(key, value);
                    });
                });
                return \`\${url.pathname}\${url.search}\`;
            };`
        );
    return import(`data:text/javascript;charset=utf-8,${encodeURIComponent(patchedSource)}`);
}

test('buildAutoRefreshUrl 保留多选筛选参数', async () => {
    globalThis.window = {
        location: {
            origin: 'http://192.168.6.10:8000',
            search: '?lang=zh_CN'
        }
    };

    globalThis.document = {
        querySelector(selector) {
            if (selector === '#filter-form') {
                return {
                    tagName: 'FORM',
                    __entries: [
                        ['rarity', 'SR'],
                        ['rarity', 'SAR'],
                        ['rarity', 'UR']
                    ]
                };
            }
            return null;
        }
    };

    globalThis.FormData = class {
        constructor(form) {
            this.entries = form.__entries || [];
        }

        forEach(callback) {
            this.entries.forEach(([key, value]) => {
                callback(value, key);
            });
        }
    };

    const { buildAutoRefreshUrl } = await loadAutoRefreshModule();
    const url = buildAutoRefreshUrl({
        dataset: {
            autoRefresh: '/api/records',
            refreshInclude: '#filter-form'
        }
    });

    const parsedUrl = new URL(url, 'http://192.168.6.10:8000');
    assert.equal(parsedUrl.pathname, '/api/records');
    assert.equal(parsedUrl.searchParams.get('page'), '0');
    assert.equal(parsedUrl.searchParams.get('lang'), 'zh_CN');
    assert.deepEqual(parsedUrl.searchParams.getAll('rarity'), ['SR', 'SAR', 'UR']);
});
