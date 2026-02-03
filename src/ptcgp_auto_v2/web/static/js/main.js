// --- ES6 Modules Import ---
import { getModal } from './modules/modal.js';
import { showToast, throttle, debounce, isElementInActiveTab } from './modules/utils.js';

// --- Constants ---
const STORAGE_KEY_LANG = 'ptcgp_lang';
const STORAGE_KEY_FILTERS = 'ptcgp_filters';
const STORAGE_KEY_OWNED_FILTERS = 'ptcgp_owned_filters';
const STORAGE_KEY_VIEW_MODE = 'ptcgp_view_mode';
const STORAGE_KEY_OWNED_COLS = 'ptcgp_owned_cols';
const STORAGE_KEY_THEME = 'ptcgp_theme';
const STORAGE_KEY_TAB = 'ptcgp_active_tab';

// --- Card Preview State ---
let cardPreviewState = {
    isOpen: false,
    isDragging: false,
    startX: 0,
    startY: 0,
    currentX: 0,
    currentY: 0,
    rotateX: 0,
    rotateY: 0,
    targetElement: null
};

// --- Tab State ---
let currentTabName = null;

// --- Card Preview Functions ---

function openCardPreview(cardElement) {
    // 防止重复打开
    if (cardPreviewState.isOpen) return;

    // 获取卡牌数据
    const cardName = cardElement.dataset.cardName || 'Unknown';
    const cardRarity = cardElement.dataset.cardRarity || '';
    const cardSet = cardElement.dataset.cardSet || '';
    const cardNumber = cardElement.dataset.cardNumber || '';
    // 大图使用高清原图 (jsDelivr CDN), 缩略图使用 wsrv.nl 裁剪版
    const cardImage = cardElement.dataset.cardImageHd || cardElement.dataset.cardImage || '/static/card_back.png';

    // 创建预览模态框 HTML
    const previewHTML = `
        <div id="card-preview-overlay" class="card-preview-overlay" onclick="closeCardPreview(event)">
            <div id="card-preview-container" class="card-preview-container">
                <div id="card-preview-card" class="card-preview-card">
                    <div class="card-preview-front">
                        <img src="${cardImage}" alt="${cardName}" class="card-preview-image" draggable="false" onerror="this.src='/static/card_back.png'">
                        <div id="card-preview-shine" class="card-preview-shine"></div>
                    </div>
                </div>
                <div class="card-preview-info">
                    <div class="card-preview-name">${cardName}</div>
                    <div class="card-preview-meta">
                        ${cardRarity ? `<span class="card-preview-rarity">${cardRarity}</span>` : ''}
                        ${cardSet ? `<span class="card-preview-set">${cardSet}</span>` : ''}
                        ${cardNumber ? `<span class="card-preview-number">#${cardNumber}</span>` : ''}
                    </div>
                </div>
                <div class="card-preview-hint">拖动旋转查看 / Drag to rotate</div>
            </div>
        </div>
    `;

    // 插入到 body
    document.body.insertAdjacentHTML('beforeend', previewHTML);

    // 更新状态
    cardPreviewState.isOpen = true;
    cardPreviewState.rotateX = 0;
    cardPreviewState.rotateY = 0;
    cardPreviewState.targetElement = document.getElementById('card-preview-card');

    // 绑定拖拽事件
    bindCardPreviewEvents();

    // 禁止背景滚动
    document.body.style.overflow = 'hidden';

    // 添加显示动画
    requestAnimationFrame(() => {
        const overlay = document.getElementById('card-preview-overlay');
        if (overlay) overlay.classList.add('active');
    });
}

function closeCardPreview(event) {
    // 如果点击的是容器内部（卡牌本身），不关闭
    if (event && event.target.id !== 'card-preview-overlay') return;

    const overlay = document.getElementById('card-preview-overlay');
    if (!overlay) return;

    // 移除显示动画
    overlay.classList.remove('active');

    // 延迟后移除 DOM
    setTimeout(() => {
        overlay.remove();
        cardPreviewState.isOpen = false;
        cardPreviewState.targetElement = null;
        document.body.style.overflow = '';
    }, 300);
}

function bindCardPreviewEvents() {
    const container = document.getElementById('card-preview-container');
    if (!container) return;

    // 鼠标事件
    container.addEventListener('mousedown', handleDragStart);
    document.addEventListener('mousemove', handleDragMove);
    document.addEventListener('mouseup', handleDragEnd);

    // 触摸事件
    container.addEventListener('touchstart', handleDragStart, { passive: false });
    document.addEventListener('touchmove', handleDragMove, { passive: false });
    document.addEventListener('touchend', handleDragEnd);
}

function handleDragStart(e) {
    if (!cardPreviewState.isOpen) return;
    
    // 阻止默认拖拽行为（防止图片被拖动）
    e.preventDefault();

    cardPreviewState.isDragging = true;

    // 获取起始位置
    if (e.type === 'touchstart') {
        cardPreviewState.startX = e.touches[0].clientX;
        cardPreviewState.startY = e.touches[0].clientY;
    } else {
        cardPreviewState.startX = e.clientX;
        cardPreviewState.startY = e.clientY;
    }

    // 添加拖拽中样式
    const card = document.getElementById('card-preview-card');
    if (card) card.classList.add('dragging');
}

function handleDragMove(e) {
    if (!cardPreviewState.isDragging || !cardPreviewState.isOpen) return;

    e.preventDefault();

    // 获取当前位置
    let clientX, clientY;
    if (e.type === 'touchmove') {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
    } else {
        clientX = e.clientX;
        clientY = e.clientY;
    }

    // 计算移动差值
    const deltaX = clientX - cardPreviewState.startX;
    const deltaY = clientY - cardPreviewState.startY;
    
    // 更新旋转角度（灵敏度：每像素 0.5 度）
    cardPreviewState.rotateY += deltaX * 0.5;
    cardPreviewState.rotateX -= deltaY * 0.5;
    
    // 限制旋转范围 (-45 到 45 度)
    cardPreviewState.rotateX = Math.max(-45, Math.min(45, cardPreviewState.rotateX));
    cardPreviewState.rotateY = Math.max(-45, Math.min(45, cardPreviewState.rotateY));

    // 应用旋转
    updateCardRotation();

    // 更新起始位置
    cardPreviewState.startX = clientX;
    cardPreviewState.startY = clientY;
}

function handleDragEnd() {
    if (!cardPreviewState.isDragging) return;

    cardPreviewState.isDragging = false;

    // 移除拖拽中样式
    const card = document.getElementById('card-preview-card');
    if (card) card.classList.remove('dragging');
    
    // 自动回正 - 平滑转回正面
    animateResetToFront();
}

function updateCardRotation() {
    const card = cardPreviewState.targetElement;
    if (!card) return;

    // 应用 3D 旋转 - 使用更自然的旋转顺序
    card.style.transform = `rotateY(${cardPreviewState.rotateY}deg) rotateX(${cardPreviewState.rotateX}deg)`;
    
    // 更新光影效果 - 根据旋转角度调整光泽位置
    updateShineEffect();
}

function updateShineEffect() {
    const shine = document.getElementById('card-preview-shine');
    if (!shine) return;
    
    // 计算光泽偏移 - 旋转越大，光泽移动越多
    const shineX = -cardPreviewState.rotateY * 2; // 水平旋转影响光泽左右移动
    const shineY = cardPreviewState.rotateX * 2;  // 垂直旋转影响光泽上下移动
    
    // 动态调整光泽角度和透明度
    const angle = 115 + (cardPreviewState.rotateY * 0.3);
    const opacity = 0.4 + (Math.abs(cardPreviewState.rotateY) / 90) * 0.3;
    
    shine.style.background = `linear-gradient(
        ${angle}deg,
        rgba(255, 255, 255, 0) 0%,
        rgba(255, 255, 255, 0) 35%,
        rgba(255, 255, 255, ${opacity}) 50%,
        rgba(255, 255, 255, 0) 65%,
        rgba(255, 255, 255, 0) 100%
    )`;
    shine.style.transform = `translateZ(2px) translateX(${shineX}px) translateY(${shineY}px)`;
}

function animateResetToFront() {
    if (!cardPreviewState.isOpen) return;
    
    const card = document.getElementById('card-preview-card');
    if (!card) return;
    
    // 保存起始角度
    const startX = cardPreviewState.rotateX;
    const startY = cardPreviewState.rotateY;
    
    // 如果已经在正面，无需动画
    if (Math.abs(startX) < 0.1 && Math.abs(startY) < 0.1) return;
    
    // 添加过渡动画
    card.style.transition = 'transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)';
    
    // 重置角度
    cardPreviewState.rotateX = 0;
    cardPreviewState.rotateY = 0;
    
    // 应用最终状态
    updateCardRotation();
    
    // 动画完成后恢复快速响应的过渡
    setTimeout(() => {
        if (card) card.style.transition = 'transform 0.15s ease-out';
    }, 600);
}

// --- Persistence Functions ---

// 1. Language Persistence
function setLang(lang) {
    localStorage.setItem(STORAGE_KEY_LANG, lang);
    const url = new URL(window.location);
    url.searchParams.set('lang', lang);
    window.location.href = url.toString();
}

function initLang() {
    const urlParams = new URLSearchParams(window.location.search);
    const currentLang = urlParams.get('lang');
    const storedLang = localStorage.getItem(STORAGE_KEY_LANG);

    if (!currentLang && storedLang) {
        const url = new URL(window.location);
        url.searchParams.set('lang', storedLang);
        window.location.replace(url.toString());
    } else if (currentLang && currentLang !== storedLang) {
        localStorage.setItem(STORAGE_KEY_LANG, currentLang);
    }
}

// 2. Filter Persistence
function saveFilters() {
    const form = document.getElementById('filter-form');
    if (!form) return;
    
    const formData = new FormData(form);
    const filters = {
        rarity: formData.getAll('rarity'),
        card_type: formData.getAll('card_type')
    };
    localStorage.setItem(STORAGE_KEY_FILTERS, JSON.stringify(filters));
}

function saveOwnedFilters() {
    const form = document.getElementById('owned-filter-form');
    if (!form) return;

    const formData = new FormData(form);
    const sortSelect = document.getElementById('owned-sort-select');
    const sortValue = sortSelect ? sortSelect.value : 'rarity';
    const filters = {
        rarity: formData.getAll('rarity'),
        card_type: formData.getAll('card_type'),
        set_code: formData.getAll('set_code'),
        pack_name: formData.getAll('pack_name'),
        element: formData.getAll('element'),
        sort_by: sortValue
    };
    localStorage.setItem(STORAGE_KEY_OWNED_FILTERS, JSON.stringify(filters));
    updateOwnedFilterGroupsState();
}

function restoreFilters() {
    const stored = localStorage.getItem(STORAGE_KEY_FILTERS);
    let queryParts = [];

    if (stored) {
        try {
            const filters = JSON.parse(stored);
            if (filters.rarity) {
                filters.rarity.forEach(val => {
                    const el = document.querySelector(`input[name="rarity"][value="${val}"]`);
                    if (el) el.checked = true;
                    queryParts.push(`rarity=${val}`);
                });
            }
            if (filters.card_type) {
                filters.card_type.forEach(val => {
                    const el = document.querySelector(`input[name="card_type"][value="${val}"]`);
                    if (el) el.checked = true;
                    queryParts.push(`card_type=${val}`);
                });
            }
        } catch (e) {
            console.error("Failed to restore filters", e);
        }
    }

    // Always trigger initial load via JS
    const container = document.getElementById('records-container');
    if (container) {
        if (!isElementInActiveTab(container)) {
            return;
        }
        if (container.dataset.loaded === 'true') {
            return;
        }
        const baseAttr = container.getAttribute('data-base-url') || container.getAttribute('data-url');
        let finalUrl = baseAttr;

        if (queryParts.length > 0) {
            finalUrl = baseAttr + '&' + queryParts.join('&');
        }

        htmx.ajax('GET', finalUrl, {target: '#records-container', swap: 'innerHTML'});
        container.dataset.loaded = 'true';
    }
}

function restoreOwnedFilters() {
    const stored = localStorage.getItem(STORAGE_KEY_OWNED_FILTERS);
    let queryParts = [];
    const form = document.getElementById('owned-filter-form');
    if (!form) return;

    if (stored) {
        try {
            const filters = JSON.parse(stored);
            if (filters.sort_by) {
                const select = document.getElementById('owned-sort-select');
                if (select) {
                    select.value = filters.sort_by;
                    if (select.classList.contains('custom-select-initialized')) {
                        reinitCustomSelect(select);
                    }
                }
                queryParts.push(`sort_by=${filters.sort_by}`);
            }
            if (filters.rarity) {
                filters.rarity.forEach(val => {
                    const el = form.querySelector(`input[name="rarity"][value="${val}"]`);
                    if (el && el.classList.contains('owned-filter-checkbox')) el.checked = true;
                    queryParts.push(`rarity=${val}`);
                });
            }
            if (filters.card_type) {
                filters.card_type.forEach(val => {
                    const el = form.querySelector(`input[name="card_type"][value="${val}"]`);
                    if (el && el.classList.contains('owned-filter-checkbox')) el.checked = true;
                    queryParts.push(`card_type=${val}`);
                });
            }
            if (filters.set_code) {
                filters.set_code.forEach(val => {
                    const el = form.querySelector(`input[name="set_code"][value="${val}"]`);
                    if (el && el.classList.contains('owned-filter-checkbox')) el.checked = true;
                    queryParts.push(`set_code=${val}`);
                });
            }
            if (filters.pack_name) {
                filters.pack_name.forEach(val => {
                    const el = form.querySelector(`input[name="pack_name"][value="${val}"]`);
                    if (el && el.classList.contains('owned-filter-checkbox')) el.checked = true;
                    queryParts.push(`pack_name=${val}`);
                });
            }
            if (filters.element) {
                filters.element.forEach(val => {
                    const el = form.querySelector(`input[name="element"][value="${val}"]`);
                    if (el && el.classList.contains('owned-filter-checkbox')) el.checked = true;
                    queryParts.push(`element=${val}`);
                });
            }
        } catch (e) {
            console.error('Failed to restore owned filters', e);
        }
    }

    updateOwnedFilterGroupsState();

    const container = document.getElementById('owned-cards-container');
    if (container) {
        if (!isElementInActiveTab(container)) {
            return;
        }
        if (container.dataset.loaded === 'true') {
            return;
        }
        const baseAttr = container.getAttribute('data-base-url') || container.getAttribute('data-url');
        let finalUrl = baseAttr;

        if (queryParts.length > 0) {
            finalUrl = baseAttr + '&' + queryParts.join('&');
        }

        htmx.ajax('GET', finalUrl, {target: '#owned-cards-container', swap: 'innerHTML'});
        container.dataset.loaded = 'true';
    }
}

function hasOwnedFilterSelection(group) {
    const inputs = group.querySelectorAll('input[type="checkbox"]');
    return Array.from(inputs).some((input) => input.checked);
}

function updateOwnedFilterGroupSummary(group) {
    const summary = group.querySelector('[data-filter-summary]');
    if (!summary) return;

    const checkedInputs = Array.from(group.querySelectorAll('input[type="checkbox"]'))
        .filter((input) => input.checked);

    if (checkedInputs.length === 0) {
        summary.classList.remove('has-items');
        summary.innerHTML = '';
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
    summary.innerHTML = items.map((item) => (
        `<button type="button" class="owned-filter-chip" data-input-id="${item.id}" onclick="toggleOwnedFilterChip('${item.id}')">${item.text}</button>`
    )).join('');
}

function toggleOwnedFilterChip(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.checked = !input.checked;
    input.dispatchEvent(new Event('change', { bubbles: true }));
}

function toggleOwnedFilterGroup(button) {
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

function updateOwnedFilterGroupsState() {
    document.querySelectorAll('[data-filter-group]').forEach((group) => {
        updateOwnedFilterGroupSummary(group);
    });
}

function clearFilters() {
    document.querySelectorAll('.filter-checkbox').forEach(el => el.checked = false);
    localStorage.removeItem(STORAGE_KEY_FILTERS);
    
    // Get base URL from current context
    // We need to know the current language
    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    
    htmx.ajax('GET', `/api/records?page=0&lang=${lang}`, {target: '#records-container', swap: 'innerHTML'});
}

function clearOwnedFilters() {
    document.querySelectorAll('.owned-filter-checkbox').forEach(el => el.checked = false);
    localStorage.removeItem(STORAGE_KEY_OWNED_FILTERS);

    const sortSelect = document.getElementById('owned-sort-select');
    if (sortSelect) {
        sortSelect.value = 'rarity';
        if (sortSelect.classList.contains('custom-select-initialized')) {
            reinitCustomSelect(sortSelect);
        }
    }

    document.querySelectorAll('[data-filter-group]').forEach((group) => {
        updateOwnedFilterGroupSummary(group);
        group.classList.remove('is-open');
    });

    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    htmx.ajax('GET', `/api/owned-cards?page=0&lang=${lang}`, {target: '#owned-cards-container', swap: 'innerHTML'});
}

// 刷新记录列表（保留当前筛选条件）
function refreshRecords() {
    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang') || 'en';
    
    // 构建带筛选参数的 URL
    const form = document.getElementById('filter-form');
    const formData = form ? new FormData(form) : null;
    const params = new URLSearchParams();
    
    params.set('page', '0');
    params.set('lang', lang);
    
    // 添加当前筛选条件
    if (formData) {
        formData.forEach((value, key) => {
            if (key === 'rarity' || key === 'card_type') {
                params.append(key, value);
            }
        });
    }
    
    htmx.ajax('GET', `/api/records?${params.toString()}`, {target: '#records-container', swap: 'innerHTML'});
    
    // 显示提示
    showToast('已刷新');
}

function refreshOwnedCards() {
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

    htmx.ajax('GET', `/api/owned-cards?${params.toString()}`, {target: '#owned-cards-container', swap: 'innerHTML'});
    showToast('已刷新');
}

function setOwnedGridCols(value) {
    const container = document.getElementById('owned-cards-container');
    if (!container) return;
    const cols = parseInt(value, 10);
    if (Number.isNaN(cols)) return;

    container.style.setProperty('--owned-grid-cols', cols);
    const label = document.getElementById('owned-cols-value');
    if (label) label.textContent = cols;
    localStorage.setItem(STORAGE_KEY_OWNED_COLS, String(cols));

    document.querySelectorAll('.owned-cols-btn').forEach((button) => {
        const target = parseInt(button.dataset.cols, 10);
        if (target === cols) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });
}

function toggleOwnedCounts() {
    const container = document.getElementById('owned-cards-container');
    if (!container) return;
    container.classList.toggle('show-counts');

    const btn = document.getElementById('owned-counts-toggle');
    if (!btn) return;
    const showText = btn.dataset.showText || btn.textContent;
    const hideText = btn.dataset.hideText || btn.textContent;
    if (container.classList.contains('show-counts')) {
        btn.textContent = hideText;
    } else {
        btn.textContent = showText;
    }
}

function restoreOwnedGridCols() {
    const stored = localStorage.getItem(STORAGE_KEY_OWNED_COLS);
    const value = stored || '5';
    setOwnedGridCols(value);
}

// 全局自动刷新抽象：刷新任何带有 data-auto-refresh 属性的容器
function autoRefreshList(container) {
    if (!container) return;
    
    // 检查容器是否在激活的 Tab 中
    if (!isElementInActiveTab(container)) return;
    
    // 获取刷新配置
    const baseUrl = container.dataset.autoRefresh;
    const includeSelector = container.dataset.refreshInclude;
    
    // 构建 URL
    let url = baseUrl;
    
    // 如果需要包含表单数据（如筛选条件）
    if (includeSelector) {
        const form = document.querySelector(includeSelector);
        const params = new URLSearchParams();
        params.set('page', '0');
        
        // 添加语言参数
        const urlParams = new URLSearchParams(window.location.search);
        const lang = urlParams.get('lang') || 'en';
        params.set('lang', lang);
        
        // 添加表单数据
        if (form) {
            const formData = new FormData(form);
            formData.forEach((value, key) => {
                params.append(key, value);
            });
        }
        
        url = `${baseUrl}?${params.toString()}`;
    }
    
    htmx.ajax('GET', url, {
        target: container,
        swap: 'innerHTML'
    });
}

// Note: isElementInActiveTab 已从 modules/utils.js 导入

// 3. View Mode Logic
function setViewMode(mode) {
    const container = document.getElementById('records-container');
    const btnList = document.getElementById('btn-view-list');
    const btnGrid = document.getElementById('btn-view-grid');

    if (!container || !btnList || !btnGrid) return;

    if (mode === 'grid') {
        container.classList.add('view-grid-layout');
        container.classList.remove('space-y-12');
        
        btnList.classList.remove('active');
        btnGrid.classList.add('active');
    } else {
        container.classList.remove('view-grid-layout');
        container.classList.add('space-y-12');
        
        btnList.classList.add('active');
        btnGrid.classList.remove('active');
    }
    
    localStorage.setItem(STORAGE_KEY_VIEW_MODE, mode);
}

function restoreViewMode() {
    const mode = localStorage.getItem(STORAGE_KEY_VIEW_MODE) || 'list';
    setViewMode(mode);
}

// 4. Theme Logic
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY_THEME, theme);
}

function restoreTheme() {
    const theme = localStorage.getItem(STORAGE_KEY_THEME) || 'brutalist';
    document.documentElement.setAttribute('data-theme', theme);
    
    // Sync selector if it exists
    const selector = document.getElementById('theme-selector');
    if (selector) {
        selector.value = theme;
    }
}

// 5. Tab Logic
function switchTab(tabName, options = {}) {
    const {
        preserveHash = false,
        preferHash = null,
        skipAutoSelect = false
    } = options;
    const initialHash = preferHash !== null ? preferHash : window.location.hash.replace('#', '');
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.add('hidden');
        el.classList.remove('block');
    });

    // Show selected
    const selected = document.getElementById(`tab-content-${tabName}`);
    if (selected) {
        selected.classList.remove('hidden');
        selected.classList.add('block');
    }

    currentTabName = tabName;

    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    const activeBtn = document.getElementById(`tab-btn-${tabName}`);
    if (activeBtn) {
        activeBtn.classList.add('active');

        // Update Main Title based on data-title attribute
        const newTitle = activeBtn.getAttribute('data-title');
        const titleEl = document.getElementById('main-title');
        if (newTitle && titleEl) {
            titleEl.textContent = newTitle;
        }

        // 更新 URL hash 以便刷新后恢复当前 Tab
        const hash = activeBtn.getAttribute('data-hash');
        if (hash && !preserveHash) {
            window.location.hash = hash;
        }
    }

    // Toggle Filters visibility
    const filters = document.getElementById('records-filters');
    if (filters) {
        filters.classList.toggle('hidden', tabName !== 'records');
    }

    if (tabName === 'records') {
        const container = document.getElementById('records-container');
        if (container && container.dataset.loaded !== 'true') {
            restoreFilters();
        }
    }

    if (tabName === 'owned-cards') {
        const container = document.getElementById('owned-cards-container');
        if (container && container.dataset.loaded !== 'true') {
            restoreOwnedFilters();
        }
        updateOwnedFilterGroupsState();
    }

    localStorage.setItem(STORAGE_KEY_TAB, tabName);

    // Auto-select first sidebar item if management tab is empty
    if (tabName === 'management' && !skipAutoSelect) {
        const content = document.getElementById('management-content');
        // Check if content is empty or has only whitespace/text (default message)
        const hasContent = content.querySelector('table') || content.querySelector('form');

        if (!hasContent) {
            // Try to restore from hash first
            const hash = initialHash;
            let targetBtn = null;
            // 检查 hash 是否为 management 子项
            if (hash && ['accounts', 'plans', 'metadata'].includes(hash)) {
                targetBtn = document.querySelector(`.sidebar-btn[data-hash="${hash}"]`);
            }

            // Fallback to first button
            if (!targetBtn) {
                targetBtn = document.querySelector('#tab-content-management .sidebar-btn');
            }

            if (targetBtn) targetBtn.click();
        }
    }
}

function updateSidebarState(btn) {
    document.querySelectorAll('.sidebar-btn').forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    const hash = btn.getAttribute('data-hash');
    if (hash) {
        window.location.hash = hash;
    }
}

function restoreTab() {
    // 优先从 URL hash 恢复，其次从 localStorage
    const hash = window.location.hash.replace('#', '');
    let tabName = null;

    if (hash === 'records' || hash === 'management' || hash === 'owned-cards') {
        // Hash 直接指向 Tab
        tabName = hash;
    } else if (['accounts', 'plans', 'metadata'].includes(hash)) {
        // Hash 指向 management 子项
        tabName = 'management';
    } else {
        // 没有 hash，从 localStorage 恢复
        tabName = localStorage.getItem(STORAGE_KEY_TAB);
    }

    if (tabName) {
        if (hash && ['accounts', 'plans', 'metadata'].includes(hash)) {
            switchTab('management', { preserveHash: true, preferHash: hash });
        } else {
            const btn = document.getElementById(`tab-btn-${tabName}`);
            if (btn) {
                btn.click();
            }
        }
    }
}

// 6. Sortable & Plan Management
function updateTaskItemState(checkbox) {
    const taskItem = checkbox.closest('.task-item');
    if (!taskItem) return;
    const configContainer = taskItem.querySelector('[data-config-container]');

    if (checkbox.checked) {
        taskItem.classList.remove('opacity-50');
        if (configContainer) {
            configContainer.classList.remove('opacity-50');
        }
        taskItem.setAttribute('data-enabled', 'true');
    } else {
        taskItem.classList.add('opacity-50');
        if (configContainer) {
            configContainer.classList.add('opacity-50');
        }
        taskItem.setAttribute('data-enabled', 'false');
    }
}

function updateTaskOrder() {
    const list = document.getElementById('tasks-list');
    if (!list) return;
    const items = list.querySelectorAll('.task-item');
    const orderedTaskTypes = [];

    items.forEach((item) => {
        const taskType = item.getAttribute('data-task-type');
        const isEnabled = item.getAttribute('data-enabled') === 'true';
        if (isEnabled) {
            orderedTaskTypes.push(taskType);
        }
    });

    const orderField = document.getElementById('task_order');
    if (orderField) {
        orderField.value = JSON.stringify(orderedTaskTypes);
    }
}

function getPlansMessages(list) {
    return {
        emptyMessage: list.dataset.emptyMessage || 'No plans assigned. Add one above.',
        duplicateMessage: list.dataset.duplicateMessage || 'Plan already in list!',
        saveErrorMessage: list.dataset.saveErrorMessage || 'Error saving plans',
        saveSuccessMessage: list.dataset.saveSuccessMessage || 'Plans saved successfully!',
        labelActive: list.dataset.labelActive || 'ACTIVE'
    };
}

function checkEmpty(list = document.getElementById('plans-list')) {
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

function addPlan() {
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

function removePlan(btn) {
    const list = document.getElementById('plans-list');
    if (!list) return;
    const item = btn.closest('.plan-item');
    if (!item) return;
    item.remove();
    checkEmpty(list);
}

function savePlans() {
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

function initSortable(context = document) {
    const taskList = context.querySelector('#tasks-list');
    if (taskList && !taskList.dataset.sortableInit) {
        new Sortable(taskList, {
            animation: 150,
            ghostClass: 'bg-subtle',
            handle: '.cursor-move',
            onEnd: function() {
                updateTaskOrder();
            }
        });
        taskList.dataset.sortableInit = 'true';
        updateTaskOrder();
    }

    const plansList = context.querySelector('#plans-list');
    if (plansList && !plansList.dataset.sortableInit) {
        new Sortable(plansList, {
            animation: 150,
            ghostClass: 'bg-subtle',
            handle: '.cursor-move',
            onEnd: function() {
                checkEmpty(plansList);
            }
        });
        plansList.dataset.sortableInit = 'true';
        checkEmpty(plansList);
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    initLang();
    restoreTheme(); // Restore theme first to avoid flash
    restoreTab();
    if (currentTabName === 'records') {
        restoreFilters();
    }
    if (currentTabName === 'owned-cards') {
        restoreOwnedFilters();
    }
    updateOwnedFilterGroupsState();
    restoreViewMode();
    restoreOwnedGridCols();
    initCustomSelects(document); // Initialize custom selects

    // 处理 management 子项的选择（restoreTab 已处理 Tab 级别）
    const hash = window.location.hash.replace('#', '');
    if (hash && ['accounts', 'plans', 'metadata'].includes(hash)) {
        const activeBtn = document.querySelector(`.sidebar-btn.active[data-hash="${hash}"]`);
        if (!activeBtn) {
            // 等待 restoreTab 完成后再选择子项
            setTimeout(() => {
                const targetBtn = document.querySelector(`.sidebar-btn[data-hash="${hash}"]`);
                if (targetBtn) {
                    targetBtn.click();
                }
            }, 0);
        }
    }

    // prefers-reduced-motion support
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mediaQuery.matches) {
        document.documentElement.classList.add('reduce-motion');
    }
    mediaQuery.addEventListener('change', () => {
        if (mediaQuery.matches) {
            document.documentElement.classList.add('reduce-motion');
        } else {
            document.documentElement.classList.remove('reduce-motion');
        }
    });

    // Card preview ESC key support
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && cardPreviewState.isOpen) {
            closeCardPreview();
        }
    });

    // Auto-init on HTMX load
    document.body.addEventListener('htmx:load', function(evt) {
        initCustomSelects(evt.detail.elt);
    });

    document.body.addEventListener('change', (event) => {
        if (event.target && event.target.classList.contains('owned-filter-checkbox')) {
            updateOwnedFilterGroupsState();
        }
    });

    const ownedFilterForm = document.getElementById('owned-filter-form');
    if (ownedFilterForm) {
        ownedFilterForm.addEventListener('click', (event) => {
            const target = event.target;
            if (target && target.tagName === 'LABEL' && target.classList.contains('filter-label')) {
                requestAnimationFrame(() => {
                    updateOwnedFilterGroupsState();
                });
            }
        });

        ownedFilterForm.addEventListener('change', (event) => {
            if (event.target && event.target.classList.contains('owned-filter-checkbox')) {
                requestAnimationFrame(() => {
                    saveOwnedFilters();
                    updateOwnedFilterGroupsState();
                });
            }
        });
    }

    // Modal 内容完成交换后，统一打开并触发初始化
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if (evt.detail && evt.detail.target && evt.detail.target.id === 'modal-content') {
            getModal().openFromSwap();
        }
    });

    // Modal 打开时自动初始化内部组件
    document.addEventListener('modal:opened', (e) => {
        const modalContent = e.detail.modal.content;
        // 自动初始化自定义选择器
        if (typeof initCustomSelects === 'function') {
            initCustomSelects(modalContent);
        }
        if (typeof initSortable === 'function' && modalContent.querySelector('.sortable-list')) {
            initSortable(modalContent);
        }
    });

    // 页面重新获得焦点时自动刷新所有带有 data-auto-refresh 的列表
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            document.querySelectorAll('[data-auto-refresh]').forEach(container => {
                autoRefreshList(container);
            });
        }
    });
});

// --- Custom Select Logic ---

// 重新初始化单个自定义选择器（用于 HTMX 更新后）
function reinitCustomSelect(selectElement) {
    if (!selectElement || !selectElement.classList.contains('js-custom-select')) return;
    
    // 保存原始的父容器引用，用于后续的初始化
    const originalParent = selectElement.parentNode;
    
    // 找到并移除旧的 custom select UI
    const container = selectElement.closest('.custom-select-container');
    if (container) {
        const parent = container.parentNode;
        // 将 select 移回原来的位置
        parent.insertBefore(selectElement, container);
        // 删除旧的 custom select 容器
        container.remove();
    }
    
    // 移除初始化标记，以便可以重新初始化
    selectElement.classList.remove('custom-select-initialized');
    
    // 使用原始父容器进行重新初始化（DOM 移动后 parentNode 可能已改变）
    initCustomSelects(originalParent);
}

function initCustomSelects(context = document) {
    const selects = context.querySelectorAll('select.js-custom-select:not(.custom-select-initialized)');
    
    selects.forEach(select => {
        // Prevent double init
        select.classList.add('custom-select-initialized');
        
        // Create container
        const container = document.createElement('div');
        container.className = 'custom-select-container';
        
        // --- 1. Copy Sizing & Layout Classes from Original Select ---
        // We want 'w-*' classes on the container, and 'text-*', 'p-*', 'font-*' on the trigger.
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

        // Add copied classes to container
        if (containerClasses.length > 0) {
            container.classList.add(...containerClasses);
        }

        select.parentNode.insertBefore(container, select);
        container.appendChild(select); // Move select inside
        
        // Create Trigger
        const trigger = document.createElement('div');
        trigger.className = 'custom-select-trigger';
        // Add copied classes to trigger
        if (triggerClasses.length > 0) {
            trigger.classList.add(...triggerClasses);
        }
        
        // Get initial text
        const selectedOption = select.options[select.selectedIndex];
        const initialText = selectedOption ? selectedOption.text : 'Select...';
        trigger.innerHTML = `<span>${initialText}</span><span class="custom-select-arrow">▼</span>`;
        container.appendChild(trigger);
        
        // Create Options List
        const optionsList = document.createElement('div');
        optionsList.className = 'custom-select-options';
        
        Array.from(select.options).forEach(option => {
            const optDiv = document.createElement('div');
            optDiv.className = 'custom-select-option';
            if (option.selected) optDiv.classList.add('selected');
            optDiv.textContent = option.text;
            optDiv.dataset.value = option.value;
            
            // Copy text size classes to options too if needed for consistency? 
            // Usually options can stay default size, but let's see. 
            // For now, keep standard size options unless requested.

            optDiv.addEventListener('click', (e) => {
                e.stopPropagation();
                
                // Update Select
                select.value = option.value;
                select.dispatchEvent(new Event('change')); // Notify listeners
                
                // Update UI
                trigger.querySelector('span').textContent = option.text;
                container.querySelectorAll('.custom-select-option').forEach(el => el.classList.remove('selected'));
                optDiv.classList.add('selected');
                
                // Close
                container.classList.remove('open');
                container.classList.remove('open-up');
            });
            
            optionsList.appendChild(optDiv);
        });
        
        container.appendChild(optionsList);
        
        // Toggle Logic with Smart Positioning
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            
            // Close others
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
                // Smart Positioning Logic
                const rect = container.getBoundingClientRect();
                const viewportHeight = window.innerHeight;
                // Estimate options height (max-height is 250px)
                // We can use the actual height if rendered, but it's hidden. 
                // Simple heuristic: if bottom space < 260px and top space > 260px, open up.
                const spaceBelow = viewportHeight - rect.bottom;
                const spaceAbove = rect.top;
                
                // Reset first
                container.classList.remove('open-up');
                
                if (spaceBelow < 260 && spaceAbove > 260) {
                    container.classList.add('open-up');
                }
                
                container.classList.add('open');
            }
        });

        // Listen for external updates to the original select (e.g. reset form)
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
    
    // Global click to close
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

// --- Global Exports for HTML Inline Handlers ---
// 将需要在 HTML 中通过 onclick/onchange 调用的函数导出到全局
window.setLang = setLang;
window.setTheme = setTheme;
window.saveFilters = saveFilters;
window.saveOwnedFilters = saveOwnedFilters;
window.clearFilters = clearFilters;
window.clearOwnedFilters = clearOwnedFilters;
window.refreshRecords = refreshRecords;
window.refreshOwnedCards = refreshOwnedCards;
window.setViewMode = setViewMode;
window.switchTab = switchTab;
window.openCardPreview = openCardPreview;
window.closeCardPreview = closeCardPreview;
window.setOwnedGridCols = setOwnedGridCols;
window.toggleOwnedCounts = toggleOwnedCounts;
window.toggleOwnedFilterGroup = toggleOwnedFilterGroup;
window.toggleOwnedFilterChip = toggleOwnedFilterChip;
window.reinitCustomSelect = reinitCustomSelect;
window.updateSidebarState = updateSidebarState;
window.updateTaskItemState = updateTaskItemState;
window.updateTaskOrder = updateTaskOrder;
window.addPlan = addPlan;
window.removePlan = removePlan;
window.savePlans = savePlans;
// 以下函数从 modules/utils.js 导入，已自动注册到全局
// window.showToast
