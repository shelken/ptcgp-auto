import { getModal } from './modal.js';
import {
    clearFilters,
    refreshOwnedCards,
    refreshRecords,
    clearOwnedFilters,
    clearOwnedFilterGroup,
    toggleOwnedFilterGroup,
    toggleOwnedFilterChip,
} from './features/filters/index.js';
import { setOwnedGridCols, toggleOwnedCounts } from './features/owned_cards.js';
import { removePlan, savePlans } from './features/plans.js';
import { openCardPreview } from './features/card_preview.js';
import { switchTab, updateSidebarState } from './tabs.js';
import { cycleThemeMode, setManualTheme } from './theme.js';
import { showToast } from './utils.js';
import { cancelExchangeForm, showExchangeForm } from './features/exchange_cards.js';
import { setLang, setViewMode, toggleRecordFilterPanel } from './ui_preferences.js';
import { getNotificationDrawer } from './features/notification_panel.js';
import { selectTaskAccountOption } from './features/filters/tasks_remote_account.js';


function toggleSection(sectionId, iconId = null) {
    if (!sectionId) return;
    const section = document.getElementById(sectionId);
    if (!section) return;

    const shouldShow = section.classList.contains('hidden');
    section.classList.toggle('hidden', !shouldShow);

    if (!iconId) return;
    const icon = document.getElementById(iconId);
    if (!icon) return;
    icon.style.transform = shouldShow ? 'rotate(0deg)' : 'rotate(-90deg)';
}

async function copyTextWithToast(text, message) {
    if (!text) return;
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
        } else {
            const input = document.createElement('textarea');
            input.value = text;
            input.style.position = 'fixed';
            input.style.opacity = '0';
            document.body.appendChild(input);
            input.focus();
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
        }
        showToast(message || 'Copied!');
    } catch (error) {
        console.error('复制失败:', error);
    }
}

function closeThemePopoverWhenOutsideClick(target) {
    const popover = document.getElementById('theme-popover');
    if (!popover || popover.classList.contains('hidden')) return;
    const isInsidePopover = target.closest('#theme-popover');
    const isToggleBtn = target.closest('#theme-picker-btn');
    if (!isInsidePopover && !isToggleBtn) {
        popover.classList.add('hidden');
    }
}

export function handleActionClick(event) {
    const target = event.target;
    if (!(target instanceof Element)) return;

    closeThemePopoverWhenOutsideClick(target);

    const actionButton = target.closest('[data-action]');
    if (!actionButton) return;
    const { action } = actionButton.dataset;

    if (action === 'set-lang' && actionButton.dataset.lang) {
        setLang(actionButton.dataset.lang);
        return;
    }

    if (action === 'switch-tab' && actionButton.dataset.tab) {
        switchTab(actionButton.dataset.tab);
        return;
    }

    if (action === 'set-view-mode' && actionButton.dataset.mode) {
        setViewMode(actionButton.dataset.mode);
        return;
    }

    if (action === 'cycle-theme-mode') {
        cycleThemeMode();
        return;
    }

    if (action === 'toggle-theme-popover') {
        const popover = document.getElementById('theme-popover');
        if (popover) {
            const isHidden = popover.classList.contains('hidden');
            popover.classList.toggle('hidden', !isHidden);
        }
        return;
    }

    if (action === 'select-theme' && actionButton.dataset.themeValue) {
        setManualTheme(actionButton.dataset.themeValue);
        const popover = document.getElementById('theme-popover');
        if (popover) popover.classList.add('hidden');
        return;
    }

    if (action === 'toggle-notification-panel') {
        getNotificationDrawer().toggle();
        return;
    }

    if (action === 'close-notification-panel') {
        getNotificationDrawer().close();
        return;
    }

    if (action === 'toggle-owned-filter-group') {
        toggleOwnedFilterGroup(actionButton);
        return;
    }

    if (action === 'toggle-owned-filter-chip') {
        const inputId = actionButton.dataset.inputId;
        if (inputId) {
            toggleOwnedFilterChip(inputId);
        }
        return;
    }

    if (action === 'set-owned-grid-cols') {
        setOwnedGridCols(actionButton.dataset.cols);
        return;
    }

    if (action === 'toggle-owned-counts') {
        toggleOwnedCounts();
        return;
    }

    if (action === 'update-sidebar-state') {
        updateSidebarState(actionButton);
        return;
    }

    if (action === 'refresh-records') {
        refreshRecords(actionButton);
        return;
    }

    if (action === 'clear-record-filters') {
        clearFilters();
        return;
    }

    if (action === 'toggle-record-filters') {
        toggleRecordFilterPanel();
        return;
    }

    if (action === 'refresh-owned-cards') {
        refreshOwnedCards(actionButton);
        return;
    }

    if (action === 'clear-owned-filters') {
        clearOwnedFilters();
        return;
    }

    if (action === 'clear-owned-filter-group') {
        clearOwnedFilterGroup(actionButton);
        return;
    }

    if (action === 'save-account-plans') {
        savePlans(actionButton);
        return;
    }

    if (action === 'remove-plan') {
        removePlan(actionButton);
        return;
    }

    if (action === 'open-card-preview') {
        openCardPreview(actionButton);
        return;
    }

    if (action === 'close-modal') {
        getModal().close();
        return;
    }

    if (action === 'toggle-section') {
        toggleSection(actionButton.dataset.targetId, actionButton.dataset.iconId || null);
        return;
    }

    if (action === 'copy-text') {
        copyTextWithToast(actionButton.dataset.copyText, actionButton.dataset.copyToast);
        return;
    }

    if (action === 'select-task-account-option') {
        selectTaskAccountOption(actionButton);
        return;
    }

    if (action === 'set-daily-gift-date' && actionButton.dataset.date) {
        const dateValue = actionButton.dataset.date;
        const form = actionButton.closest('form');
        if (form) {
            const valueInput = form.querySelector('[data-role="value"]');
            const labelEl = form.querySelector('[data-role="label"]');
            if (valueInput) valueInput.value = dateValue;
            if (labelEl) labelEl.textContent = dateValue;
        }
        const stateInput = document.querySelector('#daily-gift-state-form input[name="biz_date_local"]');
        if (stateInput) stateInput.value = dateValue;
        return;
    }

    if (action === 'show-exchange-form') {
        showExchangeForm(actionButton);
        return;
    }

    if (action === 'cancel-exchange-form') {
        cancelExchangeForm();
    }
}
