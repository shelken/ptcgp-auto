// --- Constants ---
const STORAGE_KEY_LANG = 'ptcgp_lang';
const STORAGE_KEY_FILTERS = 'ptcgp_filters';
const STORAGE_KEY_VIEW_MODE = 'ptcgp_view_mode';
const STORAGE_KEY_THEME = 'ptcgp_theme';
const STORAGE_KEY_TAB = 'ptcgp_active_tab';

// --- Focus Management ---
let previousActiveElement = null;

function saveFocus() {
    previousActiveElement = document.activeElement;
}

function restoreFocus() {
    if (previousActiveElement && previousActiveElement.focus) {
        previousActiveElement.focus();
    }
}

// --- Toast with aria-live ---
function showToast(message) {
    // Create or get toast container
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'true');
        container.className = 'fixed bottom-4 right-4 z-50 flex flex-col gap-2';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = 'bg-black text-white px-4 py-2 rounded shadow-lg transition-opacity duration-300';
    toast.textContent = message;
    toast.setAttribute('role', 'alert');

    container.appendChild(toast);

    // Fade out and remove
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
            container.removeChild(toast);
            if (container.children.length === 0) {
                container.remove();
            }
        }, 300);
    }, 2000);
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
        const baseAttr = container.getAttribute('data-url');
        let finalUrl = baseAttr;

        if (queryParts.length > 0) {
            finalUrl = baseAttr + '&' + queryParts.join('&');
            container.setAttribute('data-url', finalUrl);
        }

        htmx.ajax('GET', finalUrl, {target: '#records-container', swap: 'innerHTML'});
    }
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
function switchTab(tabName) {
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
        if (hash) {
            window.location.hash = hash;
        }
    }

    // Toggle Filters visibility
    const filters = document.getElementById('records-filters');
    if (filters) {
        filters.classList.toggle('hidden', tabName !== 'records');
    }

    localStorage.setItem(STORAGE_KEY_TAB, tabName);

    // Auto-select first sidebar item if management tab is empty
    if (tabName === 'management') {
        const content = document.getElementById('management-content');
        // Check if content is empty or has only whitespace/text (default message)
        const hasContent = content.querySelector('table') || content.querySelector('form');

        if (!hasContent) {
            // Try to restore from hash first
            const hash = window.location.hash.replace('#', '');
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

    if (hash === 'records' || hash === 'management') {
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
        const btn = document.getElementById(`tab-btn-${tabName}`);
        if (btn) {
            // 如果 hash 匹配当前 Tab，不需要重复点击
            // 但需要处理 management 子项的情况
            if (hash && ['accounts', 'plans', 'metadata'].includes(hash)) {
                // 切换到 management tab，然后让 DOMContentLoaded 处理子项
                btn.click();
            } else if (!hash || hash !== tabName) {
                // 没有 hash 或 hash 与恢复的 tab 不一致，需要点击
                btn.click();
            }
            // 如果 hash === tabName，页面已经正确显示，不需要点击
        }
    }
}

// 6. Modal Logic
function openModal(contentHtml) {
    const container = document.getElementById('modal-container');
    const content = document.getElementById('modal-content');
    if (container && content) {
        saveFocus();
        content.innerHTML = contentHtml;
        container.classList.remove('hidden');
        // Re-scan for HTMX content in modal
        htmx.process(content);
        // Focus first focusable element in modal
        const firstFocusable = content.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (firstFocusable) {
            firstFocusable.focus();
        }
        // Trap focus in modal
        container.setAttribute('aria-modal', 'true');
        container.setAttribute('role', 'dialog');
    }
}

function closeModal(event) {
    // If event is provided, only close if clicked on backdrop (id=modal-container)
    if (event && event.target.id !== 'modal-container') return;

    const container = document.getElementById('modal-container');
    if (container) {
        container.classList.add('hidden');
        container.removeAttribute('aria-modal');
        container.removeAttribute('role');
        // Clear content to stop any polling or video playing
        document.getElementById('modal-content').innerHTML = '';
        restoreFocus();
    }
}

// Helper to close modal from inside (e.g. Cancel button)
function forceCloseModal() {
    const container = document.getElementById('modal-container');
    if (container) {
        container.classList.add('hidden');
        container.removeAttribute('aria-modal');
        container.removeAttribute('role');
        document.getElementById('modal-content').innerHTML = '';
        restoreFocus();
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    initLang();
    restoreTheme(); // Restore theme first to avoid flash
    restoreTab();
    restoreFilters(); // This triggers data load
    restoreViewMode();
    initCustomSelects(document); // Initialize custom selects

    // 处理 management 子项的选择（restoreTab 已处理 Tab 级别）
    const hash = window.location.hash.replace('#', '');
    if (hash && ['accounts', 'plans', 'metadata'].includes(hash)) {
        // 等待 restoreTab 完成后再选择子项
        setTimeout(() => {
            const targetBtn = document.querySelector(`.sidebar-btn[data-hash="${hash}"]`);
            if (targetBtn) {
                targetBtn.click();
            }
        }, 0);
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

    // Auto-init on HTMX load
    document.body.addEventListener('htmx:load', function(evt) {
        initCustomSelects(evt.detail.elt);
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
