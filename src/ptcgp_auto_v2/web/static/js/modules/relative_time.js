// --- 相对时间文本 ---
function getRelativeLabels(container) {
    return {
        locale: container.dataset.relativeLocale || 'en',
        justNow: container.dataset.relativeJustNow || 'just now',
        soon: container.dataset.relativeSoon || 'soon',
        minutes: container.dataset.relativeMinutes || 'min',
        hours: container.dataset.relativeHours || 'hr',
        days: container.dataset.relativeDays || 'day',
        ago: container.dataset.relativeAgo || 'ago',
        in: container.dataset.relativeIn || 'in'
    };
}

// --- 时长文案 ---
function getDurationLabels(container) {
    return {
        locale: container.dataset.durationLocale || container.dataset.relativeLocale || 'en',
        days: container.dataset.durationDays || 'Days',
        hours: container.dataset.durationHours || 'Hours',
        minutes: container.dataset.durationMinutes || 'Minutes',
        seconds: container.dataset.durationSeconds || 'Seconds'
    };
}

// --- 格式化相对时间 ---
function formatRelativeTime(target, labels) {
    const diffMs = target.getTime() - Date.now();
    const future = diffMs > 0;
    const absSec = Math.abs(diffMs) / 1000;

    if (absSec < 60) {
        return future ? labels.soon : labels.justNow;
    }

    let value = 0;
    let unit = labels.minutes;
    if (absSec < 3600) {
        value = Math.round(absSec / 60);
        unit = labels.minutes;
    } else if (absSec < 86400) {
        value = Math.round(absSec / 3600);
        unit = labels.hours;
    } else {
        value = Math.round(absSec / 86400);
        unit = labels.days;
    }

    if (labels.locale.startsWith('en')) {
        return future ? `${labels.in} ${value} ${unit}` : `${value} ${unit} ${labels.ago}`;
    }

    return `${value}${unit}${future ? labels.in : labels.ago}`;
}

// --- 格式化精确时长 ---
export function formatExactDuration(totalSeconds, labels) {
    const normalizedSeconds = Number(totalSeconds);
    if (!Number.isFinite(normalizedSeconds)) {
        return '';
    }

    let remainingSeconds = Math.max(0, Math.trunc(normalizedSeconds));
    const dayCount = Math.floor(remainingSeconds / 86400);
    remainingSeconds %= 86400;
    const hourCount = Math.floor(remainingSeconds / 3600);
    remainingSeconds %= 3600;
    const minuteCount = Math.floor(remainingSeconds / 60);
    const secondCount = remainingSeconds % 60;

    const parts = [];
    if (dayCount > 0) {
        parts.push([dayCount, labels.days]);
    }
    if (hourCount > 0) {
        parts.push([hourCount, labels.hours]);
    }
    if (minuteCount > 0) {
        parts.push([minuteCount, labels.minutes]);
    }
    parts.push([secondCount, labels.seconds]);

    if (labels.locale === 'en') {
        return parts.map(([value, label]) => `${value} ${label}`).join(' ');
    }
    return parts.map(([value, label]) => `${value}${label}`).join('');
}

// --- 更新相对时间 ---
export function updateRelativeTimes(root = document) {
    const containers = [];
    if (root && root.nodeType === 1 && root.matches && root.matches('[data-relative-locale]')) {
        containers.push(root);
    }
    if (root && root.nodeType === 1 && root.closest) {
        const closestContainer = root.closest('[data-relative-locale]');
        if (closestContainer && !containers.includes(closestContainer)) {
            containers.push(closestContainer);
        }
    }
    if (root && root.querySelectorAll) {
        containers.push(...root.querySelectorAll('[data-relative-locale]'));
    }
    containers.forEach((container) => {
        const relativeLabels = getRelativeLabels(container);
        const durationLabels = getDurationLabels(container);
        container.querySelectorAll('.relative-time').forEach((el) => {
            const iso = el.dataset.iso;
            if (!iso) return;
            const date = new Date(iso);
            if (Number.isNaN(date.getTime())) return;
            el.textContent = formatRelativeTime(date, relativeLabels);
            if (el.dataset.tooltip) {
                el.setAttribute('data-tooltip', el.dataset.tooltip);
            }
        });
        container.querySelectorAll('.relative-duration').forEach((el) => {
            const seconds = el.dataset.seconds;
            if (!seconds) return;
            const text = formatExactDuration(seconds, durationLabels);
            if (!text) return;
            el.textContent = text;
        });
    });
}
