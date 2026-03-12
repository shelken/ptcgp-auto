import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

async function loadSharedFormModule() {
    const moduleUrl = new URL('../../static/js/modules/features/filters/shared_form.js', import.meta.url);
    const source = await readFile(moduleUrl, 'utf8');
    const patchedSource = source.replace(
        "import { reinitCustomSelect } from '../../custom_select.js';",
        'const reinitCustomSelect = () => {};'
    );
    return import(`data:text/javascript;charset=utf-8,${encodeURIComponent(patchedSource)}`);
}

class FakeElement {}

class FakeForm extends FakeElement {
    constructor(entries = []) {
        super();
        this.id = '';
        this.dataset = {};
        this.__entries = entries;
    }

    querySelectorAll() {
        return [];
    }
}

class FakeInput extends FakeElement {
    constructor({ name = '', value = '', type = 'text', checked = false, form = null } = {}) {
        super();
        this.name = name;
        this.value = value;
        this.type = type;
        this.checked = checked;
        this.disabled = false;
        this.form = form;
    }
}

class FakeSelect extends FakeElement {
    constructor({ name = '', value = '', multiple = false, selectedOptions = [], form = null } = {}) {
        super();
        this.name = name;
        this.value = value;
        this.multiple = multiple;
        this.selectedOptions = selectedOptions;
        this.disabled = false;
        this.form = form;
    }
}

class FakeTextarea extends FakeElement {
    constructor({ name = '', value = '', form = null } = {}) {
        super();
        this.name = name;
        this.value = value;
        this.disabled = false;
        this.form = form;
    }
}

class FakeDocument {
    constructor(elements = {}) {
        this.elements = elements;
    }

    querySelector(selector) {
        return this.elements[selector] || null;
    }

    querySelectorAll() {
        return [];
    }
}

test('buildUrlWithSelectorFilters 统一表单与关联控件状态', async () => {
    globalThis.Element = FakeElement;
    globalThis.HTMLFormElement = FakeForm;
    globalThis.HTMLInputElement = FakeInput;
    globalThis.HTMLSelectElement = FakeSelect;
    globalThis.HTMLTextAreaElement = FakeTextarea;
    globalThis.Document = FakeDocument;
    globalThis.window = {
        location: {
            origin: 'http://192.168.6.10:8000'
        }
    };
    globalThis.FormData = class {
        constructor(form) {
            this.entriesList = form.__entries || [];
        }

        *entries() {
            yield* this.entriesList;
        }
    };

    const form = new FakeForm([
        ['account_id', '111'],
        ['rarity', 'SR'],
        ['rarity', 'SAR'],
        ['ownership_scope', 'owned'],
        ['sort_by', 'acquired']
    ]);
    form.id = 'owned-filter-form';
    const sortSelect = new FakeSelect({
        name: 'sort_by',
        value: 'acquired',
        form
    });
    globalThis.document = new FakeDocument({
        '#owned-filter-form': form,
        '#owned-sort-select': sortSelect
    });

    const { buildUrlWithSelectorFilters } = await loadSharedFormModule();
    const url = buildUrlWithSelectorFilters(
        '/api/owned-cards',
        '#owned-filter-form,#owned-sort-select',
        { page: '0', lang: 'zh_CN' }
    );

    assert.equal(
        url,
        '/api/owned-cards?account_id=111&rarity=SR&rarity=SAR&ownership_scope=owned&sort_by=acquired&page=0&lang=zh_CN'
    );
});

test('buildUrlWithFilters 保留空字符串参数', async () => {
    globalThis.window = {
        location: {
            origin: 'http://192.168.6.10:8000'
        }
    };

    const { buildUrlWithFilters } = await loadSharedFormModule();
    const url = buildUrlWithFilters('/management/resources?lang=zh_CN', {
        view: 'stats',
        q: '',
        sort_by: 'id',
        sort_order: 'asc',
        page: '0',
        page_size: '10'
    });

    assert.equal(
        url,
        '/management/resources?lang=zh_CN&view=stats&q=&sort_by=id&sort_order=asc&page=0&page_size=10'
    );
});
