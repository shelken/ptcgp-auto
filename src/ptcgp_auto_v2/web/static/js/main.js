// --- Constants ---
const STORAGE_KEY_LANG = 'ptcgp_lang';
const STORAGE_KEY_FILTERS = 'ptcgp_filters';
const STORAGE_KEY_VIEW_MODE = 'ptcgp_view_mode';
const STORAGE_KEY_THEME = 'ptcgp_theme';

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

// Init
document.addEventListener('DOMContentLoaded', () => {
    initLang();
    restoreTheme(); // Restore theme first to avoid flash
    restoreFilters(); // This triggers data load
    restoreViewMode();
});