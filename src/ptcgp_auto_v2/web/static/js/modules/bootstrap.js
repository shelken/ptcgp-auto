import { restoreFilters, restoreOwnedFilters, updateOwnedFilterGroupsState } from './features/filters/index.js';
import { restoreOwnedGridCols } from './features/owned_cards.js';
import { restoreTab, currentTabName, syncTaskSidebarRequestUrl } from './tabs.js';
import { initTheme } from './theme.js';
import {
    initLang,
    restoreViewMode,
    restoreRecordFilterPanelState,
} from './ui_preferences.js';
import { initCustomSelects } from './custom_select.js';
import { initDailyGiftDatePickers } from './features/daily_gift.js';
import { bindAppEventHandlers } from './event_bindings.js';
import { getNotificationDrawer } from './features/notification_panel.js';

// 导出通知面板管理器供其他模块使用
export { getNotificationDrawer };

function restoreInitialTabData() {
    if (currentTabName === 'records') {
        restoreFilters();
    }
    if (currentTabName === 'owned-cards') {
        restoreOwnedFilters();
    }
}

// --- 初始化入口 ---
export function initApp() {
    document.addEventListener('DOMContentLoaded', () => {
        initLang();
        initTheme();

        bindAppEventHandlers(restoreRecordFilterPanelState);

        syncTaskSidebarRequestUrl();
        restoreTab();
        restoreInitialTabData();
        updateOwnedFilterGroupsState();

        restoreViewMode();
        restoreRecordFilterPanelState();
        restoreOwnedGridCols();

        initCustomSelects(document);
        initDailyGiftDatePickers(document);
    });
}
