import { restoreFilters, restoreOwnedFilters, updateOwnedFilterGroupsState } from './features/filters/index.js';
import { restoreOwnedGridCols } from './features/owned_cards.js';
import { restoreTab, currentTabName } from './tabs.js';
import { initTheme } from './theme.js';
import { isManagementHash } from './constants.js';
import {
    initLang,
    restoreViewMode,
    restoreRecordFilterPanelState,
} from './ui_preferences.js';
import { initCustomSelects } from './custom_select.js';
import { initDailyGiftDatePickers } from './features/daily_gift.js';
import { bindAppEventHandlers } from './event_bindings.js';

function restoreInitialTabData() {
    if (currentTabName === 'records') {
        restoreFilters();
    }
    if (currentTabName === 'owned-cards') {
        restoreOwnedFilters();
    }
}

function ensureManagementHashLoaded() {
    const hash = window.location.hash.replace('#', '');
    if (!hash || !isManagementHash(hash)) return;

    const activeBtn = document.querySelector(`.sidebar-btn.active[data-hash="${hash}"]`);
    if (activeBtn) return;

    setTimeout(() => {
        const targetBtn = document.querySelector(`.sidebar-btn[data-hash="${hash}"]`);
        if (targetBtn) {
            targetBtn.click();
        }
    }, 0);
}

// --- 初始化入口 ---
export function initApp() {
    document.addEventListener('DOMContentLoaded', () => {
        initLang();
        initTheme();

        bindAppEventHandlers(restoreRecordFilterPanelState);

        restoreTab();
        restoreInitialTabData();
        updateOwnedFilterGroupsState();

        restoreViewMode();
        restoreRecordFilterPanelState();
        restoreOwnedGridCols();

        initCustomSelects(document);
        initDailyGiftDatePickers(document);

        ensureManagementHashLoaded();
    });
}
