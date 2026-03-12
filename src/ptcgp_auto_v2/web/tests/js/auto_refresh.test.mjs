import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

async function loadAutoRefreshModule() {
    const moduleUrl = new URL('../../static/js/modules/auto_refresh.js', import.meta.url);
    const source = await readFile(moduleUrl, 'utf8');
    const patchedSource = source.replace(
        "import { isElementInActiveTab } from './utils.js';",
        'const isElementInActiveTab = () => true;'
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

    assert.equal(url, '/api/records?page=0&lang=zh_CN&rarity=SR&rarity=SAR&rarity=UR');
});
