function parseYmd(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || '').trim());
    if (!match) return null;
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    if (!year || month < 1 || month > 12 || day < 1 || day > 31) return null;
    const date = new Date(year, month - 1, day);
    if (
        date.getFullYear() !== year
        || date.getMonth() !== month - 1
        || date.getDate() !== day
    ) {
        return null;
    }
    return date;
}

function formatYmd(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function startOfMonth(date) {
    return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date, delta) {
    return new Date(date.getFullYear(), date.getMonth() + delta, 1);
}

function getLocale(picker) {
    const raw = picker.dataset.locale || 'en';
    return String(raw).replace('_', '-');
}

function getWeekdayLabels(locale) {
    const formatter = new Intl.DateTimeFormat(locale, { weekday: 'short' });
    const base = new Date(Date.UTC(2026, 0, 4));
    return Array.from({ length: 7 }, (_, i) => formatter.format(new Date(base.getTime() + i * 86400000)));
}

function getMonthLabel(date, locale) {
    return new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'long' }).format(date);
}

function closeAllPanels() {
    document.querySelectorAll('[data-daily-gift-date-picker]').forEach((picker) => {
        const panel = picker.querySelector('[data-role="panel"]');
        if (panel) panel.classList.add('hidden');
    });
}

function renderDays(picker) {
    const panel = picker.querySelector('[data-role="panel"]');
    const daysWrap = picker.querySelector('[data-role="days"]');
    const weekdaysWrap = picker.querySelector('[data-role="weekdays"]');
    const monthLabel = picker.querySelector('[data-role="month-label"]');
    const valueInput = picker.querySelector('[data-role="value"]');
    const labelEl = picker.querySelector('[data-role="label"]');
    const form = picker.closest('form');
    if (!panel || !daysWrap || !weekdaysWrap || !monthLabel || !valueInput || !labelEl || !form) return;

    const locale = getLocale(picker);
    const selectedDate = parseYmd(valueInput.value) || new Date();
    const currentMonth = picker.__currentMonth || startOfMonth(selectedDate);
    picker.__currentMonth = startOfMonth(currentMonth);

    monthLabel.textContent = getMonthLabel(currentMonth, locale);
    labelEl.textContent = formatYmd(selectedDate);

    weekdaysWrap.innerHTML = '';
    getWeekdayLabels(locale).forEach((label) => {
        const cell = document.createElement('div');
        cell.className = 'daily-date-weekday';
        cell.textContent = label;
        weekdaysWrap.appendChild(cell);
    });

    const firstDay = startOfMonth(currentMonth);
    const firstWeekday = (firstDay.getDay() + 6) % 7;
    const daysInMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getDate();

    daysWrap.innerHTML = '';

    for (let i = 0; i < firstWeekday; i += 1) {
        const empty = document.createElement('div');
        empty.className = 'daily-date-cell-empty';
        daysWrap.appendChild(empty);
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
        const date = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), day);
        const ymd = formatYmd(date);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'daily-date-day brutal-btn text-xs px-2 py-1';
        if (ymd === valueInput.value) {
            btn.classList.add('active');
        }
        btn.textContent = String(day);
        btn.setAttribute('data-value', ymd);
        btn.addEventListener('click', () => {
            valueInput.value = ymd;
            labelEl.textContent = ymd;
            panel.classList.add('hidden');
            form.requestSubmit();
        });
        daysWrap.appendChild(btn);
    }
}

function initSinglePicker(picker) {
    if (picker.dataset.inited === '1') return;
    const trigger = picker.querySelector('[data-role="trigger"]');
    const panel = picker.querySelector('[data-role="panel"]');
    const prevBtn = picker.querySelector('[data-role="prev-month"]');
    const nextBtn = picker.querySelector('[data-role="next-month"]');
    const todayBtn = picker.querySelector('[data-role="today"]');
    const valueInput = picker.querySelector('[data-role="value"]');
    if (!trigger || !panel || !prevBtn || !nextBtn || !todayBtn || !valueInput) return;

    const selected = parseYmd(valueInput.value) || new Date();
    valueInput.value = formatYmd(selected);
    picker.__currentMonth = startOfMonth(selected);

    trigger.addEventListener('click', () => {
        const wasHidden = panel.classList.contains('hidden');
        closeAllPanels();
        if (wasHidden) {
            panel.classList.remove('hidden');
            renderDays(picker);
        }
    });

    prevBtn.addEventListener('click', () => {
        picker.__currentMonth = addMonths(picker.__currentMonth || startOfMonth(new Date()), -1);
        renderDays(picker);
    });

    nextBtn.addEventListener('click', () => {
        picker.__currentMonth = addMonths(picker.__currentMonth || startOfMonth(new Date()), 1);
        renderDays(picker);
    });

    todayBtn.addEventListener('click', () => {
        const today = new Date();
        const todayYmd = formatYmd(today);
        valueInput.value = todayYmd;
        picker.__currentMonth = startOfMonth(today);
        const form = picker.closest('form');
        closeAllPanels();
        if (form) form.requestSubmit();
    });

    picker.dataset.inited = '1';
    renderDays(picker);
}

/** 初始化每日送卡日期选择器（主题化自定义面板）。 */
export function initDailyGiftDatePickers(root = document) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('[data-daily-gift-date-picker]').forEach((picker) => {
        initSinglePicker(picker);
    });
}

document.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest('[data-daily-gift-date-picker]')) return;
    closeAllPanels();
});
