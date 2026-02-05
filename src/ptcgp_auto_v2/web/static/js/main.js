import { initApp, setLang, setTheme, setViewMode } from './modules/bootstrap.js';
import {
    saveFilters,
    saveOwnedFilters,
    saveFormFilters,
    saveTasksFilters,
    clearFilters,
    clearOwnedFilters,
    refreshRecords,
    refreshOwnedCards,
    toggleOwnedFilterGroup,
    toggleOwnedFilterChip,
} from './modules/filters.js';
import { switchTab, updateSidebarState } from './modules/tabs.js';
import { openCardPreview, closeCardPreview } from './modules/card_preview.js';
import { setOwnedGridCols, toggleOwnedCounts } from './modules/owned_cards.js';
import { reinitCustomSelect, filterCustomSelectOptions } from './modules/custom_select.js';
import { updateTaskItemState, updateTaskOrder, updateIntervalSeconds } from './modules/tasks.js';
import { addPlan, removePlan, savePlans } from './modules/plans.js';

// --- 初始化入口 ---
initApp();

// --- 全局导出（用于内联事件） ---
window.setLang = setLang;
window.setTheme = setTheme;
window.saveFilters = saveFilters;
window.saveOwnedFilters = saveOwnedFilters;
window.saveFormFilters = saveFormFilters;
window.saveTasksFilters = saveTasksFilters;
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
window.updateIntervalSeconds = updateIntervalSeconds;
window.addPlan = addPlan;
window.removePlan = removePlan;
window.savePlans = savePlans;
window.filterCustomSelectOptions = filterCustomSelectOptions;
