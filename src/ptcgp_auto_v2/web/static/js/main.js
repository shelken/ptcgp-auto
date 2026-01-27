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
            const firstBtn = document.querySelector('#tab-content-management .sidebar-btn');
            if (firstBtn) firstBtn.click();
        }
    }
}

function restoreTab() {
    const tab = localStorage.getItem(STORAGE_KEY_TAB);
    if (tab) {
        const btn = document.getElementById(`tab-btn-${tab}`);
        if (btn) {
            // Trigger click to ensure HTMX loading if needed
            // But we need to be careful about infinite loops if onclick calls this
            // Actually, switchTab is called by onclick.
            // If we call switchTab directly, HTMX won't trigger if it relies on 'click' event
            // But our buttons use hx-trigger="click once"

            // If we just call switchTab, content hidden by hx-trigger won't load
            // So we should click it.
            btn.click();
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
});